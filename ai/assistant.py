"""Grounded orchestration from user question to reviewed analytics and narration."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ai.provider import Narrator
from ai.query_router import AnalyticsIntent, classify_question
from ai.rag import retrieve_context
from ai.safe_sql import execute_approved_query


@dataclass(frozen=True)
class AssistantResult:
    """Validated evidence and provider explanation returned to the API layer."""

    intent: AnalyticsIntent
    answer: str
    data: list[dict[str, Any]]
    sources: list[str]
    model: str


class BusinessAssistant:
    """Coordinate deterministic routing, approved SQL, retrieval, and narration."""

    def __init__(
        self,
        *,
        session: Session,
        narrator: Narrator,
        row_limit: int,
        query_timeout_ms: int,
    ) -> None:
        self._session = session
        self._narrator = narrator
        self._row_limit = row_limit
        self._query_timeout_ms = query_timeout_ms

    def answer(self, question: str) -> AssistantResult:
        """Answer one supported question from database and documentation evidence only."""
        intent = classify_question(question)
        data, database_sources = execute_approved_query(
            self._session,
            intent,
            row_limit=self._row_limit,
            timeout_ms=self._query_timeout_ms,
        )
        context = retrieve_context(question)
        answer = self._narrator.explain(
            question=question,
            intent=intent,
            data=data,
            context=context,
        )
        sources = [f"database:{source}" for source in database_sources]
        sources.extend(f"repository:{item.source}" for item in context)
        return AssistantResult(
            intent=intent,
            answer=answer,
            data=data,
            sources=list(dict.fromkeys(sources)),
            model=self._narrator.model_name,
        )
