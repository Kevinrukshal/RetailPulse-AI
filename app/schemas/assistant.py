"""Pydantic contracts for the guarded business assistant."""

from typing import Any

from pydantic import BaseModel, Field

from ai.query_router import AnalyticsIntent


class AssistantQuestion(BaseModel):
    """One bounded natural-language analytics question."""

    question: str = Field(min_length=5, max_length=500)


class AssistantAnswer(BaseModel):
    """Grounded explanation plus the exact structured evidence used."""

    intent: AnalyticsIntent
    answer: str = Field(min_length=1, max_length=4_000)
    data: list[dict[str, Any]]
    sources: list[str]
    model: str
    demonstration_data: bool = True


class AssistantStatus(BaseModel):
    """Non-secret runtime availability information."""

    enabled: bool
    provider: str
    model: str | None
    supported_intents: list[AnalyticsIntent]
