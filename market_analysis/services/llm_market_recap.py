"""LLM article analysis and daily market recap."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import TypedDict

from django.conf import settings
from pandas.tseries.offsets import BDay
from pydantic_ai import Agent

from central_banks_overview.models import CentralBankChoices
from core.services import logger
from data_visualization.services.central_banks_recap import (
    get_central_bank_data_item,
    get_central_bank_formatted_probability_matrix,
    get_formatted_probability_matrix_changes,
)
from data_visualization.services.market_recap import (
    FX_MATRIX_ORDER,
    FxMatrixRow,
    get_fx_prices_matrix,
)
from economic_overview.models import (
    EconomicDataCategoryChoices,
    EconomicDataLocationChoices,
    EconomicDataModel,
    EconomicPublicationFrequencyChoices,
    PublicationScheduleModel,
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
from market_analysis.models import DailyRecapModel
from market_analysis.services.analysis_cache import (
    get_cached_analysis,
    set_cached_analysis,
)
from market_analysis.services.article_extraction import (
    ArticleData,
    ArticleExtractionResult,
)
from market_overview.models import (
    AssetClassChoices,
    AssetModel,
    AssetTypeChoices,
    MarketPriceModel,
    PriceSourceChoices,
)

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
    """Return the latest daily recap, optionally filtered to ``reporting_date``."""
    daily_recaps = DailyRecapModel.objects.all()
    if reporting_date:
        daily_recaps = daily_recaps.filter(reporting_date=reporting_date)
    return daily_recaps.order_by("-reporting_date", "-date_added").first()


class MarketContextRow(TypedDict):
    """Market context row dictionnary."""

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


def _compute_pct_change(new: float, old: float | None) -> float | None:
    """Return the percent change from ``old`` to ``new``, or None if undefined."""
    if old in (None, 0):
        return None
    return ((new - old) / old) * 100.0


def _compute_bps_change(new: float, old: float | None) -> float | None:
    """Return the basis-point change from ``old`` to ``new`` (yield * 100)."""
    if old is None:
        return None
    return (new - old) * 100.0


def _get_closest_as_of_price_in_row(
    price_rows: list[MarketPriceModel], as_of: date
) -> MarketPriceModel | None:
    """Return the newest price row on or before ``as_of`` (rows newest-first)."""
    for row in price_rows:
        if row.date <= as_of:
            return row
    return None


def build_market_context(as_of: date) -> list[MarketContextRow]:
    """Verified prices with DoD / WoW / MoM changes for the agent prompt."""
    window_start = as_of - timedelta(days=MAX_MARKET_CONTEXT_DAYS)
    wow_target = as_of - timedelta(days=7)
    mom_target = as_of - timedelta(days=30)
    rows: list[MarketContextRow] = []
    assets = AssetModel.objects.all().order_by("asset_class", "short_name")
    for asset in assets:
        short_name_upper = (asset.short_name or "").upper()
        if any(marker in short_name_upper for marker in MARKET_CONTEXT_IGNORE_MARKERS):
            continue
        price_rows = list(
            MarketPriceModel.objects.filter(
                asset=asset,
                date__gte=window_start,
                date__lte=as_of,
                price__isnull=False,
            ).order_by("-date")
        )
        if not price_rows:
            continue
        price_row = price_rows[0]
        previous_row = price_rows[1] if len(price_rows) > 1 else None
        wow_row = _get_closest_as_of_price_in_row(price_rows, wow_target)
        mom_row = _get_closest_as_of_price_in_row(price_rows, mom_target)
        previous_price = previous_row.price if previous_row else None
        change_dod = (
            price_row.price - previous_price if previous_price is not None else None
        )
        wow_price = wow_row.price if wow_row else None
        mom_price = mom_row.price if mom_row else None
        change_wow = price_row.price - wow_price if wow_price is not None else None
        change_mom = price_row.price - mom_price if mom_price is not None else None
        is_rates = asset.asset_class == AssetClassChoices.RATES
        is_vol = asset.asset_type == AssetTypeChoices.VOLATILITY_INDEX
        rows.append(
            MarketContextRow(
                short_name=asset.short_name,
                ticker=asset.ticker,
                asset_class=AssetClassChoices(asset.asset_class),
                date=price_row.date.isoformat(),
                price=price_row.price,
                source=PriceSourceChoices(asset.source),
                previous_date=(previous_row.date.isoformat() if previous_row else None),
                previous_price=previous_price,
                change_dod=change_dod,
                change_dod_pct=(
                    None
                    if is_rates or is_vol
                    else _compute_pct_change(price_row.price, previous_price)
                ),
                change_dod_bps=(
                    _compute_bps_change(price_row.price, previous_price)
                    if is_rates
                    else None
                ),
                change_dod_pts=change_dod if is_vol else None,
                change_wow_pct=(
                    None
                    if is_rates or is_vol
                    else _compute_pct_change(price_row.price, wow_price)
                ),
                change_wow_bps=(
                    _compute_bps_change(price_row.price, wow_price)
                    if is_rates
                    else None
                ),
                change_wow_pts=change_wow if is_vol else None,
                change_mom_pct=(
                    None
                    if is_rates or is_vol
                    else _compute_pct_change(price_row.price, mom_price)
                ),
                change_mom_bps=(
                    _compute_bps_change(price_row.price, mom_price)
                    if is_rates
                    else None
                ),
                change_mom_pts=change_mom if is_vol else None,
            )
        )
    return rows


class EconomicContextRow(TypedDict):
    """Economic indicator context row for LLM prompts."""

    name: str
    location: EconomicDataLocationChoices
    category: EconomicDataCategoryChoices
    frequency: EconomicPublicationFrequencyChoices
    period: str | None  # ISO date string for the LLM/JSON boundary
    period_display: str | None  # Display period label for the LLM
    data_value: float | None
    comment: str | None
    publication_date: str | None  # ISO datetime/date string for the LLM/JSON boundary
    kind: str


def build_economic_context(as_of: date) -> list[EconomicContextRow]:
    """Economic indicators scheduled for publication on ``as_of`` only."""
    rows: list[EconomicContextRow] = []
    schedules = (
        PublicationScheduleModel.objects.filter(current_publication_date__date=as_of)
        .select_related("indicator")
        .order_by("indicator__location", "indicator__name")
    )
    for schedule in schedules:
        indicator = schedule.indicator
        latest = (
            EconomicDataModel.objects.filter(indicator=indicator)
            .order_by("-period", "-last_modified")
            .first()
        )
        pub = schedule.current_publication_date
        rows.append(
            EconomicContextRow(
                name=indicator.name,
                location=EconomicDataLocationChoices(indicator.location),
                category=EconomicDataCategoryChoices(indicator.category),
                frequency=EconomicPublicationFrequencyChoices(indicator.frequency),
                period=latest.period.isoformat() if latest and latest.period else None,
                period_display=latest.get_period_display() if latest else None,
                data_value=latest.data_value if latest else None,
                comment=latest.comment if latest else None,
                publication_date=pub.isoformat() if pub else as_of.isoformat(),
                kind="scheduled_release",
            )
        )
    return rows


class CentralBankFigureRow(TypedDict):
    """One central-bank key figure as shown on the Central Banks page."""

    label: str  # Display label from the Central Banks UI
    value: str  # Display value from the Central Banks UI


class CentralBankContextRow(TypedDict):
    """Central-bank key figures block for LLM prompts (one bank)."""

    central_bank: CentralBankChoices
    reference_date: str  # ISO date string for the LLM/JSON boundary
    figures: list[CentralBankFigureRow]


def build_central_bank_context(as_of: date) -> list[CentralBankContextRow]:
    """Key CB figures as on the Central Banks page (policy baseline for the LLM)."""
    rows: list[CentralBankContextRow] = []
    for central_bank in CENTRAL_BANKS_FOR_CONTEXT:
        figures = [
            CentralBankFigureRow(label=item["label"], value=item["value"])
            for item in get_central_bank_data_item(central_bank, as_of)
        ]
        rows.append(
            CentralBankContextRow(
                central_bank=central_bank,
                reference_date=as_of.isoformat(),
                figures=figures,
            )
        )
    return rows


def _get_previous_business_day(as_of: date) -> date:
    """Return the previous weekday business day before ``as_of``."""
    return (as_of - BDay(1)).date()


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


class FxCurrencyStrengthRow(TypedDict):
    """Average pairwise FX DoD % change for one currency vs the heatmap basket."""

    currency: str
    average_change_pct: float


class FxHeatmapContext(TypedDict):
    """FX heatmap (pairwise DoD %) plus per-currency average strength."""

    as_of: str
    previous_date: str
    currencies: list[str]
    matrix: list[FxMatrixRow]
    currency_strength: list[FxCurrencyStrengthRow]


def _get_fx_matrix_pair_change(matrix_row: FxMatrixRow, quote_currency: str) -> float:
    """Return the pairwise DoD % change for one quote currency in a matrix row."""
    if quote_currency == "EUR":
        return matrix_row["EUR"]
    if quote_currency == "USD":
        return matrix_row["USD"]
    if quote_currency == "GBP":
        return matrix_row["GBP"]
    if quote_currency == "JPY":
        return matrix_row["JPY"]
    if quote_currency == "CHF":
        return matrix_row["CHF"]
    if quote_currency == "AUD":
        return matrix_row["AUD"]
    if quote_currency == "CNY":
        return matrix_row["CNY"]
    raise ValueError(f"Unsupported FX matrix quote currency: {quote_currency}")


def _compute_fx_currency_strength(
    matrix: list[FxMatrixRow],
) -> list[FxCurrencyStrengthRow]:
    """Average off-diagonal pairwise % changes for each base currency row."""
    strength_rows: list[FxCurrencyStrengthRow] = []
    for matrix_row in matrix:
        base_currency = matrix_row["currency"]
        pairwise_changes: list[float] = []
        for quote_currency in FX_MATRIX_ORDER:
            if quote_currency == base_currency:
                continue
            pairwise_changes.append(
                _get_fx_matrix_pair_change(matrix_row, quote_currency)
            )
        average_change_pct = (
            sum(pairwise_changes) / len(pairwise_changes) if pairwise_changes else 0.0
        )
        strength_rows.append(
            FxCurrencyStrengthRow(
                currency=base_currency,
                average_change_pct=round(average_change_pct, 4),
            )
        )
    return strength_rows


def build_fx_heatmap_context(as_of: date) -> FxHeatmapContext:
    """FX heatmap DoD % matrix and average currency strength for LLM prompts."""
    previous_date = _get_previous_business_day(as_of)
    matrix = get_fx_prices_matrix(as_of, previous_date)
    return FxHeatmapContext(
        as_of=as_of.isoformat(),
        previous_date=previous_date.isoformat(),
        currencies=list(FX_MATRIX_ORDER),
        matrix=matrix,
        currency_strength=_compute_fx_currency_strength(matrix),
    )


class ProbabilityStepRow(TypedDict):
    """One rate-step row of probabilities or probability changes."""

    expected_rate_step: int
    probabilities: list[float]


class ProbabilityMatrixShiftContextRow(TypedDict):
    """Current policy-path probabilities and DoD shifts for one central bank."""

    central_bank: CentralBankChoices
    as_of: str
    previous_date: str
    meeting_dates: list[str]
    current_probabilities: list[ProbabilityStepRow]
    probability_changes: list[ProbabilityStepRow]


def build_probability_matrix_shift_context(
    as_of: date,
) -> list[ProbabilityMatrixShiftContextRow]:
    """FRB / ECB / BOJ probability matrices and DoD shifts for LLM prompts."""
    previous_date = _get_previous_business_day(as_of)
    rows: list[ProbabilityMatrixShiftContextRow] = []
    for central_bank in CENTRAL_BANKS_FOR_CONTEXT:
        try:
            current_matrix = get_central_bank_formatted_probability_matrix(
                central_bank, as_of
            )
            previous_matrix = get_central_bank_formatted_probability_matrix(
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
            continue

        if current_matrix is None:
            continue

        meeting_dates = _format_meeting_dates_for_context(
            current_matrix["meeting_dates"]
        )
        current_probabilities = [
            ProbabilityStepRow(
                expected_rate_step=entry["expected_rate_step"],
                probabilities=list(entry["probabilities"]),
            )
            for entry in current_matrix["probability_matrix"]
        ]
        probability_changes = [
            ProbabilityStepRow(
                expected_rate_step=entry["expected_rate_step"],
                probabilities=list(entry["probabilities"]),
            )
            for entry in (
                change_matrix["probability_matrix"] if change_matrix is not None else []
            )
        ]
        rows.append(
            ProbabilityMatrixShiftContextRow(
                central_bank=central_bank,
                as_of=as_of.isoformat(),
                previous_date=previous_date.isoformat(),
                meeting_dates=meeting_dates,
                current_probabilities=current_probabilities,
                probability_changes=probability_changes,
            )
        )
    return rows


class EvidenceEntry(TypedDict):
    """Evidence entry dictionnary."""

    claim: str
    source_url: str
    quote_or_paraphrase: str
    is_interpretation: bool


class AnalyzedArticle(TypedDict):
    """Structured article analysis (process memory only; not persisted)."""

    title: str
    summary: str
    event_types: list[EventType]
    companies: list[str]
    sectors: list[str]
    sentiment: Sentiment
    key_facts: list[str]
    uncertainties: list[str]
    source_url: str


def analyze_extracted_article(
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
            return cached["analysis"]

    content = article["content"] or ""
    if len(content) > MAX_ARTICLE_CHARS:
        content = content[: MAX_ARTICLE_CHARS - 20] + "\n…[truncated]"

    prompt = (
        f"{format_skills_as_prompt_block()}\n\n"
        f"Article URL: {article['url']}\n"
        f"Title: {article['title']}\n"
        f"Source: {article['source_name']} ({article['source_key']})\n\n"
        f"{wrap_untrusted_content_safely(content)}\n\n"
        "Return structured analysis. Use company/sector names as written in the "
        "article. Never invent URLs."
    )

    try:
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
        )
        if use_cache and article["url"]:
            set_cached_analysis(reporting_date, analyzed, source_url=article["url"])
        logger.info(
            "LLM article analysis finished for %s (%s)",
            article.get("source_key"),
            article["url"],
        )
        return analyzed
    except Exception as exc:
        logger.error("Article analysis failed for %s: %s", article["url"], exc)
        raise


class ArticleAnalysisFailure(TypedDict):
    """Article analysis failure dictionnary."""

    url: str
    error: str


class ArticleBatchAnalysisResult(TypedDict):
    """Batch article analysis result dictionnary."""

    analyses: list[AnalyzedArticle]
    analyzed_count: int
    failed: list[ArticleAnalysisFailure]
    cache_hits: int
    cache_misses: int


def analyze_extracted_articles(
    articles: list[ArticleData],
    reporting_date: date,
    use_cache: bool = True,
) -> ArticleBatchAnalysisResult:
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
                    analyzed.append(cached["analysis"])
                    cache_hits += 1
                    logger.info("Article analysis cache hit (%s/%s)", index, total)
                    continue
            analyzed.append(
                analyze_extracted_article(
                    article,
                    reporting_date=reporting_date,
                    use_cache=use_cache,
                )
            )
            cache_misses += 1
        except Exception as exc:
            failed.append(ArticleAnalysisFailure(url=article["url"], error=str(exc)))
            logger.warning(
                "Article analysis %s/%s failed: %s",
                index,
                total,
                exc,
            )

    logger.info(
        "Article batch analysis complete for %s: analyzed=%s failed=%s "
        "cache_hits=%s cache_misses=%s",
        reporting_date.isoformat(),
        len(analyzed),
        len(failed),
        cache_hits,
        cache_misses,
    )
    return ArticleBatchAnalysisResult(
        analyses=analyzed,
        analyzed_count=len(analyzed),
        failed=failed,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


class ExtractionGap(TypedDict):
    """Source that yielded no article during extraction."""

    source_id: str
    name: str
    comment: str | None


class PipelineIssues(TypedDict):
    """Extraction/analysis gaps summarized for the recap prompt."""

    extraction_gaps: list[ExtractionGap]
    analysis_failures: list[ArticleAnalysisFailure]
    has_issues: bool


def _build_pipeline_issues(
    extraction_sources: list[ArticleExtractionResult] | None,
    analysis_failures: list[ArticleAnalysisFailure] | None,
) -> PipelineIssues:
    """Summarize missing extractions and failed analyses for the recap prompt."""
    extraction_gaps = [
        ExtractionGap(
            source_id=source["source_id"],
            name=source["name"],
            comment=source.get("comment"),
        )
        for source in (extraction_sources or [])
        if not source.get("article")
    ]
    failures = list(analysis_failures or [])
    return PipelineIssues(
        extraction_gaps=extraction_gaps,
        analysis_failures=failures,
        has_issues=bool(extraction_gaps or failures),
    )


def generate_daily_recap(
    reporting_date: date,
    analyses: list[AnalyzedArticle] | None = None,
    extraction_sources: list[ArticleExtractionResult] | None = None,
    analysis_failures: list[ArticleAnalysisFailure] | None = None,
) -> DailyRecapModel:
    """Persist analysis from in-memory analyses + ingested market/econ data."""
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
    market_context = build_market_context(reporting_date)
    economic_context = build_economic_context(reporting_date)
    central_bank_context = build_central_bank_context(reporting_date)
    fx_heatmap_context = build_fx_heatmap_context(reporting_date)
    probability_matrix_shift_context = build_probability_matrix_shift_context(
        reporting_date
    )
    logger.info(
        "Daily recap context ready for %s "
        "(market_rows=%s, economic_rows=%s, central_bank_rows=%s, "
        "fx_heatmap_currencies=%s, probability_matrix_banks=%s)",
        reporting_date.isoformat(),
        len(market_context),
        len(economic_context),
        len(central_bank_context),
        len(fx_heatmap_context["currency_strength"]),
        len(probability_matrix_shift_context),
    )
    source_urls = [
        analyse["source_url"] for analyse in analyses if analyse.get("source_url")
    ]

    prompt = (
        f"Reporting date (T-1 session): {reporting_date.isoformat()}\n\n"
        f"{format_skills_as_prompt_block()}\n\n"
        "Verified market prices from the database (authoritative):\n"
        f"{json.dumps(market_context, ensure_ascii=False)}\n\n"
        "Economic indicators from the database (authoritative):\n"
        f"{json.dumps(economic_context, ensure_ascii=False)}\n\n"
        "Central bank key figures from the database / Central Banks page "
        "(authoritative policy baseline — effective rates, CB macro prints, "
        "next meeting; use when assessing policy outlook / future CB moves):\n"
        f"{json.dumps(central_bank_context, ensure_ascii=False)}\n\n"
        "FX heatmap DoD % changes and per-currency average strength "
        "(use only when FX strength/weakness helps explain the session):\n"
        f"{json.dumps(fx_heatmap_context, ensure_ascii=False)}\n\n"
        "Central-bank probability matrices and DoD probability shifts "
        "(what the market is pricing — use only when policy-path repricing "
        "helps explain the session):\n"
        f"{json.dumps(probability_matrix_shift_context, ensure_ascii=False)}\n\n"
        "In-memory analyzed news for this run:\n"
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
        logger.info(
            "LLM daily recap generation finished for %s; persisting DailyRecap",
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
    except Exception as exc:
        logger.error("Daily analysis failed for %s: %s", reporting_date, exc)
        raise
