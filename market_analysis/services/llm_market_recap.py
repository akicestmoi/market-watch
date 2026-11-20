"""LLM article analysis and daily market recap."""

import json
import logging
import math
from datetime import date, datetime, timedelta
from typing import NamedTuple, TypedDict

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q
from pydantic_ai import Agent

from central_banks_overview.models import CentralBankChoices
from central_banks_overview.services.central_banks_data import (
    get_decision_day_key_rates,
    list_central_banks_with_meetings_at_date,
)
from core.services.calendar import (
    convert_to_display_timezone,
    get_previous_business_day,
)
from core.services.time_series_calculation import (
    ValueChangeType,
    calculate_value_change,
)
from data_visualization.services.central_banks_recap import (
    get_formatted_probability_matrix_changes,
    get_formatted_probability_matrix_for_central_bank,
    list_central_bank_recap_figures,
)
from data_visualization.services.config import FX_MATRIX_ORDER
from data_visualization.services.economic_recap.table_content import (
    format_indicator_value,
    get_shared_amount_magnitude,
)
from data_visualization.services.market_recap import FxMatrixEntry, get_fx_prices_matrix
from economic_overview.models.common import (
    EconomicDataLocationChoices,
    IndicatorBaseUnitChoices,
)
from economic_overview.models.economic_indicators import (
    EconomicDataCategoryChoices,
    EconomicDataModel,
    EconomicDataSubcategoryChoices,
    EconomicIndicatorInformationModel,
    EconomicPublicationFrequencyChoices,
    IndicatorDisplayModeChoices,
)
from economic_overview.models.publication import PublicationScheduleModel
from economic_overview.services.economic_data import (
    TimedEconomicDataValue,
    change_triplet_values_for_mode,
    get_number_of_months_to_calculate_mode_change,
)
from market_analysis.llm.config import (
    MAX_ARTICLE_CHARS,
    PROMPT_VERSION,
    format_skills_as_prompt_block,
    is_llm_configured,
    load_instruction,
    wrap_untrusted_content_safely,
)
from market_analysis.llm.schemas import (
    ArticleAnalysisOutput,
    DailyRecapOutput,
    EventType,
    Sentiment,
)
from market_analysis.models import ArticleRegionChoices, DailyRecapModel
from market_analysis.services.article_extraction import (
    ArticleData,
    ArticleExtractionResult,
)
from market_analysis.services.cache import get_cached_analysis, set_cached_analysis
from market_overview.models.market_prices import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    MarketPriceModel,
    PriceSourceChoices,
)

logger = logging.getLogger(__name__)

MAX_MARKET_CONTEXT_DAYS = 40
MARKET_CONTEXT_IGNORE_MARKERS = ["EURIBOR"]
CENTRAL_BANKS_FOR_CONTEXT = (
    CentralBankChoices.FRB,
    CentralBankChoices.ECB,
    CentralBankChoices.BOJ,
)


def get_latest_recap(
    reporting_date: date | None = None,
) -> DailyRecapModel | None:
    """Return the latest daily recap, optionally filtered to 'reporting_date'."""
    daily_recaps = DailyRecapModel.objects.all()
    if reporting_date:
        daily_recaps = daily_recaps.filter(reporting_date=reporting_date)
    return daily_recaps.order_by("-reporting_date", "-date_added").first()


class MarketContextEntry(TypedDict):
    """Market context for one asset in LLM prompts."""

    short_name: str
    ticker: str | None
    asset_class: AssetClassChoices
    date: str  # ISO date string for the LLM/JSON boundary
    price: float
    source: PriceSourceChoices
    previous_date: str | None  # ISO date string for the LLM/JSON boundary
    previous_price: float | None
    change_dod: float | None
    change_dod_pct: float | None
    change_dod_bps: float | None
    change_dod_pts: float | None
    change_wow_pct: float | None
    change_wow_bps: float | None
    change_wow_pts: float | None
    change_mom_pct: float | None
    change_mom_bps: float | None
    change_mom_pts: float | None


def _get_closest_as_of_price(
    market_prices: list[MarketPriceModel], as_of: date
) -> MarketPriceModel | None:
    """Return the newest price on or before 'as_of' (series newest-first)."""
    for market_price in market_prices:
        if market_price.date <= as_of:
            return market_price
    return None


def _should_skip_asset_for_market_context(short_name: str | None) -> bool:
    """Return whether an asset short name is excluded from market LLM context."""
    short_name_upper = (short_name or "").upper()
    return any(marker in short_name_upper for marker in MARKET_CONTEXT_IGNORE_MARKERS)


def _list_asset_market_prices_in_window(
    asset: AssetModel,
    window_start: date,
    as_of: date,
) -> list[MarketPriceModel]:
    """List verified prices for one asset in the market-context lookback window."""
    return list(
        MarketPriceModel.objects.filter(
            asset=asset,
            date__gte=window_start,
            date__lte=as_of,
            price__isnull=False,
        ).order_by("-date")
    )


class _MarketContextPeriodChanges(NamedTuple):
    """DoD / WoW / MoM change metrics for one market-context price entry."""

    dod_absolute: float | None
    dod_percent: float | None
    dod_bps: float | None
    wow_absolute: float | None
    wow_percent: float | None
    wow_bps: float | None
    mom_absolute: float | None
    mom_percent: float | None
    mom_bps: float | None


def _calculate_market_context_period_changes(
    as_of_price: float,
    previous_price: float | None,
    wow_price: float | None,
    mom_price: float | None,
) -> _MarketContextPeriodChanges:
    """Compute DoD / WoW / MoM changes for one as-of market price."""
    return _MarketContextPeriodChanges(
        dod_absolute=calculate_value_change(
            as_of_price, previous_price, ValueChangeType.ABSOLUTE
        ),
        dod_percent=calculate_value_change(
            as_of_price, previous_price, ValueChangeType.PERCENT
        ),
        dod_bps=calculate_value_change(
            as_of_price, previous_price, ValueChangeType.BPS
        ),
        wow_absolute=calculate_value_change(
            as_of_price, wow_price, ValueChangeType.ABSOLUTE
        ),
        wow_percent=calculate_value_change(
            as_of_price, wow_price, ValueChangeType.PERCENT
        ),
        wow_bps=calculate_value_change(as_of_price, wow_price, ValueChangeType.BPS),
        mom_absolute=calculate_value_change(
            as_of_price, mom_price, ValueChangeType.ABSOLUTE
        ),
        mom_percent=calculate_value_change(
            as_of_price, mom_price, ValueChangeType.PERCENT
        ),
        mom_bps=calculate_value_change(as_of_price, mom_price, ValueChangeType.BPS),
    )


def _build_market_context_entry_for_asset(
    asset: AssetModel,
    market_prices: list[MarketPriceModel],
    wow_target: date,
    mom_target: date,
) -> MarketContextEntry:
    """Build one market-context entry with DoD / WoW / MoM changes for an asset."""
    # The series is newest-first by date, so index 0 is the as-of price.
    as_of_price = market_prices[0]
    # The series is newest-first, so index 1 is the prior session for DoD.
    previous_price_entry = market_prices[1] if len(market_prices) > 1 else None
    wow_price_entry = _get_closest_as_of_price(market_prices, wow_target)
    mom_price_entry = _get_closest_as_of_price(market_prices, mom_target)
    previous_price = previous_price_entry.price if previous_price_entry else None
    wow_price = wow_price_entry.price if wow_price_entry else None
    mom_price = mom_price_entry.price if mom_price_entry else None
    period_changes = _calculate_market_context_period_changes(
        as_of_price.price, previous_price, wow_price, mom_price
    )
    is_rates = asset.asset_class == AssetClassChoices.RATES
    is_vol = asset.asset_type == AssetTypeChoices.VOLATILITY_INDEX
    return MarketContextEntry(
        short_name=asset.short_name,
        ticker=asset.ticker,
        asset_class=AssetClassChoices(asset.asset_class),
        date=as_of_price.date.isoformat(),
        price=as_of_price.price,
        source=PriceSourceChoices(asset.source),
        previous_date=(
            previous_price_entry.date.isoformat() if previous_price_entry else None
        ),
        previous_price=previous_price,
        change_dod=period_changes.dod_absolute,
        change_dod_pct=(None if is_rates or is_vol else period_changes.dod_percent),
        change_dod_bps=period_changes.dod_bps if is_rates else None,
        change_dod_pts=period_changes.dod_absolute if is_vol else None,
        change_wow_pct=(None if is_rates or is_vol else period_changes.wow_percent),
        change_wow_bps=period_changes.wow_bps if is_rates else None,
        change_wow_pts=period_changes.wow_absolute if is_vol else None,
        change_mom_pct=(None if is_rates or is_vol else period_changes.mom_percent),
        change_mom_bps=period_changes.mom_bps if is_rates else None,
        change_mom_pts=period_changes.mom_absolute if is_vol else None,
    )


def build_market_context(as_of: date) -> list[MarketContextEntry]:
    """Verified prices with DoD / WoW / MoM changes for the agent prompt."""
    window_start = as_of - timedelta(days=MAX_MARKET_CONTEXT_DAYS)
    wow_target = as_of - timedelta(days=7)
    mom_target = as_of - timedelta(days=30)
    market_context: list[MarketContextEntry] = []
    assets = AssetModel.objects.all().order_by("asset_class", "short_name")
    for asset in assets:
        if _should_skip_asset_for_market_context(asset.short_name):
            continue
        market_prices = _list_asset_market_prices_in_window(asset, window_start, as_of)
        if not market_prices:
            continue
        market_context.append(
            _build_market_context_entry_for_asset(
                asset, market_prices, wow_target, mom_target
            )
        )
    return market_context


class _EconomicContextModeValues(TypedDict):
    """One display-mode triplet for an economic indicator in LLM context."""

    mode: str  # IndicatorDisplayModeChoices value (Raw / MoM / QoQ / QoQy / YoY / …)
    mode_label: str  # Same as 'mode' (kept for prompt compatibility)
    is_default: bool  # True for the indicator's seeded main/default mode
    current_value: float | None
    previous_value: float | None
    change_value: float | None
    display_current_value: str
    display_previous_value: str
    display_change_value: str


class EconomicContextEntry(TypedDict):
    """Economic indicator context for LLM prompts.

    'values_by_mode' carries Raw / QoQ / QoQy / YoY so article figures can be
    matched to the correct convention. 'default_mode' / 'is_default' mark the
    indicator's main mode from 'EconomicIndicatorInformationModel.default_mode'
    (seeded from 'economic_data.json').
    """

    name: str
    location: EconomicDataLocationChoices
    category: EconomicDataCategoryChoices
    subcategory: EconomicDataSubcategoryChoices
    frequency: EconomicPublicationFrequencyChoices
    period: str | None  # ISO date string for the LLM/JSON boundary
    period_display: str | None  # Display period label for the LLM
    # Main mode from the indicator model / economic_data.json seed.
    default_mode: str  # IndicatorDisplayModeChoices value
    default_mode_label: str  # Same as 'default_mode' (kept for prompt compatibility)
    base_unit: str
    base_currency: str
    # Raw stored values (before display-mode change).
    raw_current_value: float | None
    raw_previous_value: float | None
    values_by_mode: list[_EconomicContextModeValues]
    comment: str | None
    publication_date: str | None  # ISO datetime/date string for the LLM/JSON boundary
    kind: str


def _get_publication_datetime_on_date(
    publication_schedule: PublicationScheduleModel, as_of: date
) -> datetime | None:
    """Return the publication datetime that falls on 'as_of', if any.

    Prefers 'current' when both current and previous land on the same date.
    After ingest, the just-released value is often on 'previous' only.
    Compare in Europe/Paris so the calendar day matches market recap.
    """
    for publication_date in (
        publication_schedule.current_publication_date,
        publication_schedule.previous_publication_date,
    ):
        if publication_date is None:
            continue
        if convert_to_display_timezone(publication_date).date() == as_of:
            return publication_date
    return None


def _get_required_indicator_base_unit_for_display(
    indicator: EconomicIndicatorInformationModel,
) -> str:
    """Return the indicator base unit, or raise when it is missing."""
    base_unit = indicator.base_unit
    if not base_unit:
        raise ValueError(
            f"base_unit is missing for indicator {indicator.full_name!r} "
            f"(ticker={indicator.ticker!r})."
        )
    return base_unit


def _get_indicator_base_currency_for_display(
    indicator: EconomicIndicatorInformationModel,
    *,
    base_unit: str,
) -> str:
    """Return base currency when required for amount display; else empty string."""
    if base_unit not in {
        IndicatorBaseUnitChoices.K,
        IndicatorBaseUnitChoices.M,
        IndicatorBaseUnitChoices.B,
    }:
        return indicator.base_currency or ""
    base_currency = indicator.base_currency
    if not base_currency:
        raise ValueError(
            f"base_currency is required for amount unit {base_unit!r} on "
            f"indicator {indicator.full_name!r} (ticker={indicator.ticker!r})."
        )
    return base_currency


def _get_economic_context_mode_values(
    economic_data_time_series: list[TimedEconomicDataValue],
    *,
    frequency: EconomicPublicationFrequencyChoices,
    mode: IndicatorDisplayModeChoices,
    is_default: bool,
    base_unit: str,
    base_currency: str,
) -> _EconomicContextModeValues:
    """Build current / previous / change for one indicator display mode."""
    indicator_value_triplet = change_triplet_values_for_mode(
        economic_data_time_series,
        frequency=frequency,
        mode=mode,
    )
    shared_amount_magnitude = (
        get_shared_amount_magnitude(
            current=indicator_value_triplet.current,
            previous=indicator_value_triplet.previous,
            change=indicator_value_triplet.change,
            base_unit=base_unit,
        )
        if mode == IndicatorDisplayModeChoices.RAW
        else None
    )
    return _EconomicContextModeValues(
        mode=mode.value,
        mode_label=mode.value,
        is_default=is_default,
        current_value=indicator_value_triplet.current,
        previous_value=indicator_value_triplet.previous,
        change_value=indicator_value_triplet.change,
        display_current_value=format_indicator_value(
            indicator_value_triplet.current,
            base_unit=base_unit,
            base_currency=base_currency,
            mode=mode,
            amount_magnitude=shared_amount_magnitude,
        ),
        display_previous_value=format_indicator_value(
            indicator_value_triplet.previous,
            base_unit=base_unit,
            base_currency=base_currency,
            mode=mode,
            amount_magnitude=shared_amount_magnitude,
        ),
        display_change_value=format_indicator_value(
            indicator_value_triplet.change,
            base_unit=base_unit,
            base_currency=base_currency,
            mode=mode,
            amount_magnitude=shared_amount_magnitude,
        ),
    )


def _list_publication_schedules_on_date(as_of: date) -> list[PublicationScheduleModel]:
    """List publication schedules whose release falls on 'as_of'."""
    return list(
        PublicationScheduleModel.objects.filter(indicator__is_hidden=False)
        .filter(
            Q(current_publication_date__date=as_of)
            | Q(previous_publication_date__date=as_of)
        )
        .select_related("indicator")
        .order_by("indicator__location", "indicator__full_name")
    )


# Usage of tuple: fixed (time series values, latest ORM instance or None) pair.
def _fetch_stored_economic_data_time_series_for_indicator(
    indicator: EconomicIndicatorInformationModel,
    indicator_frequency: EconomicPublicationFrequencyChoices,
) -> tuple[list[TimedEconomicDataValue], EconomicDataModel | None]:
    """Load newest-first stored economic data for indicator display-mode math."""
    latest_time_series_value = (
        EconomicDataModel.objects.filter(
            indicator=indicator,
            data_value__isnull=False,
            period__isnull=False,
        )
        .order_by("-period", "-last_modified")
        .first()
    )
    if (
        latest_time_series_value is not None
        and latest_time_series_value.period is not None
    ):
        history_fetch_months = max(
            get_number_of_months_to_calculate_mode_change(indicator_frequency, mode)
            for mode in IndicatorDisplayModeChoices
        )
        history_start_period = latest_time_series_value.period - relativedelta(
            months=history_fetch_months
        )
        stored_economic_data_time_series = list(
            EconomicDataModel.objects.filter(
                indicator=indicator,
                data_value__isnull=False,
                period__gte=history_start_period,
            ).order_by("-period", "-last_modified")
        )
    else:
        stored_economic_data_time_series = []
    # The series is newest-first by period, so index 0 is the latest value.
    if stored_economic_data_time_series:
        latest_time_series_value = stored_economic_data_time_series[0]
    economic_data_time_series = [
        TimedEconomicDataValue(
            period=time_series_value.period,
            value=float(time_series_value.data_value),
        )
        for time_series_value in stored_economic_data_time_series
        if time_series_value.period is not None
        and time_series_value.data_value is not None
    ]
    return economic_data_time_series, latest_time_series_value


def _format_economic_context_entry_from_indicator(
    indicator: EconomicIndicatorInformationModel,
    *,
    indicator_frequency: EconomicPublicationFrequencyChoices,
    indicator_default_display_mode: IndicatorDisplayModeChoices,
    matched_publication_date: datetime,
    latest_time_series_value: EconomicDataModel | None,
    raw_current_value: float | None,
    raw_previous_value: float | None,
    values_by_mode: list[_EconomicContextModeValues],
    base_unit: str,
    base_currency: str,
) -> EconomicContextEntry:
    """Format one economic-context entry from indicator metadata and mode values."""
    return EconomicContextEntry(
        name=indicator.full_name,
        location=EconomicDataLocationChoices(indicator.location),
        category=EconomicDataCategoryChoices(indicator.category),
        subcategory=EconomicDataSubcategoryChoices(indicator.subcategory),
        frequency=indicator_frequency,
        period=(
            latest_time_series_value.period.isoformat()
            if latest_time_series_value and latest_time_series_value.period
            else None
        ),
        period_display=(
            latest_time_series_value.get_period_display()
            if latest_time_series_value
            else None
        ),
        default_mode=indicator_default_display_mode.value,
        default_mode_label=indicator_default_display_mode.value,
        base_unit=base_unit,
        base_currency=base_currency,
        raw_current_value=raw_current_value,
        raw_previous_value=raw_previous_value,
        values_by_mode=values_by_mode,
        comment=(
            latest_time_series_value.comment if latest_time_series_value else None
        ),
        publication_date=matched_publication_date.isoformat(),
        kind="scheduled_release",
    )


def _build_economic_context_entry_for_schedule(
    publication_schedule: PublicationScheduleModel,
    as_of: date,
) -> EconomicContextEntry | None:
    """Build one economic-context entry when the schedule matches 'as_of'."""
    matched_publication_date = _get_publication_datetime_on_date(
        publication_schedule, as_of
    )
    if matched_publication_date is None:
        return None
    indicator = publication_schedule.indicator
    indicator_default_display_mode = IndicatorDisplayModeChoices(indicator.default_mode)
    indicator_frequency = EconomicPublicationFrequencyChoices(indicator.frequency)
    economic_data_time_series, latest_time_series_value = (
        _fetch_stored_economic_data_time_series_for_indicator(
            indicator, indicator_frequency
        )
    )
    # The value list stays newest-first, so index 0 is the latest raw level.
    raw_current_value = (
        economic_data_time_series[0].value if economic_data_time_series else None
    )
    # The series is newest-first, so index 1 is the prior raw level.
    raw_previous_value = (
        economic_data_time_series[1].value
        if len(economic_data_time_series) > 1
        else None
    )
    base_unit = _get_required_indicator_base_unit_for_display(indicator)
    base_currency = _get_indicator_base_currency_for_display(
        indicator, base_unit=base_unit
    )
    values_by_mode = [
        _get_economic_context_mode_values(
            economic_data_time_series,
            frequency=indicator_frequency,
            mode=mode,
            is_default=mode == indicator_default_display_mode,
            base_unit=base_unit,
            base_currency=base_currency,
        )
        for mode in IndicatorDisplayModeChoices
    ]
    return _format_economic_context_entry_from_indicator(
        indicator,
        indicator_frequency=indicator_frequency,
        indicator_default_display_mode=indicator_default_display_mode,
        matched_publication_date=matched_publication_date,
        latest_time_series_value=latest_time_series_value,
        raw_current_value=raw_current_value,
        raw_previous_value=raw_previous_value,
        values_by_mode=values_by_mode,
        base_unit=base_unit,
        base_currency=base_currency,
    )


def build_economic_context(as_of: date) -> list[EconomicContextEntry]:
    """Economic indicators scheduled for publication on 'as_of'.

    Matches 'current' or 'previous' publication date (post-ingest roll).
    Includes every display mode so article figures can be matched correctly.
    """
    economic_context_entries: list[EconomicContextEntry] = []
    for publication_schedule in _list_publication_schedules_on_date(as_of):
        economic_context_entry = _build_economic_context_entry_for_schedule(
            publication_schedule, as_of
        )
        if economic_context_entry is not None:
            economic_context_entries.append(economic_context_entry)
    return economic_context_entries


class _CentralBankFigure(TypedDict):
    """One central-bank key figure as shown on the Central Banks page."""

    label: str  # Display label from the Central Banks UI
    value: str  # Display value from the Central Banks UI


class _CentralBankDecisionRate(TypedDict):
    """Key policy rate on a monetary-policy decision day."""

    name: str
    current_value: float | None
    previous_value: float | None
    change_value: float | None
    display_current_value: str
    display_previous_value: str
    display_change_value: str


class CentralBankContextEntry(TypedDict):
    """Central-bank key figures block for LLM prompts (one bank)."""

    central_bank: CentralBankChoices
    reference_date: str  # ISO date string for the LLM/JSON boundary
    is_decision_day: bool
    decision_rates: list[_CentralBankDecisionRate]
    figures: list[_CentralBankFigure]


def _format_decision_rate_change(change_value: float | None) -> str:
    """Format a signed policy-rate change with a percent unit label."""
    if change_value is None:
        return ""
    formatted_magnitude = format_indicator_value(
        abs(change_value),
        base_unit=IndicatorBaseUnitChoices.PERCENT,
        include_unit_label=True,
        digits=2,
    )
    if change_value > 0:
        return f"+{formatted_magnitude}"
    if change_value < 0:
        return f"-{formatted_magnitude}"
    return formatted_magnitude


def build_central_bank_context(as_of: date) -> list[CentralBankContextEntry]:
    """Key CB figures plus decision-day key rates when a meeting falls on 'as_of'."""
    central_banks_with_meeting = set(list_central_banks_with_meetings_at_date(as_of))
    # Usage of dict: keys are central banks; values are that bank's decision-day rates.
    decision_rates_by_central_bank: dict[
        CentralBankChoices, list[_CentralBankDecisionRate]
    ] = {}
    for decision_day_key_rate in get_decision_day_key_rates(as_of):
        central_bank = decision_day_key_rate["central_bank"]
        decision_rates_by_central_bank.setdefault(central_bank, []).append(
            _CentralBankDecisionRate(
                name=decision_day_key_rate["full_name"],
                current_value=decision_day_key_rate["current_value"],
                previous_value=decision_day_key_rate["previous_value"],
                change_value=decision_day_key_rate["change_value"],
                display_current_value=format_indicator_value(
                    decision_day_key_rate["current_value"],
                    base_unit=IndicatorBaseUnitChoices.PERCENT,
                    include_unit_label=True,
                    digits=2,
                ),
                display_previous_value=format_indicator_value(
                    decision_day_key_rate["previous_value"],
                    base_unit=IndicatorBaseUnitChoices.PERCENT,
                    include_unit_label=True,
                    digits=2,
                ),
                display_change_value=_format_decision_rate_change(
                    decision_day_key_rate["change_value"]
                ),
            )
        )

    central_bank_context_entries: list[CentralBankContextEntry] = []
    for central_bank in CENTRAL_BANKS_FOR_CONTEXT:
        figures = [
            _CentralBankFigure(label=item["label"], value=item["value"])
            for item in list_central_bank_recap_figures(central_bank, as_of)
        ]
        central_bank_context_entries.append(
            CentralBankContextEntry(
                central_bank=central_bank,
                reference_date=as_of.isoformat(),
                is_decision_day=central_bank in central_banks_with_meeting,
                decision_rates=decision_rates_by_central_bank.get(central_bank, []),
                figures=figures,
            )
        )
    return central_bank_context_entries


def _format_meeting_dates_for_context(
    meeting_dates: list[date | datetime],
) -> list[str]:
    """Serialize meeting dates as ISO date strings for LLM JSON context."""
    formatted: list[str] = []
    for meeting_date in meeting_dates:
        if isinstance(meeting_date, datetime):
            formatted.append(meeting_date.date().isoformat())
        else:
            formatted.append(meeting_date.isoformat())
    return formatted


class _FxCurrencyStrength(TypedDict):
    """Quadratic-mean (RMS) pairwise FX DoD % move for one currency vs the basket.

    Always non-negative: opposing peer moves do not cancel the way a signed
    arithmetic mean would. Direction still comes from the pairwise matrix.
    """

    currency: str
    rms_change_pct: float


class FxHeatmapContext(TypedDict):
    """FX heatmap (pairwise DoD %) plus per-currency RMS strength magnitude."""

    as_of: str
    previous_date: str
    currencies: list[str]
    matrix: list[FxMatrixEntry]
    currency_strength: list[_FxCurrencyStrength]


def _compute_fx_currency_strength(
    matrix: list[FxMatrixEntry],
) -> list[_FxCurrencyStrength]:
    """Quadratic mean (RMS) of off-diagonal pairwise % changes per base currency.

    'rms = sqrt(sum(x_i^2) / n)' so mixed-sign peer moves do not cancel.
    """
    strength_entries: list[_FxCurrencyStrength] = []
    for matrix_entry in matrix:
        base_currency = matrix_entry["currency"]
        pairwise_changes: list[float] = []
        for quote_currency in FX_MATRIX_ORDER:
            if quote_currency == base_currency:
                continue
            pairwise_changes.append(matrix_entry[quote_currency])
        if not pairwise_changes:
            rms_change_pct = 0.0
        else:
            squared_sum = sum(change**2 for change in pairwise_changes)
            rms_change_pct = math.sqrt(squared_sum / len(pairwise_changes))
        strength_entries.append(
            _FxCurrencyStrength(
                currency=base_currency,
                rms_change_pct=round(rms_change_pct, 4),
            )
        )
    return strength_entries


def get_fx_heatmap_context(as_of: date) -> FxHeatmapContext:
    """FX heatmap DoD % matrix and RMS currency-move magnitude for LLM prompts."""
    previous_date = get_previous_business_day(as_of)
    matrix = get_fx_prices_matrix(as_of, previous_date)
    return FxHeatmapContext(
        as_of=as_of.isoformat(),
        previous_date=previous_date.isoformat(),
        currencies=list(FX_MATRIX_ORDER),
        matrix=matrix,
        currency_strength=_compute_fx_currency_strength(matrix),
    )


class _ProbabilityStepEntry(TypedDict):
    """One rate-step of probabilities or probability changes."""

    expected_rate_step: int
    probabilities: list[float]


class ProbabilityMatrixShiftContextEntry(TypedDict):
    """Current policy-path probabilities and DoD shifts for one central bank."""

    central_bank: CentralBankChoices
    as_of: str
    previous_date: str
    meeting_dates: list[str]
    current_probabilities: list[_ProbabilityStepEntry]
    probability_changes: list[_ProbabilityStepEntry]


def _build_one_central_bank_probability_matrix_shift_for_context(
    central_bank: CentralBankChoices,
    as_of: date,
    previous_date: date,
) -> ProbabilityMatrixShiftContextEntry | None:
    """Build one probability-matrix context block for a central bank."""
    try:
        current_matrix = get_formatted_probability_matrix_for_central_bank(
            central_bank, as_of
        )
        previous_matrix = get_formatted_probability_matrix_for_central_bank(
            central_bank, previous_date
        )
        change_matrix = get_formatted_probability_matrix_changes(
            current_matrix,
            previous_matrix,
            previous_date=previous_date,
        )
    except Exception as error:
        logger.warning(
            "Skipping probability-matrix context for %s on %s: %s",
            central_bank,
            as_of.isoformat(),
            error,
        )
        return None

    if current_matrix is None:
        return None

    meeting_dates = _format_meeting_dates_for_context(current_matrix["meeting_dates"])
    current_probabilities = [
        _ProbabilityStepEntry(
            expected_rate_step=entry["expected_rate_step"],
            probabilities=list(entry["probabilities"]),
        )
        for entry in current_matrix["probability_matrix"]
    ]
    probability_changes = [
        _ProbabilityStepEntry(
            expected_rate_step=entry["expected_rate_step"],
            probabilities=list(entry["probabilities"]),
        )
        for entry in (
            change_matrix["probability_matrix"] if change_matrix is not None else []
        )
    ]
    return ProbabilityMatrixShiftContextEntry(
        central_bank=central_bank,
        as_of=as_of.isoformat(),
        previous_date=previous_date.isoformat(),
        meeting_dates=meeting_dates,
        current_probabilities=current_probabilities,
        probability_changes=probability_changes,
    )


def build_probability_matrix_shift_context(
    as_of: date,
) -> list[ProbabilityMatrixShiftContextEntry]:
    """FRB / ECB / BOJ probability matrices and DoD shifts for LLM prompts."""
    previous_date = get_previous_business_day(as_of)
    probability_matrix_shift_entries: list[ProbabilityMatrixShiftContextEntry] = []
    for central_bank in CENTRAL_BANKS_FOR_CONTEXT:
        shift_entry = _build_one_central_bank_probability_matrix_shift_for_context(
            central_bank, as_of, previous_date
        )
        if shift_entry is not None:
            probability_matrix_shift_entries.append(shift_entry)
    return probability_matrix_shift_entries


class EvidenceEntry(TypedDict):
    """One cited claim used as evidence in a market-recap answer."""

    claim: str
    source_url: str
    quote_or_paraphrase: str
    is_interpretation: bool


class AnalyzedArticle(TypedDict):
    """Structured article analysis (process memory only; not stored in the DB)."""

    title: str
    summary: str
    event_types: list[EventType]
    companies: list[str]
    sectors: list[str]
    sentiment: Sentiment
    key_facts: list[str]
    uncertainties: list[str]
    source_url: str
    source_name: str
    regions: list[ArticleRegionChoices]


class RecapSourceUrl(TypedDict):
    """Article source kept on the Daily Market Recap for the UI."""

    url: str
    regions: list[ArticleRegionChoices]
    label: str


def _get_analyzed_article_from_cache_hit(
    article: ArticleData,
    cached_analysis: AnalyzedArticle,
) -> AnalyzedArticle:
    """Merge cached analysis with fresh catalog metadata from the article record."""
    # Refresh catalog metadata on cache hits (region/label may change).
    return AnalyzedArticle(
        title=cached_analysis["title"],
        summary=cached_analysis["summary"],
        event_types=list(cached_analysis["event_types"]),
        companies=list(cached_analysis["companies"]),
        sectors=list(cached_analysis["sectors"]),
        sentiment=cached_analysis["sentiment"],
        key_facts=list(cached_analysis["key_facts"]),
        uncertainties=list(cached_analysis["uncertainties"]),
        source_url=cached_analysis["source_url"],
        source_name=article["source_name"],
        regions=list(article["regions"]),
    )


def _trim_article_content_for_analysis(content: str) -> str:
    """Truncate article body when it exceeds the LLM article analysis cap."""
    if len(content) > MAX_ARTICLE_CHARS:
        return content[: MAX_ARTICLE_CHARS - 20] + "\n…[truncated]"
    return content


def _build_article_analysis_prompt(article: ArticleData, content: str) -> str:
    """Assemble the article-analysis prompt with skills and untrusted content."""
    return (
        f"{format_skills_as_prompt_block()}\n\n"
        f"Article URL: {article['url']}\n"
        f"Title: {article['title']}\n"
        f"Source: {article['source_name']} ({article['source_key']})\n"
        f"Regions: {', '.join(article['regions'])}\n\n"
        f"{wrap_untrusted_content_safely(content)}\n\n"
        "Return structured analysis in English. Use company/sector names as "
        "written in the article (do not invent tickers). Never invent URLs."
    )


def _run_llm_article_analysis_agent(
    article: ArticleData,
    prompt: str,
    reporting_date: date,
    use_cache: bool,
) -> AnalyzedArticle:
    """Call the LLM agent for one article and optionally store the digest cache."""
    logger.info(
        "LLM article analysis starting for %s (%s)",
        article.get("source_key"),
        article["url"],
    )
    agent = Agent(
        settings.LLM_MODEL_NAME,
        output_type=ArticleAnalysisOutput,
        instructions=load_instruction("analysis_system.md"),
    )
    result = agent.run_sync(prompt)
    output: ArticleAnalysisOutput = result.output
    analyzed = AnalyzedArticle(
        title=output.title[:500],
        summary=output.summary,
        event_types=list(output.event_types),
        companies=output.companies,
        sectors=output.sectors,
        sentiment=output.sentiment,
        key_facts=output.key_facts,
        uncertainties=output.uncertainties,
        source_url=article["url"][:1000],
        source_name=article["source_name"],
        regions=list(article["regions"]),
    )
    if use_cache and article["url"]:
        set_cached_analysis(reporting_date, analyzed, source_url=article["url"])
    logger.info(
        "LLM article analysis finished for %s (%s)",
        article.get("source_key"),
        article["url"],
    )
    return analyzed


def _analyze_extracted_article(
    article: ArticleData,
    reporting_date: date,
    use_cache: bool = True,
) -> AnalyzedArticle:
    """Analyze one extracted article; optionally reuse the Redis digest cache."""
    if not is_llm_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    if use_cache and article["url"]:
        cached = get_cached_analysis(reporting_date, article["url"])
        if cached:
            logger.info("Article analysis cache hit for %s", article["url"])
            return _get_analyzed_article_from_cache_hit(article, cached["analysis"])

    content = _trim_article_content_for_analysis(article["content"] or "")
    prompt = _build_article_analysis_prompt(article, content)

    try:
        return _run_llm_article_analysis_agent(
            article, prompt, reporting_date, use_cache
        )
    except Exception as exc:
        logger.error("Article analysis failed for %s: %s", article["url"], exc)
        raise


class ArticleAnalysisFailure(TypedDict):
    """Failed article analysis with the source URL and error message."""

    url: str
    error: str


class _ArticleBatchAnalysisResult(TypedDict):
    """Batch outcome of analyzing extracted articles for one reporting date."""

    analyses: list[AnalyzedArticle]
    analyzed_count: int
    failed: list[ArticleAnalysisFailure]
    cache_hits: int
    cache_misses: int


class _SingleArticleBatchOutcome(NamedTuple):
    """Outcome of analyzing one article inside a batch run."""

    analyzed: AnalyzedArticle | None
    failure: ArticleAnalysisFailure | None
    cache_hit: bool
    cache_miss: bool


def _analyze_single_article_in_batch(
    article: ArticleData,
    reporting_date: date,
    use_cache: bool,
    index: int,
    total: int,
) -> _SingleArticleBatchOutcome:
    """Analyze one article in a batch, counting cache hits and failures."""
    logger.info(
        "Article analysis %s/%s: %s",
        index,
        total,
        article.get("url") or article.get("source_key"),
    )
    try:
        if use_cache and article["url"]:
            cached = get_cached_analysis(reporting_date, article["url"])
            if cached:
                logger.info("Article analysis cache hit (%s/%s)", index, total)
                return _SingleArticleBatchOutcome(
                    analyzed=cached["analysis"],
                    failure=None,
                    cache_hit=True,
                    cache_miss=False,
                )
        return _SingleArticleBatchOutcome(
            analyzed=_analyze_extracted_article(
                article,
                reporting_date=reporting_date,
                use_cache=use_cache,
            ),
            failure=None,
            cache_hit=False,
            cache_miss=True,
        )
    except Exception as exc:
        logger.warning(
            "Article analysis %s/%s failed: %s",
            index,
            total,
            exc,
        )
        return _SingleArticleBatchOutcome(
            analyzed=None,
            failure=ArticleAnalysisFailure(url=article["url"], error=str(exc)),
            cache_hit=False,
            cache_miss=False,
        )


def analyze_extracted_articles(
    articles: list[ArticleData],
    reporting_date: date,
    use_cache: bool = True,
) -> _ArticleBatchAnalysisResult:
    """Analyze extracted articles in source order."""
    analyzed: list[AnalyzedArticle] = []
    failed: list[ArticleAnalysisFailure] = []
    cache_hits = 0
    cache_misses = 0
    total = len(articles)

    logger.info(
        "Analyzing %s article(s) for %s (use_cache=%s)",
        total,
        reporting_date.isoformat(),
        use_cache,
    )
    for index, article in enumerate(articles, start=1):
        outcome = _analyze_single_article_in_batch(
            article, reporting_date, use_cache, index, total
        )
        if outcome.analyzed is not None:
            analyzed.append(outcome.analyzed)
        if outcome.failure is not None:
            failed.append(outcome.failure)
        if outcome.cache_hit:
            cache_hits += 1
        if outcome.cache_miss:
            cache_misses += 1

    logger.info(
        "Article batch analysis complete for %s: analyzed=%s failed=%s "
        "cache_hits=%s cache_misses=%s",
        reporting_date.isoformat(),
        len(analyzed),
        len(failed),
        cache_hits,
        cache_misses,
    )
    return _ArticleBatchAnalysisResult(
        analyses=analyzed,
        analyzed_count=len(analyzed),
        failed=failed,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


class _ExtractionGap(TypedDict):
    """Source that yielded no article during extraction."""

    source_id: str
    name: str
    comment: str | None


class _PipelineIssues(TypedDict):
    """Extraction/analysis gaps summarized for the recap prompt."""

    extraction_gaps: list[_ExtractionGap]
    analysis_failures: list[ArticleAnalysisFailure]
    has_issues: bool


def _build_pipeline_issues(
    extraction_sources: list[ArticleExtractionResult] | None,
    analysis_failures: list[ArticleAnalysisFailure] | None,
) -> _PipelineIssues:
    """Summarize missing extractions and failed analyses for the recap prompt."""
    extraction_gaps = [
        _ExtractionGap(
            source_id=source["source_id"],
            name=source["name"],
            comment=source.get("comment"),
        )
        for source in (extraction_sources or [])
        if not source.get("articles")
    ]
    failures = list(analysis_failures or [])
    return _PipelineIssues(
        extraction_gaps=extraction_gaps,
        analysis_failures=failures,
        has_issues=bool(extraction_gaps or failures),
    )


class _DailyRecapLlmContext(TypedDict):
    """Database-backed context blocks assembled for daily recap generation."""

    market_context: list[MarketContextEntry]
    economic_context: list[EconomicContextEntry]
    central_bank_context: list[CentralBankContextEntry]
    fx_heatmap_context: FxHeatmapContext
    probability_matrix_shift_context: list[ProbabilityMatrixShiftContextEntry]


def _gather_daily_recap_llm_context(reporting_date: date) -> _DailyRecapLlmContext:
    """Load market, economic, and central-bank context for recap generation."""
    market_context = build_market_context(reporting_date)
    economic_context = build_economic_context(reporting_date)
    central_bank_context = build_central_bank_context(reporting_date)
    fx_heatmap_context = get_fx_heatmap_context(reporting_date)
    probability_matrix_shift_context = build_probability_matrix_shift_context(
        reporting_date
    )
    logger.info(
        "Daily recap context ready for %s "
        "(market_entries=%s, economic_entries=%s, central_bank_entries=%s, "
        "fx_heatmap_currencies=%s, probability_matrix_banks=%s)",
        reporting_date.isoformat(),
        len(market_context),
        len(economic_context),
        len(central_bank_context),
        len(fx_heatmap_context["currency_strength"]),
        len(probability_matrix_shift_context),
    )
    return _DailyRecapLlmContext(
        market_context=market_context,
        economic_context=economic_context,
        central_bank_context=central_bank_context,
        fx_heatmap_context=fx_heatmap_context,
        probability_matrix_shift_context=probability_matrix_shift_context,
    )


def _list_recap_source_urls(analyses: list[AnalyzedArticle]) -> list[RecapSourceUrl]:
    """Collect source URLs from in-memory article analyses for the DailyRecap."""
    return [
        RecapSourceUrl(
            url=analyse["source_url"],
            regions=list(analyse["regions"]),
            label=analyse["source_name"],
        )
        for analyse in analyses
        if analyse.get("source_url")
    ]


def _build_daily_recap_generation_prompt(
    reporting_date: date,
    analyses: list[AnalyzedArticle],
    pipeline_issues: _PipelineIssues,
    llm_context: _DailyRecapLlmContext,
) -> str:
    """Assemble the daily recap LLM prompt from authoritative DB context."""
    market_context = llm_context["market_context"]
    economic_context = llm_context["economic_context"]
    central_bank_context = llm_context["central_bank_context"]
    fx_heatmap_context = llm_context["fx_heatmap_context"]
    probability_matrix_shift_context = llm_context["probability_matrix_shift_context"]
    return (
        f"Reporting date (T-1 session): {reporting_date.isoformat()}\n\n"
        f"{format_skills_as_prompt_block()}\n\n"
        "Verified market prices from the database (authoritative):\n"
        f"{json.dumps(market_context, ensure_ascii=False)}\n\n"
        "Economic indicators from the database (authoritative). Each indicator "
        "includes values_by_mode for Raw, MoM, QoQ, QoQy, "
        "and YoY. The indicator's main mode is "
        "default_mode / default_mode_label (from the seeded indicator "
        "default_mode); the matching values_by_mode entry has is_default=true. "
        "Use that main mode when stating the DB value unless the article "
        "clearly uses another convention — then match that mode before "
        "comparing:\n"
        f"{json.dumps(economic_context, ensure_ascii=False)}\n\n"
        "Central bank context from the database / Central Banks page "
        "(authoritative — figures: effective rates, CB macro values, next "
        "meeting; on a decision day, is_decision_day=true and decision_rates "
        "holds that day's key rates with previous/change — use those "
        "to state the decision and compare vs prior pricing; otherwise use "
        "figures only when they materially help the policy outlook):\n"
        f"{json.dumps(central_bank_context, ensure_ascii=False)}\n\n"
        "FX heatmap DoD % changes and per-currency RMS move magnitude "
        "(quadratic mean of pairwise % changes; always >= 0 — use pairwise "
        "cells for direction; use only when FX strength/weakness helps "
        "explain the session):\n"
        f"{json.dumps(fx_heatmap_context, ensure_ascii=False)}\n\n"
        "Central-bank probability matrices and DoD probability shifts "
        "(what the market is pricing — use only when policy-path repricing "
        "helps explain the session):\n"
        f"{json.dumps(probability_matrix_shift_context, ensure_ascii=False)}\n\n"
        "In-memory analyzed news for this run:\n"
        # Cap prompt size; the first 40 analyses are the newest ones in this run.
        f"{json.dumps(analyses[:40], ensure_ascii=False)}\n\n"
        "Pipeline issues (authoritative — must be reported if has_issues is true):\n"
        f"{json.dumps(pipeline_issues, ensure_ascii=False)}\n\n"
        "Produce the structured daily recap per the market-analysis skill: "
        "title (Day Month Year: one-liner), main_summary, us_summary, "
        "eur_summary, jp_summary, additional_summary. "
        "Do not withhold the recap because of gaps. Put pipeline gaps and "
        "unresolved DB-vs-article discrepancies under Uncertainties in the "
        "relevant zone (or additional_summary); omit Uncertainties when a "
        "zone has none material."
    )


def _upsert_daily_recap_from_llm_output(
    reporting_date: date,
    output: DailyRecapOutput,
    model_name: str,
    source_urls: list[RecapSourceUrl],
) -> DailyRecapModel:
    """Upsert the DailyRecap from structured LLM recap output."""
    logger.info(
        "LLM daily recap generation finished for %s; upserting DailyRecap",
        reporting_date.isoformat(),
    )
    recap, created = DailyRecapModel.objects.update_or_create(
        reporting_date=reporting_date,
        defaults={
            "title": output.title[:300],
            "main_summary": output.main_summary,
            "us_summary": output.us_summary,
            "eur_summary": output.eur_summary,
            "jp_summary": output.jp_summary,
            "additional_summary": output.additional_summary,
            "source_urls": source_urls,
            "model_name": model_name,
            "prompt_version": PROMPT_VERSION,
        },
    )
    logger.info(
        "DailyRecap %s for %s (id=%s, title=%r)",
        "created" if created else "updated",
        reporting_date.isoformat(),
        recap.pk,
        recap.title,
    )
    return recap


def generate_daily_recap(
    reporting_date: date,
    analyses: list[AnalyzedArticle] | None = None,
    extraction_sources: list[ArticleExtractionResult] | None = None,
    analysis_failures: list[ArticleAnalysisFailure] | None = None,
) -> DailyRecapModel:
    """Generate and upsert a DailyRecap from analyses plus market/econ data."""
    if not is_llm_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    analyses = analyses or []
    pipeline_issues = _build_pipeline_issues(extraction_sources, analysis_failures)
    logger.info(
        "Building daily recap context for %s " "(analyses=%s, pipeline_has_issues=%s)",
        reporting_date.isoformat(),
        len(analyses),
        pipeline_issues.get("has_issues"),
    )

    model_name = settings.LLM_MODEL_NAME
    llm_context = _gather_daily_recap_llm_context(reporting_date)
    source_urls = _list_recap_source_urls(analyses)
    prompt = _build_daily_recap_generation_prompt(
        reporting_date, analyses, pipeline_issues, llm_context
    )

    agent = Agent(
        settings.LLM_MODEL_NAME,
        output_type=DailyRecapOutput,
        instructions=load_instruction("recap_system.md"),
    )

    try:
        logger.info(
            "LLM daily recap generation starting for %s (model=%s)",
            reporting_date.isoformat(),
            model_name,
        )
        result = agent.run_sync(prompt)
        output: DailyRecapOutput = result.output
        return _upsert_daily_recap_from_llm_output(
            reporting_date, output, model_name, source_urls
        )
    except Exception as exc:
        logger.error("Daily analysis failed for %s: %s", reporting_date, exc)
        raise
