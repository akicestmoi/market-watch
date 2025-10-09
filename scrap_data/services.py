import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from typing import Dict, List, Optional, TypedDict
from copy import deepcopy
import environ
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache
from dateutil.relativedelta import relativedelta
from django.http import Http404


import shared.services as shared_services
from scrap_data.models import (
    AssetClassChoices,
    AssetTypeChoices,
    LocationChoices,
    MarketPriceModel,
    SourceChoices,
)

env = environ.Env()


class TickerInfo(TypedDict):
    """Ticker information dictionnary."""

    asset_class: AssetClassChoices
    location: LocationChoices
    asset: str
    name: str
    maturity: Optional[float]
    asset_type: AssetTypeChoices
    ticker: str
    source: SourceChoices


class MarketData(TypedDict):
    """Ticker information dictionnary."""

    asset_class: AssetClassChoices
    location: LocationChoices
    asset: str
    name: str
    maturity: Optional[float]
    asset_type: AssetTypeChoices
    ticker: str
    price: Optional[float]
    date: date
    source: SourceChoices
    comment: Optional[str]


class PriceChange(TypedDict):
    """Price change dictionnary."""

    asset_class: AssetClassChoices
    asset_type: AssetTypeChoices
    location: LocationChoices
    asset: str
    name: str
    maturity: Optional[float]
    price_change: Optional[float]
    price_change_pct: Optional[float]


class YieldCurvePoint(TypedDict):
    """Information on Yield Curve specific tenor."""

    maturity: Optional[float]
    price: Optional[float]
    short_name: str


class HistoricalPrice(TypedDict):
    """Information of a specific historical price."""

    price_date: date
    price: Optional[float]


class AssetNames(TypedDict):
    """Asset names dictionnary."""

    short_name: str
    full_name: str


with open("scrap_data/data_sources/market_data.json") as f:
    ASSETS_BASE_INFO = json.load(f)

SOURCE_SCRAP_MAP = {
    SourceChoices.GOV_TREASURY_DEPT: lambda d, t: _get_treasury_yield_from_dep_treasury(
        d, t
    ),
    SourceChoices.FRED: lambda d, t: _get_fed_funds_rate_from_fred(d, t),
    SourceChoices.NYFED: lambda d, _: _get_sofr_from_nyfed(d),
    SourceChoices.WEBSTAT: lambda d, t: _get_webstat_rates(d, t),
    SourceChoices.BUNDESBANK: lambda d, t: _get_bund_yield_from_bundesbank(d, t),
    SourceChoices.BOJ: lambda d, _: _get_mutan_rate_from_boj(d),
    SourceChoices.BB: lambda d, t: _get_jgb_yield_from_bb(d, t),
    SourceChoices.GLOBAL_RATES: lambda d, t: _scrap_euribor_from_global_rates(d, t),
    SourceChoices.YAHOO: lambda d, t: _get_yahoo_finance_closing_prices(d, t),
}


def _parse_str_decimals_to_float(a: str) -> Optional[float]:
    """Parse French and English string decimals to float."""
    return float(str(a).replace(",", ".")) if pd.notna(a) else None


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_yahoo_finance_closing_prices(
    target_date: date, ticker: str
) -> Optional[float]:
    """Get closing prices from Yahoo Finance.

    Using publicly available yahoo scrapper module yfiance.
    """
    prices = yf.Ticker(ticker).history(period="5d").reset_index()
    closing_price = prices[prices["Date"].dt.date == target_date].reset_index()
    if not closing_price.empty:
        return closing_price.loc[0, "Close"]


@ttl_cache(maxsize=128, ttl=10 * 60)
def _scrap_euribor_from_global_rates(target_date: date, ticker: str) -> Optional[float]:
    """Scrap euribor rates from GlobalRates.

    Source: https://www.global-rates.com/en/
    """
    res = requests.get(
        f"https://www.global-rates.com/en/interest-rates/euribor/{ticker}"
    )
    res.raise_for_status()
    soup = BeautifulSoup(res.content, "html.parser")

    table = soup.find("table")
    if not table:
        raise ValueError("Could not find Euribor rates table on page")

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) == 2:
            raw_date = cells[0].get_text(strip=True)
            raw_rate = cells[1].get_text(strip=True)

            try:
                parsed_date = datetime.strptime(raw_date, "%m-%d-%Y").date()
            except ValueError:
                continue

            if parsed_date == target_date:
                rate_str = raw_rate.replace("%", "").replace(",", ".").strip()
                try:
                    return float(rate_str)
                except ValueError:
                    return


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_fed_funds_rate_from_fred(target_date: date, ticker: str) -> Optional[float]:
    """Get Fedfund rate from FRED via API

    Source: https://fred.stlouisfed.org/series/FEDFUNDS
    """
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    obs_start = target_date - relativedelta(months=2)
    query_params = f"series_id={ticker}&api_key={env('FRED_API_KEY')}&file_type=json&observation_start={obs_start}&sort_order=desc"
    r = requests.get(f"{BASE_URL}?{query_params}")
    result = json.loads(r.content)
    observations = result.get("observations", [])
    if observations and (value := observations[0].get("value")):
        return float(value)


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_sofr_from_nyfed(target_date: date) -> Optional[float]:
    """
    Scrap SOFR rate from NY Fed XML.

    Source: https://www.newyorkfed.org/markets/reference-rates/sofr
    """
    response = requests.get(
        "https://markets.newyorkfed.org/read?productCode=50&eventCodes=520&limit=25&startPosition=0&sort=postDt:-1&format=xml"
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    for rate in root.findall(".//rate"):
        effective_date = rate.find("effectiveDate").text
        if effective_date == target_date.isoformat():
            percent_rate = rate.find("percentRate").text
            return float(percent_rate)


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_treasury_yield_curve_from_dep_treasury(target_date: date) -> dict:
    """
    Scrap entire UST yield curves from Treasury department.

    Source: https://home.treasury.gov/
    """
    response = requests.get(
        f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve&field_tdr_date_value={target_date.year}"
    )
    response.raise_for_status()

    yield_curve = {}
    root = ET.fromstring(response.content)
    sdmx_namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    }
    for entry in root.findall("atom:entry", sdmx_namespaces):
        obs_date = entry.find("atom:content/m:properties/d:NEW_DATE", sdmx_namespaces)
        if obs_date is not None and obs_date.text.startswith(target_date.isoformat()):
            props = entry.find("atom:content/m:properties", sdmx_namespaces)
            for child in props:
                tag = child.tag.split("}")[1]  # Remove namespace
                if tag.startswith("BC_"):
                    term = tag.replace("BC_", "")
                    try:
                        yield_curve[term] = float(child.text)
                    except (TypeError, ValueError):
                        continue
            break

    return yield_curve


def _get_treasury_yield_from_dep_treasury(
    target_date: date, ticker: str
) -> Optional[float]:
    """Infer UST yield from Treasury department yield curve."""
    mapping = {
        "UST1M": "1MONTH",
        "UST2M": "2MONTH",
        "UST3M": "3MONTH",
        "UST6M": "6MONTH",
        "UST1Y": "1YEAR",
        "UST2Y": "2YEAR",
        "UST3Y": "3YEAR",
        "UST5Y": "5YEAR",
        "UST7Y": "7YEAR",
        "UST10Y": "10YEAR",
        "UST20Y": "20YEAR",
    }
    if ticker not in mapping.keys():
        return
    curve = _get_treasury_yield_curve_from_dep_treasury(target_date)
    if not curve:
        return
    return curve.get(mapping[ticker])


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_webstat_rates(target_date: date, ticker: str) -> Optional[float]:
    """Get Webstat data.

    Source: https://webstat.banque-france.fr/en/
    """
    response = requests.get(
        f"https://webstat.banque-france.fr/export/csv/fr/catalog/{ticker}"
    )
    response.raise_for_status()

    csv_data = StringIO(response.text)
    prices = pd.read_csv(csv_data, sep=";")
    closing_price_series = prices[
        pd.to_datetime(prices["time_period"]).dt.date == target_date
    ].reset_index()
    if not closing_price_series.empty:
        closing_price_str = closing_price_series.loc[0, "obs_value"]
        return _parse_str_decimals_to_float(closing_price_str)


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_bund_yield_from_bundesbank(target_date: date, ticker: str) -> Optional[float]:
    """Extract Bunds yield from Bundesbank database.

    Source: https://www.bundesbank.de/en/statistics/time-series-databases/
    """
    response = requests.get(
        f"https://api.statistiken.bundesbank.de/rest/download/BBSSY/{ticker}?format=sdmx&lang=en"
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    sdmx_namespaces = {
        "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic"
    }
    for obs in root.findall(".//generic:Obs", sdmx_namespaces):
        obs_date = obs.find("generic:ObsDimension", sdmx_namespaces)
        obs_value = obs.find("generic:ObsValue", sdmx_namespaces)
        if (
            obs_date is not None
            and obs_date.attrib.get("value") == target_date.isoformat()
        ):
            if obs_value is not None:
                return float(obs_value.attrib["value"])


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_mutan_rate_from_boj(target_date: date) -> Optional[float]:
    """Scrap BoJ website to get Mutan Rate.

    Source: https://www.boj.or.jp/statistics/market/short/mutan/index.htm
    """
    DATA_TYPE = {"prevision": "mp", "certified": "md"}
    file_name = f"{DATA_TYPE['certified']}{target_date.strftime('%Y%m%d')}.xlsx"
    response = requests.get(
        f"https://www.boj.or.jp/statistics/market/short/mutan/d_release/{DATA_TYPE['certified']}/{target_date.year}/{file_name}"
    )
    if response.status_code != 200:
        if response.status_code != 404:
            response.raise_for_status()
        else:
            file_name = f"{DATA_TYPE['prevision']}{target_date.strftime('%Y%m%d')}.xlsx"
            response = requests.get(
                f"https://www.boj.or.jp/statistics/market/short/mutan/d_release/{DATA_TYPE['prevision']}/{file_name}"
            )
            response.raise_for_status()

    df = pd.read_excel(response.content)
    matches = df.applymap(lambda x: "Average" in str(x))
    match_locations = [(i, j) for i, j in zip(*matches.to_numpy().nonzero())]
    if len(match_locations) > 1:
        raise Http404("BoJ file has likely changed. Review of code is needed.")

    mutan_location_row = match_locations[0][0]
    mutan_location_column = match_locations[0][1] + 1
    mutan_rate = df.iloc[mutan_location_row, mutan_location_column]
    if not pd.isna(df.iloc[mutan_location_row, mutan_location_column]):
        return float(mutan_rate)


@ttl_cache(maxsize=128, ttl=10 * 60)
def _scrap_jgb_yield_curve_from_bb(target_date: date) -> dict:
    """Scrap entire UST yield curves from Treasury department.

    Source: https://www.bb.jbts.co.jp/en/historical/main_rate.html
    """
    response = requests.get("https://www.bb.jbts.co.jp/en/historical/main_rate.html")
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")

    rows = []
    for tr in soup.select("table.tbCore tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        # Must have a date (YYYY/MM/DD)
        if cols and len(cols[0].split("/")) == 3:
            rows.append(cols)

    # Define maturities (according to header order)
    maturities = [
        "40Y",
        "30Y",
        "20Y",
        "10Y",
        "5Y",
        "2Y",
        "TDB(1Y)",
        "TDB(6M)",
        "TDB(3M)",
    ]

    df = pd.DataFrame(rows, columns=["Date"] + maturities)
    df["Date"] = pd.to_datetime(df["Date"], format="%Y/%m/%d")

    for col in maturities:
        df[col] = pd.to_numeric(df[col].replace("", None), errors="coerce")

    df_cleaned = df.sort_values("Date").ffill()
    target_yield_curves_df = df_cleaned[df_cleaned["Date"].dt.date == target_date]
    if target_yield_curves_df.empty or target_yield_curves_df.shape[0] > 1:
        return
    return target_yield_curves_df.iloc[0].to_dict()


def _get_jgb_yield_from_bb(target_date: date, ticker: str):
    """Infer JGB yield from BB yield curve."""
    mapping = {
        "TDB3M": "TDB(3M)",
        "TDB6M": "TDB(6M)",
        "TDB1Y": "TDB(1Y)",
        "JGB2Y": "2Y",
        "JGB5Y": "5Y",
        "JGB10Y": "10Y",
        "JGB20Y": "20Y",
    }
    if ticker not in mapping.keys():
        return
    curve = _scrap_jgb_yield_curve_from_bb(target_date)
    if not curve:
        return
    return curve.get(mapping[ticker])


def get_market_data(target_date: date) -> List[MarketData]:
    """Get market data."""
    market_data = []
    for asset_info in ASSETS_BASE_INFO:
        data = deepcopy(asset_info)
        scrapping_function = SOURCE_SCRAP_MAP.get(data["source"])
        data["date"] = target_date
        data["price"] = (
            scrapping_function(target_date, data["ticker"])
            if scrapping_function
            else None
        )

    return market_data


def get_specific_asset_market_data(
    short_name: str,
    start_date: date,
    end_date: date,
) -> List[MarketData]:
    """Get specific asset market data."""
    targeted_market_data = next(
        d for d in ASSETS_BASE_INFO if d["short_name"] == short_name
    )

    delta_days = (end_date - start_date).days
    date_range = [start_date + timedelta(days=i) for i in range(delta_days + 1)]

    scrapping_function = SOURCE_SCRAP_MAP.get(targeted_market_data["source"])
    market_data = []
    for date in date_range:
        data = deepcopy(targeted_market_data)
        data["date"] = date
        data["price"] = scrapping_function(date, data["ticker"])
        market_data.append(data)

    return market_data


def get_all_asset_prices_for_date(price_date: date) -> List[MarketPriceModel]:
    """Get market prices for a specific date."""
    market_data_queryset = MarketPriceModel.objects.filter(date=price_date)
    return shared_services.convert_query_to_dictionary_list(
        queryset=market_data_queryset
    )


def calculate_price_change(
    reference_market_prices: List[MarketData],
    comparison_market_prices: List[MarketData],
) -> pd.DataFrame:
    """Calculate price change between two dates."""
    reference_df = pd.DataFrame(reference_market_prices)
    comparison_df = pd.DataFrame(comparison_market_prices)
    price_diff = pd.merge(
        reference_df,
        comparison_df,
        on="short_name",
        how="left",
        suffixes=("", "_previous"),
    )

    # Calculate price changes
    price_diff["price_change"] = price_diff["price"] - price_diff["price_previous"]
    price_diff["price_change_pct"] = (
        price_diff["price"] / price_diff["price_previous"] - 1
    ) * 100

    # Adjusting price changes for Interest Rate classes
    rates_row = price_diff["asset_class"].isin(
        [AssetClassChoices.RATES, AssetClassChoices.CB_RATES]
    )
    price_diff.loc[rates_row, "price_change"] *= 100
    price_diff.loc[rates_row, "price_change_pct"] = None

    return price_diff.replace({float("nan"): None})


def get_price_change(
    reference_market_prices: List[MarketData],
    comparison_market_prices: List[MarketData],
) -> List[PriceChange]:
    """Select only required information from price change Dataframe."""
    price_diff = calculate_price_change(
        reference_market_prices, comparison_market_prices
    )
    return [PriceChange(**row) for row in price_diff.to_dict("records")]


def get_asset_names(filters: Dict[str, str]) -> List[AssetNames]:
    """Get all assets based on unique short_name and full_name pair."""
    market_data = (
        MarketPriceModel.objects.filter(**filters)
        .values("short_name", "full_name")
        .distinct()
    )

    market_data_map = {
        d["short_name"]: AssetNames(
            short_name=d["short_name"], full_name=d["full_name"]
        )
        for d in market_data
    }

    # Preserve order from reference JSON
    return [
        market_data_map[a["short_name"]]
        for a in ASSETS_BASE_INFO
        if a["short_name"] in market_data_map
    ]


def check_asset_existence(asset_name: str) -> bool:
    """Check asset existence in database."""
    return (
        asset_name
        in MarketPriceModel.objects.values_list("short_name", flat=True).distinct()
    )


def get_historical_prices(
    short_name: str, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> List[HistoricalPrice]:
    """Get historical prices of an asset."""
    market_data_queryset = MarketPriceModel.objects.filter(short_name=short_name)

    if start_date:
        market_data_queryset = market_data_queryset.filter(date__gte=start_date)
    if end_date:
        market_data_queryset = market_data_queryset.filter(date__lte=end_date)

    query_result = shared_services.convert_query_to_dictionary_list(
        queryset=market_data_queryset
    )

    historical_prices = [
        HistoricalPrice(
            price_date=asset["date"],
            price=asset["price"],
        )
        for asset in query_result
    ]

    return sorted(historical_prices, key=lambda x: x["price_date"])


def get_yield_curve(
    target_date: date,
    location: LocationChoices,
    asset_type: AssetTypeChoices = AssetTypeChoices.GOVERNMENT_BOND_RATE,
) -> List[YieldCurvePoint]:
    """Get yield curve for a specific date and location."""
    market_data_queryset = MarketPriceModel.objects.filter(
        date=target_date, location=location, asset_type=asset_type
    )
    query_result = shared_services.convert_query_to_dictionary_list(
        queryset=market_data_queryset
    )
    yield_curve = [
        YieldCurvePoint(
            short_name=asset["short_name"],
            maturity=asset["maturity"],
            price=asset["price"],
        )
        for asset in query_result
        if asset["asset_class"] == AssetClassChoices.RATES
    ]
    return sorted(yield_curve, key=lambda x: (x["maturity"] is None, x["maturity"]))
