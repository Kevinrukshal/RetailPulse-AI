"""Deterministic natural-language routing to approved analytics intents."""

import re
from enum import StrEnum


class AnalyticsIntent(StrEnum):
    """Questions supported by fixed, reviewed analytics templates."""

    LOSS_PRODUCTS = "loss_products"
    REGION_MARGIN = "region_margin"
    REVENUE_LAST_QUARTER = "revenue_last_quarter"
    TOP_CUSTOMERS = "top_customers"
    DISCOUNT_IMPACT = "discount_impact"
    CATEGORY_INVESTIGATION = "category_investigation"


class UnsupportedQuestionError(ValueError):
    """Raised when a question cannot be mapped to an approved intent."""


INTENT_PATTERNS: tuple[tuple[AnalyticsIntent, tuple[str, ...]], ...] = (
    (
        AnalyticsIntent.LOSS_PRODUCTS,
        (r"products?.*(lost|loss|losing|negative profit)", r"(lost|loss).*(products?)"),
    ),
    (
        AnalyticsIntent.REGION_MARGIN,
        (r"regions?.*(highest|best|top).*(margin)", r"(margin).*(regions?)"),
    ),
    (
        AnalyticsIntent.REVENUE_LAST_QUARTER,
        (r"revenue.*(last|previous).*(quarter)", r"(last|previous).*(quarter).*revenue"),
    ),
    (
        AnalyticsIntent.TOP_CUSTOMERS,
        (r"customers?.*(most|highest|top).*(profit)", r"(profit).*(customers?)"),
    ),
    (
        AnalyticsIntent.DISCOUNT_IMPACT,
        (r"discounts?.*(profit|margin|profitability)", r"(profit|margin).*(discounts?)"),
    ),
    (
        AnalyticsIntent.CATEGORY_INVESTIGATION,
        (
            r"categor(y|ies).*(investigate|weak|worst|lowest)",
            r"(investigate|weak|worst|lowest).*(categor(y|ies))",
        ),
    ),
)


def classify_question(question: str) -> AnalyticsIntent:
    """Map a bounded question to one approved intent without involving an LLM."""
    normalized = " ".join(question.casefold().split())
    for intent, patterns in INTENT_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return intent
    raise UnsupportedQuestionError(
        "Question is outside the approved analytics catalog. Ask about loss-making products, "
        "regional margin, last-quarter revenue, profitable customers, discount impact, or "
        "categories to investigate."
    )
