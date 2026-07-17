"""Create Power BI-friendly analytical views.

Revision ID: 0002_analytics_views
Revises: 0001_initial_schema
"""

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0002_analytics_views"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEW_NAMES = (
    "executive_summary",
    "monthly_performance",
    "product_performance",
    "customer_performance",
    "regional_performance",
    "profit_leakage",
)


def upgrade() -> None:
    """Create each view from the versioned SQL source file."""
    views_path = Path(__file__).resolve().parents[2] / "sql" / "views.sql"
    for statement in views_path.read_text(encoding="utf-8").split("-- statement"):
        if statement.strip() and not statement.lstrip().startswith("-- Power BI"):
            op.execute(sa.text(statement.strip().rstrip(";")))


def downgrade() -> None:
    """Drop analytical views in reverse dependency order."""
    for view_name in reversed(VIEW_NAMES):
        op.execute(sa.text(f"DROP VIEW IF EXISTS {view_name}"))
