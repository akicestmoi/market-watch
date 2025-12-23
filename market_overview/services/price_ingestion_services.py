import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from typing import List, Optional, TypedDict

import environ
import pandas as pd
import requests
import yfinance as yf
from cachetools.func import ttl_cache
from pandas.tseries.offsets import BDay

import core.services as core_services
from core.services import CACHE_MAXSIZE, CACHE_TTL_SECONDS, fetch_html, logger
from market_overview.models import (
    AssetModel,
    HolidayModel,
    LocationChoices,
    MarketPriceModel,
    PriceSourceChoices,
    PriceUpdateLogModel,
    SpecialComment,
)
from market_overview.services import market_data_services

env = environ.Env()

GLOBAL_RATES_URL = "https://www.global-rates.com/en/interest-rates"
NY_FED_RATE_URL = "https://markets.newyorkfed.org/read?productCode=50&limit=25&startPosition=0&sort=postDt:-1&format=xml"
DEPT_TREASURY_RATE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve"
WEBSTAT_RATE_URL = "https://webstat.banque-france.fr/export/csv/fr/catalog"
BUNDESBANK_RATE_URL = "https://api.statistiken.bundesbank.de/rest/download/BBSSY"
BOJ_MUTAN_RATE_URL = "https://www.boj.or.jp/statistics/market/short/mutan/d_release"
BB_YIELD_CURVE_URL = "https://www.bb.jbts.co.jp/en/historical/main_rate.html"


SOURCE_SCRAP_MAP = {
    PriceSourceChoices.GOV_TREASURY_DEPT: lambda d, t: _get_treasury_yield_from_dep_treasury(
        d, t
    ),
    PriceSourceChoices.NYFED: lambda d, t: _scrap_rate_from_nyfed_xml(d, t),
    PriceSourceChoices.WEBSTAT: lambda d, t: get_webstat_rates(d, t),
    PriceSourceChoices.BUNDESBANK: lambda d, t: _get_bund_yield_from_bundesbank(d, t),
    PriceSourceChoices.BOJ: lambda d, _: _get_mutan_rate_from_boj(d),
    PriceSourceChoices.BB: lambda d, t: _get_jgb_yield_from_bb(d, t),
    PriceSourceChoices.GLOBAL_RATES: lambda d, t: scrap_from_global_rates(d, t),
    PriceSourceChoices.YAHOO: lambda d, t: get_yahoo_finance_closing_prices(d, t),
}


class ScrapingResult(TypedDict):
    """Scraping result dictionnary."""

    price: Optional[float]
    comment: Optional[str]


class MarketData(TypedDict):
    """Market data dictionnary."""

    asset: AssetModel
    price: Optional[float]
    date: date
    comment: Optional[str]


class BatchPriceIngestionItem(TypedDict):
    """Batch price ingestion item dictionnary."""

    short_name: str
    start_date: date
    end_date: Optional[date]


class BatchPriceIngestionResult(TypedDict):
    """Batch price ingestion result dictionnary."""

    short_name: str
    status: str
    error: Optional[str]
    asset_not_updated: Optional[List[str]]


def _parse_str_decimals_to_float(a: str) -> Optional[float]:
    """Parse French and English string decimals to float."""
    return float(str(a).replace(",", ".")) if pd.notna(a) else None


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_yahoo_finance_closing_prices(target_date: date, ticker: str) -> ScrapingResult:
    """Get closing prices from Yahoo Finance.

    Using publicly available yahoo scraper module yfiance.
    """
    prices = yf.Ticker(str(ticker)).history(period="1mo").reset_index()
    if prices.empty:
        return ScrapingResult(price=None, comment="Yahoo Finance: No prices found.")
    closing_price = prices[prices["Date"].dt.date == target_date].reset_index()
    if not closing_price.empty:
        return ScrapingResult(
            price=float(str(closing_price.loc[0, "Close"])), comment=""
        )
    return ScrapingResult(price=None, comment="Yahoo Finance: No prices found.")


def _parse_euribor_rate_from_table(
    table, target_date: Optional[date]
) -> ScrapingResult:
    """Parse EURIBOR rate from table for a specific date."""
    if target_date is None:
        return ScrapingResult(
            price=None, comment="Target date is required for EURIBOR rates"
        )

    for tr in table.find_all("tr"):  # type: ignore[reportAttributeAccessIssue]
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue

        raw_date = cells[0].get_text(strip=True)
        raw_rate = cells[1].get_text(strip=True)

        try:
            parsed_date = datetime.strptime(raw_date, "%m-%d-%Y").date()
        except ValueError:
            logger.debug(f"Could not parse date format: {raw_date}")
            continue

        if parsed_date == target_date:
            rate_str = raw_rate.replace("%", "").replace(",", ".").strip()
            try:
                return ScrapingResult(price=float(rate_str), comment="")
            except ValueError:
                return ScrapingResult(
                    price=None,
                    comment=f"Could not parse Euribor rate: {raw_rate}",
                )
    return ScrapingResult(price=None, comment="Euribor rate not found.")


def _parse_central_bank_rate_from_table(table) -> ScrapingResult:
    """Parse central bank rate from table (first row, second column)."""
    tbody = table.find("tbody")
    if not tbody:
        return ScrapingResult(price=None, comment="Table has no <tbody>")

    first_row = tbody.find("tr")
    if not first_row:
        return ScrapingResult(price=None, comment="Table contains no rows")

    cells = first_row.find_all("td")
    if len(cells) < 2:
        return ScrapingResult(price=None, comment="Row has insufficient columns")

    rate_text = cells[1].get_text(strip=True)
    if not rate_text:
        return ScrapingResult(price=None, comment="Rate cell is empty")

    match = re.search(r"([-+]?\d+(?:\.\d+)?)", rate_text)
    if not match:
        return ScrapingResult(
            price=None, comment=f"Could not extract rate from: {rate_text}"
        )

    try:
        return ScrapingResult(price=float(match.group(1)), comment="")
    except ValueError:
        return ScrapingResult(
            price=None, comment=f"Could not convert rate to float: {match.group(1)}"
        )


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def scrap_from_global_rates(target_date: Optional[date], ticker: str) -> ScrapingResult:
    """Scrap rates from GlobalRates.

    Source: https://www.global-rates.com/en/
    """
    soup = fetch_html(f"{GLOBAL_RATES_URL}/{ticker}")
    if not soup:
        return ScrapingResult(
            price=None, comment=f"Failed to fetch HTML from {GLOBAL_RATES_URL}"
        )

    table = soup.find("table")
    if not table:
        return ScrapingResult(
            price=None, comment="Could not find interest rates table on page"
        )

    rate_type = ticker.split("/")[0] if "/" in ticker else ticker
    match rate_type:
        case "euribor":
            result = _parse_euribor_rate_from_table(table, target_date)
        case "central-banks":
            result = _parse_central_bank_rate_from_table(table)
        case _:
            result = ScrapingResult(
                price=None, comment=f"Unsupported rate type: {rate_type}"
            )
    return result


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _scrap_rate_from_nyfed_xml(target_date: date, ticker: str) -> ScrapingResult:
    """Scrap rate from NY Fed XML.

    Source: https://www.newyorkfed.org/markets/reference-rates/
    """
    response = requests.get(f"{NY_FED_RATE_URL}&eventCodes={ticker}")
    if response.status_code >= 400:
        logger.warning(f"Error scraping rates from NY Fed XML: {response.text}")
        return ScrapingResult(price=None, comment=response.text)

    root = ET.fromstring(response.content)
    for rate in root.findall(".//rate"):
        effective_date = rate.find("effectiveDate").text  # type: ignore[reportOptionalMemberAccess]
        if effective_date == target_date.isoformat():
            percent_rate = rate.find("percentRate").text  # type: ignore[reportOptionalMemberAccess]
            if percent_rate:
                return ScrapingResult(price=float(percent_rate), comment="")
    return ScrapingResult(price=None, comment="Rate not found.")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_treasury_yield_curve_from_dep_treasury(target_date: date) -> dict:
    """
    Scrap entire UST yield curves from Treasury department.

    Source: https://home.treasury.gov/
    """
    response = requests.get(
        f"{DEPT_TREASURY_RATE_URL}&field_tdr_date_value={target_date.year}"
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
) -> ScrapingResult:
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
        return ScrapingResult(price=None, comment="Ticker not found in mapping.")
    curve = _get_treasury_yield_curve_from_dep_treasury(target_date)
    if not curve:
        return ScrapingResult(price=None, comment="Yield curve not found.")
    if curve.get("error"):
        return ScrapingResult(price=None, comment=curve.get("error"))
    return ScrapingResult(price=curve.get(mapping[ticker]), comment="")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def get_webstat_rates(target_date: date, ticker: str) -> ScrapingResult:
    """Get Webstat data.

    Source: https://webstat.banque-france.fr/en/
    """
    response = requests.get(f"{WEBSTAT_RATE_URL}/{ticker}")
    if response.status_code >= 400:
        logger.warning(f"Error scraping Webstat rates: {response.text}")
        return ScrapingResult(price=None, comment=response.text)

    csv_data = StringIO(response.text)
    prices = pd.read_csv(csv_data, sep=";")
    closing_price_series = prices[
        pd.to_datetime(prices["time_period"]).dt.date == target_date
    ].reset_index()
    if not closing_price_series.empty:
        closing_price_str = closing_price_series.loc[0, "obs_value"]
        try:
            return ScrapingResult(
                price=_parse_str_decimals_to_float(str(closing_price_str)), comment=""
            )
        except ValueError:
            return ScrapingResult(
                price=None,
                comment=f"Could not convert rate to float: {closing_price_str}",
            )
    return ScrapingResult(price=None, comment="Webstat rate not found.")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_bund_yield_from_bundesbank(target_date: date, ticker: str) -> ScrapingResult:
    """Extract Bunds yield from Bundesbank database.

    Source: https://www.bundesbank.de/en/statistics/time-series-databases/
    """
    response = requests.get(f"{BUNDESBANK_RATE_URL}/{ticker}?format=sdmx&lang=en")
    if response.status_code >= 400:
        logger.warning(f"Error scraping Bundesbank rates: {response.text}")
        return ScrapingResult(price=None, comment=response.text)
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
                return ScrapingResult(
                    price=float(obs_value.attrib["value"]), comment=""
                )
    return ScrapingResult(price=None, comment="Bunds rate not found.")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _get_mutan_rate_from_boj(target_date: date) -> ScrapingResult:
    """Scrap BoJ website to get Mutan Rate.

    Source: https://www.boj.or.jp/statistics/market/short/mutan/index.htm
    """
    DATA_TYPE = {"prevision": "mp", "certified": "md"}
    file_name = f"{DATA_TYPE['certified']}{target_date.strftime('%Y%m%d')}.xlsx"
    response = requests.get(
        f"{BOJ_MUTAN_RATE_URL}/{DATA_TYPE['certified']}/{target_date.year}/{file_name}"
    )
    if response.status_code != 200:
        file_name = f"{DATA_TYPE['prevision']}{target_date.strftime('%Y%m%d')}.xlsx"
        response = requests.get(
            f"{BOJ_MUTAN_RATE_URL}/{DATA_TYPE['prevision']}/{file_name}"
        )
        if response.status_code >= 400:
            logger.warning(f"Error scraping BoJ rates: {response.text}")
            return ScrapingResult(price=None, comment=response.text)

    df = pd.read_excel(BytesIO(response.content))
    matches = df.map(lambda x: "Average" in str(x))
    match_locations = [(i, j) for i, j in zip(*matches.to_numpy().nonzero())]
    if len(match_locations) > 1:
        return ScrapingResult(
            price=None, comment="BoJ file has likely changed. Review of code is needed."
        )

    mutan_location_row = match_locations[0][0]
    mutan_location_column = match_locations[0][1] + 1
    mutan_rate = df.iloc[mutan_location_row, mutan_location_column]
    if not pd.isna(df.iloc[mutan_location_row, mutan_location_column]):
        return ScrapingResult(price=float(str(mutan_rate)), comment="")
    return ScrapingResult(price=None, comment="Mutan rate not found.")


@ttl_cache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_SECONDS)
def _scrap_jgb_yield_curve_from_bb(target_date: date) -> dict:
    """Scrap entire UST yield curves from Treasury department.

    Source: https://www.bb.jbts.co.jp/en/index.html
    """
    soup = fetch_html(BB_YIELD_CURVE_URL)
    if not soup:
        return {"error": f"Failed to fetch HTML from {BB_YIELD_CURVE_URL}"}

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


def _get_jgb_yield_from_bb(target_date: date, ticker: str) -> ScrapingResult:
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
        return ScrapingResult(price=None, comment="Ticker not found in mapping.")
    curve = _scrap_jgb_yield_curve_from_bb(target_date)
    if not curve:
        return ScrapingResult(price=None, comment="Yield curve not found.")
    if curve.get("error"):
        return ScrapingResult(price=None, comment=curve.get("error"))
    return ScrapingResult(price=curve.get(mapping[ticker]), comment="")


def _is_holiday_at_location(target_date: date, location: LocationChoices) -> bool:
    """Check if target date is a holiday at a given location."""
    return HolidayModel.objects.filter(date=target_date, location=location).exists()


def _get_market_data(
    asset: AssetModel,
    target_date: date,
) -> MarketData:
    """Get price from scraping function."""
    if _is_holiday_at_location(target_date, asset.location):
        logger.info(
            f"No price found for {asset.short_name} on {target_date} as it is a bank holiday."
        )
        return MarketData(
            asset=asset,
            price=None,
            date=target_date,
            comment=SpecialComment.BANK_HOLIDAY,
        )
    scraping_function = SOURCE_SCRAP_MAP.get(asset.source)
    try:
        scraping_result: ScrapingResult = (
            scraping_function(target_date, asset.ticker)
            if scraping_function
            else ScrapingResult(price=None, comment="No scraping function found.")
        )
        if not scraping_result.get("price"):
            logger.warning("No price found.")
    except Exception as e:
        scraping_result = ScrapingResult(
            price=None, comment=f"Error getting market data: {str(e)}"
        )
    return MarketData(
        asset=asset,
        price=scraping_result.get("price"),
        date=target_date,
        comment=scraping_result.get("comment"),
    )


def get_market_data(target_date: date) -> List[MarketData]:
    """Get market data."""
    market_data = []
    for asset in AssetModel.objects.all():
        logger.info(f"Scraping asset: {asset.short_name}")
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
                "logs": f"Automated price update on {data['asset'].short_name}.",
                "price": data["price"],
                "comment": data["comment"],
            },
            logging_on_fields=["price"],
            none_skip_fields=["price"],
        )
    return asset_not_updated


def _get_specific_asset_market_data(
    short_name: str,
    start_date: date,
    end_date: date,
) -> List[MarketData]:
    """Get specific asset market data."""
    asset = AssetModel.objects.get(short_name=short_name)
    delta_days = (end_date - start_date).days
    date_range = [
        start_date + timedelta(days=i)
        for i in range(delta_days + 1)
        if (start_date + timedelta(days=i)).weekday() < 5
    ]
    market_data = []
    for target_date in date_range:
        logger.info(f"Scraping asset: {asset.short_name} for date: {target_date}")
        market_data.append(_get_market_data(asset, target_date))
    return market_data


def _ingest_specific_asset_market_prices(
    short_name: str,
    start_date: date,
    end_date: Optional[date] = None,
) -> BatchPriceIngestionResult:
    """Ingest market prices for a specific asset over a date range."""
    target_end_date = end_date if end_date else (date.today() - BDay(1)).date()
    if not market_data_services.check_asset_existence(short_name):
        return BatchPriceIngestionResult(
            short_name=short_name,
            status="error",
            error=f"Asset: {short_name} does not exist in database.",
            asset_not_updated=None,
        )

    market_data = _get_specific_asset_market_data(
        short_name, start_date, target_end_date
    )
    asset_not_updated = ingest_market_data(market_data)

    return BatchPriceIngestionResult(
        short_name=short_name,
        status="success",
        error=None,
        asset_not_updated=[data["date"].isoformat() for data in asset_not_updated],
    )


def batch_ingest_specific_asset_market_prices(
    batch_ingestion_items: List[BatchPriceIngestionItem],
) -> List[BatchPriceIngestionResult]:
    """Batch ingest market prices for multiple assets."""
    results = []
    for item in batch_ingestion_items:
        result = _ingest_specific_asset_market_prices(
            item["short_name"], item["start_date"], item.get("end_date")
        )
        results.append(result)

    return results
