import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from typing import List, Optional, TypedDict

import environ
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from cachetools.func import ttl_cache
from dateutil.relativedelta import relativedelta

import core.services as core_services
from core.services import logger
from market_overview.models import (
    AssetModel,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
)

env = environ.Env()


SOURCE_SCRAP_MAP = {
    PriceSourceChoices.GOV_TREASURY_DEPT: lambda d, t: _get_treasury_yield_from_dep_treasury(
        d, t
    ),
    PriceSourceChoices.FRED: lambda d, t: _get_fed_funds_rate_from_fred(d, t),
    PriceSourceChoices.NYFED: lambda d, _: _get_sofr_from_nyfed(d),
    PriceSourceChoices.WEBSTAT: lambda d, t: _get_webstat_rates(d, t),
    PriceSourceChoices.BUNDESBANK: lambda d, t: _get_bund_yield_from_bundesbank(d, t),
    PriceSourceChoices.BOJ: lambda d, _: _get_mutan_rate_from_boj(d),
    PriceSourceChoices.BB: lambda d, t: _get_jgb_yield_from_bb(d, t),
    PriceSourceChoices.GLOBAL_RATES: lambda d, t: _scrap_euribor_from_global_rates(
        d, t
    ),
    PriceSourceChoices.YAHOO: lambda d, t: _get_yahoo_finance_closing_prices(d, t),
}


class ScrappingResult(TypedDict):
    """Scrapping result dictionnary."""

    price: Optional[float]
    comment: Optional[str]


class MarketData(TypedDict):
    """Market data dictionnary."""

    asset: AssetModel
    price: Optional[float]
    date: date
    comment: Optional[str]


def _parse_str_decimals_to_float(a: str) -> Optional[float]:
    """Parse French and English string decimals to float."""
    return float(str(a).replace(",", ".")) if pd.notna(a) else None


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_yahoo_finance_closing_prices(
    target_date: date, ticker: str
) -> ScrappingResult:
    """Get closing prices from Yahoo Finance.

    Using publicly available yahoo scrapper module yfiance.
    """
    prices = yf.Ticker(str(ticker)).history(period="5d").reset_index()
    if prices.empty:
        return ScrappingResult(price=None, comment="Yahoo Finance: No prices found.")
    closing_price = prices[prices["Date"].dt.date == target_date].reset_index()
    if not closing_price.empty:
        return ScrappingResult(
            price=float(str(closing_price.loc[0, "Close"])), comment=""
        )
    return ScrappingResult(price=None, comment="Yahoo Finance: No prices found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _scrap_euribor_from_global_rates(target_date: date, ticker: str) -> ScrappingResult:
    """Scrap euribor rates from GlobalRates.

    Source: https://www.global-rates.com/en/
    """
    response = requests.get(
        f"https://www.global-rates.com/en/interest-rates/euribor/{ticker}"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Euribor rates: {response.text}")
        return ScrappingResult(price=None, comment=response.text)
    soup = BeautifulSoup(response.content, "html.parser")  # type: ignore[reportArgumentType]

    table = soup.find("table")
    if not table:
        return ScrappingResult(
            price=None, comment="Could not find Euribor rates table on page"
        )

    for tr in table.find_all("tr"):  # type: ignore[reportAttributeAccessIssue]
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
                    return ScrappingResult(price=float(rate_str), comment="")
                except ValueError:
                    return ScrappingResult(
                        price=None, comment="Could not parse Euribor rate"
                    )
    return ScrappingResult(price=None, comment="Euribor rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_fed_funds_rate_from_fred(target_date: date, ticker: str) -> ScrappingResult:
    """Get Fedfund rate from FRED via API

    Source: https://fred.stlouisfed.org/series/FEDFUNDS
    """
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    obs_start = target_date - relativedelta(months=2)
    FRED_API_KEY = env("FRED_API_KEY")
    query_params = f"series_id={ticker}&api_key={FRED_API_KEY}&file_type=json&observation_start={obs_start}&sort_order=desc"
    response = requests.get(f"{BASE_URL}?{query_params}")
    if response.status_code >= 400:
        logger.warning(f"Error scraping Fedfund rates: {response.text}")
        return ScrappingResult(price=None, comment=response.text)
    result = json.loads(response.content)
    observations = result.get("observations", [])
    if observations and (value := observations[0].get("value")):
        return ScrappingResult(price=float(value), comment="")
    return ScrappingResult(price=None, comment="Fedfund rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_sofr_from_nyfed(target_date: date) -> ScrappingResult:
    """
    Scrap SOFR rate from NY Fed XML.

    Source: https://www.newyorkfed.org/markets/reference-rates/sofr
    """
    response = requests.get(
        "https://markets.newyorkfed.org/read?productCode=50&eventCodes=520&limit=25&startPosition=0&sort=postDt:-1&format=xml"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping SOFR rates: {response.text}")
        return ScrappingResult(price=None, comment=response.text)

    root = ET.fromstring(response.content)
    for rate in root.findall(".//rate"):
        effective_date = rate.find("effectiveDate").text  # type: ignore[reportOptionalMemberAccess]
        if effective_date == target_date.isoformat():
            percent_rate = rate.find("percentRate").text  # type: ignore[reportOptionalMemberAccess]
            if percent_rate:
                return ScrappingResult(price=float(percent_rate), comment="")
    return ScrappingResult(price=None, comment="SOFR rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_treasury_yield_curve_from_dep_treasury(target_date: date) -> dict:
    """
    Scrap entire UST yield curves from Treasury department.

    Source: https://home.treasury.gov/
    """
    response = requests.get(
        f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve&field_tdr_date_value={target_date.year}"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Treasury yield curve: {response.text}")
        return {"error": response.text}

    yield_curve = {}
    root = ET.fromstring(response.content)
    sdmx_namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    }
    for entry in root.findall("atom:entry", sdmx_namespaces):
        obs_date = entry.find("atom:content/m:properties/d:NEW_DATE", sdmx_namespaces)
        if obs_date is not None and obs_date.text.startswith(target_date.isoformat()):  # type: ignore[reportOptionalMemberAccess]
            props = entry.find("atom:content/m:properties", sdmx_namespaces)
            for child in props:  # type: ignore[reportOptionalIterable]
                tag = child.tag.split("}")[1]  # Remove namespace
                if tag.startswith("BC_"):
                    term = tag.replace("BC_", "")
                    try:
                        yield_curve[term] = float(child.text)  # type: ignore[ArgumentType]
                    except (TypeError, ValueError):
                        continue
            break

    return yield_curve


def _get_treasury_yield_from_dep_treasury(
    target_date: date, ticker: str
) -> ScrappingResult:
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
        return ScrappingResult(price=None, comment="Ticker not found in mapping.")
    curve = _get_treasury_yield_curve_from_dep_treasury(target_date)
    if not curve:
        return ScrappingResult(price=None, comment="Yield curve not found.")
    if curve.get("error"):
        return ScrappingResult(price=None, comment=curve.get("error"))
    return ScrappingResult(price=curve.get(mapping[ticker]), comment="")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_webstat_rates(target_date: date, ticker: str) -> ScrappingResult:
    """Get Webstat data.

    Source: https://webstat.banque-france.fr/en/
    """
    response = requests.get(
        f"https://webstat.banque-france.fr/export/csv/fr/catalog/{ticker}"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Webstat rates: {response.text}")
        return ScrappingResult(price=None, comment=response.text)

    csv_data = StringIO(response.text)
    prices = pd.read_csv(csv_data, sep=";")
    closing_price_series = prices[
        pd.to_datetime(prices["time_period"]).dt.date == target_date
    ].reset_index()
    if not closing_price_series.empty:
        closing_price_str = closing_price_series.loc[0, "obs_value"]
        return ScrappingResult(
            price=_parse_str_decimals_to_float(str(closing_price_str)), comment=""
        )
    return ScrappingResult(price=None, comment="Webstat rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_bund_yield_from_bundesbank(target_date: date, ticker: str) -> ScrappingResult:
    """Extract Bunds yield from Bundesbank database.

    Source: https://www.bundesbank.de/en/statistics/time-series-databases/
    """
    response = requests.get(
        f"https://api.statistiken.bundesbank.de/rest/download/BBSSY/{ticker}?format=sdmx&lang=en"
    )
    if response.status_code >= 400:
        logger.warning(f"Error scraping Bundesbank rates: {response.text}")
        return ScrappingResult(price=None, comment=response.text)
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
                return ScrappingResult(
                    price=float(obs_value.attrib["value"]), comment=""
                )
    return ScrappingResult(price=None, comment="Bunds rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _get_mutan_rate_from_boj(target_date: date) -> ScrappingResult:
    """Scrap BoJ website to get Mutan Rate.

    Source: https://www.boj.or.jp/statistics/market/short/mutan/index.htm
    """
    DATA_TYPE = {"prevision": "mp", "certified": "md"}
    file_name = f"{DATA_TYPE['certified']}{target_date.strftime('%Y%m%d')}.xlsx"
    response = requests.get(
        f"https://www.boj.or.jp/statistics/market/short/mutan/d_release/{DATA_TYPE['certified']}/{target_date.year}/{file_name}"
    )
    if response.status_code != 200:
        file_name = f"{DATA_TYPE['prevision']}{target_date.strftime('%Y%m%d')}.xlsx"
        response = requests.get(
            f"https://www.boj.or.jp/statistics/market/short/mutan/d_release/{DATA_TYPE['prevision']}/{file_name}"
        )
        if response.status_code >= 400:
            logger.warning(f"Error scraping BoJ rates: {response.text}")
            return ScrappingResult(price=None, comment=response.text)

    df = pd.read_excel(BytesIO(response.content))
    matches = df.applymap(lambda x: "Average" in str(x))  # type: ignore[CallIssue]
    match_locations = [(i, j) for i, j in zip(*matches.to_numpy().nonzero())]
    if len(match_locations) > 1:
        return ScrappingResult(
            price=None, comment="BoJ file has likely changed. Review of code is needed."
        )

    mutan_location_row = match_locations[0][0]
    mutan_location_column = match_locations[0][1] + 1
    mutan_rate = df.iloc[mutan_location_row, mutan_location_column]
    if not pd.isna(df.iloc[mutan_location_row, mutan_location_column]):
        return ScrappingResult(price=float(str(mutan_rate)), comment="")
    return ScrappingResult(price=None, comment="Mutan rate not found.")


@ttl_cache(maxsize=128, ttl=10 * 60)
def _scrap_jgb_yield_curve_from_bb(target_date: date) -> dict:
    """Scrap entire UST yield curves from Treasury department.

    Source: https://www.bb.jbts.co.jp/en/index.html
    """
    response = requests.get("https://www.bb.jbts.co.jp/en/historical/main_rate.html")
    if response.status_code >= 400:
        logger.warning(f"Error scraping JGB yield curve: {response.text}")
        return {"error": response.text}
    soup = BeautifulSoup(response.content, "html.parser")  # type: ignore[reportArgumentType]

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
        return {"error": "Yield curve not found."}
    return target_yield_curves_df.iloc[0].to_dict()


def _get_jgb_yield_from_bb(target_date: date, ticker: str) -> ScrappingResult:
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
        return ScrappingResult(price=None, comment="Ticker not found in mapping.")
    curve = _scrap_jgb_yield_curve_from_bb(target_date)
    if not curve:
        return ScrappingResult(price=None, comment="Yield curve not found.")
    if curve.get("error"):
        return ScrappingResult(price=None, comment=curve.get("error"))
    return ScrappingResult(price=curve.get(mapping[ticker]), comment="")


def _get_market_data(
    asset: AssetModel,
    target_date: date,
) -> MarketData:
    """Get price from scrapping function."""
    scrapping_function = SOURCE_SCRAP_MAP.get(asset.source)
    scrapping_result: ScrappingResult = (
        scrapping_function(target_date, asset.ticker)
        if scrapping_function
        else ScrappingResult(price=None, comment="No scrapping function found.")
    )
    if not scrapping_result.get("price"):
        logger.warning("No price found.")
    return MarketData(
        asset=asset,
        price=scrapping_result.get("price"),
        date=target_date,
        comment=scrapping_result.get("comment"),
    )


def get_market_data(target_date: date) -> List[MarketData]:
    """Get market data."""
    market_data = []
    for asset in AssetModel.objects.all():
        logger.info(f"Scrapping asset: {asset.short_name}")
        market_data.append(_get_market_data(asset, target_date))
    return market_data


def get_specific_asset_market_data(
    short_name: str,
    start_date: date,
    end_date: date,
) -> List[MarketData]:
    """Get specific asset market data."""
    asset = AssetModel.objects.get(short_name=short_name)
    delta_days = (end_date - start_date).days
    date_range = [start_date + timedelta(days=i) for i in range(delta_days + 1)]
    market_data = []
    for target_date in date_range:
        logger.info(f"Scrapping asset: {asset.short_name} for date: {target_date}")
        market_data.append(_get_market_data(asset, target_date))
    return market_data


def ingest_market_data(
    market_data: List[MarketData],
) -> List[MarketData]:
    """Ingest market data."""
    asset_not_updated = []
    for data in market_data:
        if not data["price"]:
            asset_not_updated.append(data)
        core_services.upsert_with_logs(
            model=MarketPriceModel,
            log_model=PriceUpdateLogModel,
            lookup_kwargs={"date": data["date"], "asset": data["asset"]},
            updates={
                "logs": f"Automated price update on {data['asset'].short_name} to price: {data['price']}.",
                "price": data["price"],
                "comment": data["comment"],
            },
        )
    return asset_not_updated
