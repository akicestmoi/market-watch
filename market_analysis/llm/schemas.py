"""Pydantic schemas for LLM structured outputs (article analysis, recap, chat)."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """High-level category of a news event."""

    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    M_AND_A = "M_AND_A"
    REGULATION = "REGULATION"
    MACRO = "MACRO"
    STOCKS = "STOCKS"
    RATES = "RATES"
    CREDIT = "CREDIT"
    FX = "FX"
    CRYPTO = "CRYPTO"
    COMMODITIES = "COMMODITIES"
    MARKETS = "MARKETS"
    CORPORATE = "CORPORATE"
    OTHER = "OTHER"


class Sentiment(str, Enum):
    """Coarse sentiment of the article toward markets and events."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class EvidenceItem(BaseModel):
    """A single claim backed by a source URL and quote/paraphrase."""

    claim: str = Field(..., max_length=500)
    source_url: str = Field(..., max_length=1000)
    quote_or_paraphrase: str = Field(..., max_length=800)
    is_interpretation: bool = False


class ArticleAnalysisOutput(BaseModel):
    """Structured analysis of one collected article (pipeline memory only)."""

    title: str = Field(..., max_length=500)
    summary: str = Field(..., max_length=2000)
    event_types: List[EventType] = Field(default_factory=list, max_length=10)
    companies: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Company names mentioned as impacted.",
    )
    sectors: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Sectors mentioned as impacted.",
    )
    sentiment: Sentiment
    key_facts: List[str] = Field(default_factory=list, max_length=15)
    uncertainties: List[str] = Field(default_factory=list, max_length=10)
    source_url: str = Field(..., max_length=1000)


class DailyRecapOutput(BaseModel):
    """LLM shape for the daily T-1 analysis persisted on DailyRecapModel."""

    title: str = Field(
        ...,
        max_length=300,
        description=(
            "Format: 'Day Month Year: one-liner', e.g. "
            "'23 October 2026: Oil-led risk-off as higher energy costs weigh on equities'."
        ),
    )
    main_summary: str = Field(
        ...,
        max_length=6000,
        description=(
            "High-level worldwide mainline only (US/EUR/Japan + RoW). Not detailed."
        ),
    )
    us_summary: str = Field(
        ...,
        max_length=8000,
        description=(
            "US zone detail as markdown bullets '- Subtitle: content'; "
            "assertive body; end with '- Uncertainties: …' "
            "(include DB vs article discrepancies)."
        ),
    )
    eur_summary: str = Field(
        ...,
        max_length=8000,
        description=(
            "EUR-denominated euro-area zone detail as bullets "
            "'- Subtitle: content'; end with Uncertainties. "
            "Watch DE–FR yield spreads when material."
        ),
    )
    jp_summary: str = Field(
        ...,
        max_length=8000,
        description=(
            "Japan zone detail as bullets '- Subtitle: content'; "
            "end with Uncertainties."
        ),
    )
    additional_summary: str = Field(
        ...,
        max_length=8000,
        description=(
            "Everything else notable: commodities, crypto, minor FX, geopolitics, "
            "non-EUR Europe, EM, etc. Bullets '- Subtitle: content'; "
            "end with Uncertainties."
        ),
    )


class ChatAnswerOutput(BaseModel):
    """LLM shape for a chat reply."""

    answer: str = Field(..., max_length=8000)
    citations: List[EvidenceItem] = Field(default_factory=list, max_length=15)
    missing_information: List[str] = Field(default_factory=list, max_length=10)
    uncertainties: List[str] = Field(default_factory=list, max_length=10)
    proposed_recap_title: Optional[str] = Field(
        default=None,
        max_length=300,
        description=(
            "Proposed DailyRecap title only if it would change; "
            "apply only after user agrees or orders. Leave null if unchanged."
        ),
    )
    proposed_main_summary: Optional[str] = Field(
        default=None,
        max_length=6000,
        description="Only if main_summary would change; else null.",
    )
    proposed_us_summary: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Only if us_summary would change; else null.",
    )
    proposed_eur_summary: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Only if eur_summary would change; else null.",
    )
    proposed_jp_summary: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Only if jp_summary would change; else null.",
    )
    proposed_additional_summary: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Only if additional_summary would change; else null.",
    )
    proposed_recap_reporting_date: Optional[str] = Field(
        default=None,
        description="ISO date for the recap being discussed/updated.",
    )
    cursor_guidelines_prompt: Optional[str] = Field(
        default=None,
        max_length=8000,
        description=(
            "Prompt for the user to paste into Cursor Agent to edit market-analysis.md. "
            "Only after a recap update was agreed or ordered."
        ),
    )
    recap_updated: bool = Field(
        default=False,
        description=(
            "Informational only for the model. The API sets this from whether "
            "tool_update_daily_recap actually persisted changes."
        ),
    )
