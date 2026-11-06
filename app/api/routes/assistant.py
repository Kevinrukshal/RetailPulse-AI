"""Versioned API routes for the guarded AI business assistant."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai.assistant import BusinessAssistant
from ai.provider import AssistantProviderError, Narrator, OpenAINarrator
from ai.query_router import AnalyticsIntent, UnsupportedQuestionError
from app.api.dependencies import get_read_only_session
from app.core.config import get_settings
from app.schemas.assistant import AssistantAnswer, AssistantQuestion, AssistantStatus

router = APIRouter(prefix="/api/v1/assistant", tags=["AI Assistant"])


@lru_cache
def get_narrator() -> Narrator:
    """Create the configured provider lazily only when AI is enabled and called."""
    settings = get_settings()
    if not settings.ai_enabled or not settings.ai_external_sharing_enabled:
        raise AssistantProviderError("AI assistant is disabled")
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return OpenAINarrator(api_key=api_key, model=settings.ai_model or "")


def get_business_assistant(
    session: Annotated[Session, Depends(get_read_only_session)],
) -> BusinessAssistant:
    """Build a request-scoped orchestrator around a read-only session."""
    settings = get_settings()
    if not settings.ai_enabled or not settings.ai_external_sharing_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI assistant is disabled; set AI_ENABLED=true with provider credentials",
        )
    try:
        narrator = get_narrator()
    except AssistantProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return BusinessAssistant(
        session=session,
        narrator=narrator,
        row_limit=settings.ai_row_limit,
        query_timeout_ms=settings.ai_query_timeout_ms,
    )


@router.get("/status", response_model=AssistantStatus)
def assistant_status() -> AssistantStatus:
    """Report availability without exposing credentials."""
    settings = get_settings()
    return AssistantStatus(
        enabled=settings.ai_enabled and settings.ai_external_sharing_enabled,
        provider=settings.ai_provider,
        model=settings.ai_model if settings.ai_enabled else None,
        supported_intents=list(AnalyticsIntent),
    )


@router.post("/query", response_model=AssistantAnswer)
def assistant_query(
    payload: AssistantQuestion,
    assistant: Annotated[BusinessAssistant, Depends(get_business_assistant)],
) -> AssistantAnswer:
    """Answer one supported question using reviewed analytics and grounded narration."""
    try:
        result = assistant.answer(payload.question)
    except UnsupportedQuestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except AssistantProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return AssistantAnswer(
        intent=result.intent,
        answer=result.answer,
        data=result.data,
        sources=result.sources,
        model=result.model,
    )
