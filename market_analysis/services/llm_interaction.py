"""LLM chat — one shared agent; prior turns come from the request body."""

from contextvars import ContextVar
from datetime import date, timedelta
from typing import Literal, TypedDict

from django.conf import settings
from pydantic_ai import Agent, Tool

from core.services import logger
from market_analysis.llm.config import (
    MAX_CHAT_HISTORY_MESSAGES,
    PROMPT_VERSION,
    format_skills_as_prompt_block,
    is_llm_configured,
    load_instruction,
)
from market_analysis.llm.schemas import ChatAnswerOutput
from market_analysis.models import DailyRecapModel
from market_analysis.services.llm_market_recap import (
    CentralBankContextRow,
    EconomicContextRow,
    EvidenceEntry,
    FxHeatmapContext,
    MarketContextRow,
    ProbabilityMatrixShiftContextRow,
    build_central_bank_context,
    build_economic_context,
    build_fx_heatmap_context,
    build_market_context,
    build_probability_matrix_shift_context,
)

_chat_agent: Agent[None, ChatAnswerOutput] | None = None
# Set True only when _update_daily_recap persists successfully in this ask().
_recap_updated_this_turn: ContextVar[bool] = ContextVar(
    "market_analysis_recap_updated_this_turn", default=False
)


class ChatMessage(TypedDict):
    """Chat message dictionnary."""

    role: Literal["user", "assistant"]
    content: str


class ChatAskResult(TypedDict):
    """Chat ask result dictionnary."""

    answer: str
    citations: list[EvidenceEntry]
    missing_information: list[str]
    uncertainties: list[str]
    messages: list[ChatMessage]
    proposed_recap_title: str | None
    proposed_main_summary: str | None
    proposed_us_summary: str | None
    proposed_eur_summary: str | None
    proposed_jp_summary: str | None
    proposed_additional_summary: str | None
    proposed_recap_reporting_date: str | None
    cursor_guidelines_prompt: str | None
    recap_updated: bool


class PreviousRecapItem(TypedDict):
    """One daily recap row returned by the get_previous_recaps tool."""

    id: int
    reporting_date: str
    title: str
    main_summary: str
    us_summary: str
    eur_summary: str
    jp_summary: str
    additional_summary: str
    source_urls: list[str]


class UpdateDailyRecapResult(TypedDict, total=False):
    """Result of the update_daily_recap tool."""

    ok: bool
    error: str
    id: int
    reporting_date: str
    title: str


def _get_previous_recaps(days: int = 7, limit: int = 5) -> list[PreviousRecapItem]:
    """Return recent daily analyses (full structured content)."""
    start_date = date.today() - timedelta(days=days)
    return [
        PreviousRecapItem(
            id=recap.pk,
            reporting_date=recap.reporting_date.isoformat(),
            title=recap.title,
            main_summary=recap.main_summary,
            us_summary=recap.us_summary,
            eur_summary=recap.eur_summary,
            jp_summary=recap.jp_summary,
            additional_summary=recap.additional_summary,
            source_urls=recap.source_urls,
        )
        for recap in DailyRecapModel.objects.filter(
            reporting_date__gte=start_date
        ).order_by("-reporting_date")[:limit]
    ]


def _get_market_context(reporting_date: str) -> list[MarketContextRow]:
    """Return verified market prices for all assets as of an ISO date (YYYY-MM-DD)."""
    day = date.fromisoformat(reporting_date)
    return list(build_market_context(day))


def _get_economic_context(reporting_date: str) -> list[EconomicContextRow]:
    """Return economic indicator context for an ISO reporting date (YYYY-MM-DD)."""
    day = date.fromisoformat(reporting_date)
    return list(build_economic_context(day))


def _get_central_bank_context(reporting_date: str) -> list[CentralBankContextRow]:
    """Return Central Banks page key figures (effective rate, CB prints, next meeting)
    for FRB / ECB / BOJ as of an ISO date (YYYY-MM-DD). Use for policy outlook."""
    day = date.fromisoformat(reporting_date)
    return list(build_central_bank_context(day))


def _get_fx_heatmap_context(reporting_date: str) -> FxHeatmapContext:
    """Return FX heatmap DoD % matrix and RMS currency-move magnitude for an ISO date."""
    day = date.fromisoformat(reporting_date)
    return build_fx_heatmap_context(day)


def _get_probability_matrix_shift_context(
    reporting_date: str,
) -> list[ProbabilityMatrixShiftContextRow]:
    """Return FRB / ECB / BOJ probability matrices and DoD shifts for an ISO date."""
    day = date.fromisoformat(reporting_date)
    return list(build_probability_matrix_shift_context(day))


def _update_daily_recap(
    reporting_date: str,
    title: str | None = None,
    main_summary: str | None = None,
    us_summary: str | None = None,
    eur_summary: str | None = None,
    jp_summary: str | None = None,
    additional_summary: str | None = None,
) -> UpdateDailyRecapResult:
    """Update the stored DailyRecap for a date.

    Call only after explicit user agreement to a proposal, or when the user
    explicitly orders an update. Never call on ambiguous intent.
    Pass only the fields that should change; leave others empty.
    """
    fields = {
        "title": title,
        "main_summary": main_summary,
        "us_summary": us_summary,
        "eur_summary": eur_summary,
        "jp_summary": jp_summary,
        "additional_summary": additional_summary,
    }
    if not any(value for value in fields.values()):
        return UpdateDailyRecapResult(
            ok=False,
            error=(
                "Provide title and/or at least one summary field "
                "(main_summary, us_summary, eur_summary, jp_summary, additional_summary)"
            ),
        )
    day = date.fromisoformat(reporting_date)
    recap = DailyRecapModel.objects.filter(reporting_date=day).first()
    if not recap:
        return UpdateDailyRecapResult(
            ok=False,
            error=f"No DailyRecap for {reporting_date}",
        )
    if title:
        recap.title = title[:300]
    if main_summary is not None and main_summary != "":
        recap.main_summary = main_summary
    if us_summary is not None and us_summary != "":
        recap.us_summary = us_summary
    if eur_summary is not None and eur_summary != "":
        recap.eur_summary = eur_summary
    if jp_summary is not None and jp_summary != "":
        recap.jp_summary = jp_summary
    if additional_summary is not None and additional_summary != "":
        recap.additional_summary = additional_summary
    recap.model_name = settings.LLM_MODEL_NAME
    recap.prompt_version = PROMPT_VERSION
    recap.save()
    _recap_updated_this_turn.set(True)
    logger.info("DailyRecap %s updated via chat", reporting_date)
    return UpdateDailyRecapResult(
        ok=True,
        id=recap.pk,
        reporting_date=reporting_date,
        title=recap.title,
    )


def _get_chat_agent() -> Agent[None, ChatAnswerOutput]:
    """Shared chat agent (same tools + instructions across requests)."""
    global _chat_agent
    if _chat_agent is None:
        if not is_llm_configured():
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        _chat_agent = Agent(
            settings.LLM_MODEL_NAME,
            output_type=ChatAnswerOutput,
            instructions=load_instruction("chat_system.md"),
            tools=[
                Tool(_get_previous_recaps, name="get_previous_recaps"),
                Tool(_get_market_context, name="get_market_context"),
                Tool(_get_economic_context, name="get_economic_context"),
                Tool(_get_central_bank_context, name="get_central_bank_context"),
                Tool(_get_fx_heatmap_context, name="get_fx_heatmap_context"),
                Tool(
                    _get_probability_matrix_shift_context,
                    name="get_probability_matrix_shift_context",
                ),
                Tool(_update_daily_recap, name="update_daily_recap"),
            ],
        )
    return _chat_agent


def ask(
    question: str,
    messages: list[ChatMessage] | None = None,
) -> ChatAskResult:
    """Answer one turn using optional prior messages sent by the client.

    Chat is stateless on the server.
    The DB never stores turns — the client owns history and sends it back each request.
    """
    if not is_llm_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    history: list[ChatMessage] = [
        ChatMessage(role=message["role"], content=message["content"])
        for message in (messages or [])
        if message.get("role") in ("user", "assistant") and message.get("content")
    ][-MAX_CHAT_HISTORY_MESSAGES:]

    prompt_parts = [
        format_skills_as_prompt_block(),
        "",
        "Conversation so far:",
    ]
    for message in history:
        prompt_parts.append(f"{message['role'].upper()}: {message['content']}")
    prompt_parts.append(f"USER: {question.strip()}")
    prompt_parts.append(
        "Respond clearly. Use tools for recaps, market context, or economic "
        "context. Propose recap edits in the structured fields when helpful; "
        "call _update_daily_recap only after explicit user agreement or order. "
        "Only after a recap update is agreed/ordered may you fill "
        "cursor_guidelines_prompt for missing regime logic."
    )
    prompt = "\n".join(prompt_parts)

    updated_token = _recap_updated_this_turn.set(False)
    try:
        result = _get_chat_agent().run_sync(prompt)
        output: ChatAnswerOutput = result.output
        # Persist flag comes from the update tool, not the LLM's structured guess.
        recap_updated = _recap_updated_this_turn.get()
        return ChatAskResult(
            answer=output.answer,
            citations=[EvidenceEntry(**c.model_dump()) for c in output.citations],
            missing_information=output.missing_information,
            uncertainties=output.uncertainties,
            messages=history
            + [
                ChatMessage(role="user", content=question.strip()),
                ChatMessage(role="assistant", content=output.answer),
            ],
            proposed_recap_title=output.proposed_recap_title,
            proposed_main_summary=output.proposed_main_summary,
            proposed_us_summary=output.proposed_us_summary,
            proposed_eur_summary=output.proposed_eur_summary,
            proposed_jp_summary=output.proposed_jp_summary,
            proposed_additional_summary=output.proposed_additional_summary,
            proposed_recap_reporting_date=output.proposed_recap_reporting_date,
            cursor_guidelines_prompt=output.cursor_guidelines_prompt,
            recap_updated=recap_updated,
        )
    except Exception as exc:
        logger.error("Chat failed: %s", exc)
        raise
    finally:
        _recap_updated_this_turn.reset(updated_token)
