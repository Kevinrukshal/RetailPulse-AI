"""Small local retriever for approved RetailPulse documentation."""

import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPROVED_DOCUMENTS = (
    Path("docs/business_insights.md"),
    Path("docs/architecture.md"),
    Path("docs/database.md"),
    Path("docs/powerbi_setup.md"),
    Path("dashboard/powerbi_data_dictionary.md"),
)
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]+")


@dataclass(frozen=True)
class RetrievedContext:
    """One bounded documentation excerpt and its repository source."""

    source: str
    content: str


def _tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.casefold()))


def _chunks(relative_path: Path) -> list[RetrievedContext]:
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT not in path.parents or not path.is_file():
        return []
    sections = re.split(r"(?=^#{1,3} )", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return [
        RetrievedContext(source=relative_path.as_posix(), content=section.strip()[:1_500])
        for section in sections
        if section.strip()
    ]


def retrieve_context(question: str, *, limit: int = 3) -> list[RetrievedContext]:
    """Rank allowlisted local documentation by lexical overlap with the question."""
    if not 1 <= limit <= 5:
        raise ValueError("RAG context limit must be between 1 and 5")
    query_tokens = _tokens(question)
    candidates = [chunk for document in APPROVED_DOCUMENTS for chunk in _chunks(document)]
    ranked = sorted(
        candidates,
        key=lambda chunk: (len(query_tokens & _tokens(chunk.content)), chunk.source),
        reverse=True,
    )
    relevant = [chunk for chunk in ranked if query_tokens & _tokens(chunk.content)]
    return relevant[:limit]
