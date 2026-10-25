"""LLM chat — one shared agent; prior turns come from the request body."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, timedelta
from typing import List, Optional, TypedDict

from django.conf import settings
from pydantic_ai import Agent

from core.services import logger
from market_analysis.llm.config import (
    MAX_CHAT_HISTORY_MESSAGES,
    PROMPT_VERSION,
    llm_is_configured,
    load_instruction,
    skills_as_prompt_block,
)
from market_analysis.llm.schemas import ChatAnswerOutput
from market_analysis.models import DailyRecapModel
from market_analysis.services.llm_market_recap_services import (
    EvidenceEntry,
    _build_central_bank_context,
    _build_economic_context,
    _build_market_context,
)

_chat_agent: Optional[Agent] = None
# Set True only when tool_update_daily_recap persists successfully in this ask().
_recap_updated_this_turn: ContextVar[bool] = ContextVar(
    "market_analysis_recap_updated_this_turn", default=False
)


class ChatMessage(TypedDict):
    """Chat message dictionnary."""

    role: str
    content: str


class ChatAskResult(TypedDict):
    """Chat ask result dictionnary."""

    answer: str
    citations: List[EvidenceEntry]
    missing_information: List[str]
    uncertainties: List[str]
    messages: List[ChatMessage]
    proposed_recap_title: Optional[str]
    proposed_main_summary: Optional[str]
    proposed_us_summary: Optional[str]
    proposed_eur_summary: Optional[str]
    proposed_jp_summary: Optional[str]
    proposed_additional_summary: Optional[str]
    proposed_recap_reporting_date: Optional[str]
    cursor_guidelines_prompt: Optional[str]
    recap_updated: bool


def _get_previous_recaps(days: int = 7, limit: int = 5) -> list:
    """Load recent daily recaps for the chat agent tool."""
    start_date = date.today() - timedelta(days=days)
    return [
        {
            "id": recap.id,
            "reporting_date": recap.reporting_date.isoformat(),
            "title": recap.title,
            "main_summary": recap.main_summary,
            "us_summary": recap.us_summary,
            "eur_summary": recap.eur_summary,
            "jp_summary": recap.jp_summary,
            "additional_summary": recap.additional_summary,
            "source_urls": recap.source_urls,
        }
        for recap in DailyRecapModel.objects.filter(
            reporting_date__gte=start_date
        ).order_by("-reporting_date")[:limit]
    ]


def _get_market_context(reporting_date: str) -> list:
    """Load verified market prices for an ISO reporting date."""
    day = date.fromisoformat(reporting_date)
    return list(_build_market_context(day))


def _get_economic_context(reporting_date: str) -> list:
    """Load economic context rows for an ISO reporting date."""
    day = date.fromisoformat(reporting_date)
    return list(_build_economic_context(day))


def _get_central_bank_context(reporting_date: str) -> list:
    """Load Central Banks page key figures for an ISO reporting date."""
    day = date.fromisoformat(reporting_date)
    return list(_build_central_bank_context(day))


def _update_daily_recap(
    reporting_date: str,
    title: Optional[str] = None,
    main_summary: Optional[str] = None,
    us_summary: Optional[str] = None,
    eur_summary: Optional[str] = None,
    jp_summary: Optional[str] = None,
    additional_summary: Optional[str] = None,
) -> dict:
    """Persist a DailyRecap update (when to call is governed by the skill)."""
    fields = {
        "title": title,
        "main_summary": main_summary,
        "us_summary": us_summary,
        "eur_summary": eur_summary,
        "jp_summary": jp_summary,
        "additional_summary": additional_summary,
    }
    if not any(value for value in fields.values()):
        return {
            "ok": False,
            "error": (
                "Provide title and/or at least one summary field "
                "(main_summary, us_summary, eur_summary, jp_summary, additional_summary)"
            ),
        }
    day = date.fromisoformat(reporting_date)
    recap = DailyRecapModel.objects.filter(reporting_date=day).first()
    if not recap:
        return {
            "ok": False,
            "error": f"No DailyRecap for {reporting_date}",
        }
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
    logger.info("DailyRecap %s updated via chat", reporting_date)
    return {
        "ok": True,
        "id": recap.id,
        "reporting_date": reporting_date,
        "title": recap.title,
    }


def _register_chat_tools(agent: Agent) -> None:
    """Data + recap-update tools; when to update is governed by the skill."""

    @agent.tool_plain
    def tool_get_previous_recaps(days: int = 7, limit: int = 5) -> list:
        """Return recent daily analyses (full structured content)."""
        return _get_previous_recaps(days=days, limit=limit)

    @agent.tool_plain
    def tool_get_market_context(reporting_date: str) -> list:
        """Return verified market prices for all assets as of an ISO date (YYYY-MM-DD)."""
        return _get_market_context(reporting_date)

    @agent.tool_plain
    def tool_get_economic_context(reporting_date: str) -> list:
        """Return economic indicator context for an ISO reporting date (YYYY-MM-DD)."""
        return _get_economic_context(reporting_date)

    @agent.tool_plain
    def tool_get_central_bank_context(reporting_date: str) -> list:
        """Return Central Banks page key figures (effective rate, CB prints, next meeting)
        for FRB / ECB / BOJ as of an ISO date (YYYY-MM-DD). Use for policy outlook."""
        return _get_central_bank_context(reporting_date)

    @agent.tool_plain
    def tool_update_daily_recap(
        reporting_date: str,
        title: str = "",
        main_summary: str = "",
        us_summary: str = "",
        eur_summary: str = "",
        jp_summary: str = "",
        additional_summary: str = "",
    ) -> dict:
        """Update the stored DailyRecap for a date.

        Call only after explicit user agreement to a proposal, or when the user
        explicitly orders an update. Never call on ambiguous intent.
        Pass only the fields that should change; leave others empty.
        """
        result = _update_daily_recap(
            reporting_date=reporting_date,
            title=title or None,
            main_summary=main_summary or None,
            us_summary=us_summary or None,
            eur_summary=eur_summary or None,
            jp_summary=jp_summary or None,
            additional_summary=additional_summary or None,
        )
        if result.get("ok"):
            _recap_updated_this_turn.set(True)
        return result


def get_chat_agent() -> Agent:
    """Shared chat agent (same tools + instructions across requests)."""
    global _chat_agent
    if _chat_agent is None:
        if not llm_is_configured():
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        agent = Agent(
            settings.LLM_MODEL_NAME,
            output_type=ChatAnswerOutput,
            instructions=load_instruction("chat_system.md"),
        )
        _register_chat_tools(agent)
        _chat_agent = agent
    return _chat_agent


def ask(
    question: str,
    messages: Optional[List[ChatMessage]] = None,
) -> ChatAskResult:
    """Answer one turn using optional prior messages sent by the client.

    Chat is stateless on the server.
    The DB never stores turns — the client owns history and sends it back each request.
    """
    if not llm_is_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    history: List[ChatMessage] = [
        ChatMessage(role=message["role"], content=message["content"])
        for message in (messages or [])
        if message.get("role") in ("user", "assistant") and message.get("content")
    ][-MAX_CHAT_HISTORY_MESSAGES:]

    prompt_parts = [
        skills_as_prompt_block(),
        "",
        "Conversation so far:",
    ]
    for message in history:
        prompt_parts.append(f"{message['role'].upper()}: {message['content']}")
    prompt_parts.append(f"USER: {question.strip()}")
    prompt_parts.append(
        "Respond clearly. Use tools for recaps, market context, or economic "
        "context. Propose recap edits in the structured fields when helpful; "
        "call tool_update_daily_recap only after explicit user agreement or order. "
        "Only after a recap update is agreed/ordered may you fill "
        "cursor_guidelines_prompt for missing regime logic."
    )
    prompt = "\n".join(prompt_parts)

    updated_token = _recap_updated_this_turn.set(False)
    try:
        result = get_chat_agent().run_sync(prompt)
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
