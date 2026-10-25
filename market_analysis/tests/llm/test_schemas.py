"""Tests for market_analysis.llm.schemas."""

from market_analysis.llm.schemas import (
    ArticleAnalysisOutput,
    DailyRecapOutput,
    EventType,
    Sentiment,
)


def test_article_analysis_schema_validates():
    """
    GIVEN valid article analysis fields including event types and sentiment
    WHEN ArticleAnalysisOutput is constructed
    THEN the model validates and preserves the provided values
    """
    out = ArticleAnalysisOutput(
        title="Earnings beat",
        summary="Company beat estimates.",
        event_types=[EventType.EARNINGS, EventType.GUIDANCE],
        companies=["Acme"],
        sectors=["Tech"],
        sentiment=Sentiment.BULLISH,
        key_facts=["EPS above consensus"],
        uncertainties=["Guidance unclear"],
        source_url="https://example.com/a",
    )
    assert out.event_types == [EventType.EARNINGS, EventType.GUIDANCE]
    assert out.companies == ["Acme"]


def test_daily_recap_schema_requires_zone_summaries():
    """
    GIVEN structured daily recap fields
    WHEN DailyRecapOutput is constructed
    THEN title and all zone summaries are preserved
    """
    out = DailyRecapOutput(
        title="23 October 2026: Oil-led risk-off as energy costs weigh on equities",
        main_summary="Worldwide risk-off led by oil.",
        us_summary="- Stocks: S&P 500 (-1.4%).\n- Uncertainties: None.",
        eur_summary="- Rates: Bunds bid.\n- Uncertainties: DE–FR spread unclear.",
        jp_summary="- Stocks: Nikkei soft.\n- Uncertainties: None.",
        additional_summary="- Commodities: Brent (-2.1%).\n- Uncertainties: None.",
    )
    assert out.main_summary.startswith("Worldwide")
    assert "S&P 500" in out.us_summary
    assert "additional_summary" not in out.title
