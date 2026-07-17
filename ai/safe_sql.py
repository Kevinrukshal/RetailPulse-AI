"""Fixed SQL catalog and bounded read-only execution for the AI assistant."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ai.query_router import AnalyticsIntent


@dataclass(frozen=True)
class ApprovedQuery:
    """One reviewed query and the reporting objects it relies on."""

    sql: str
    sources: tuple[str, ...]


APPROVED_QUERIES = {
    AnalyticsIntent.LOSS_PRODUCTS: ApprovedQuery(
        """SELECT product_name, category, ROUND(SUM(sales), 2) AS revenue,
                  ROUND(SUM(profit), 2) AS profit,
                  ROUND(SUM(profit) / NULLIF(SUM(sales), 0), 6) AS profit_margin,
                  ROUND(AVG(discount), 6) AS average_discount,
                  COUNT(*)::integer AS loss_making_lines
           FROM profit_leakage WHERE leakage_reason = 'Loss-making line'
           GROUP BY product_id, product_name, category
           ORDER BY profit ASC, product_id LIMIT :limit""",
        ("profit_leakage",),
    ),
    AnalyticsIntent.REGION_MARGIN: ApprovedQuery(
        """SELECT region, revenue, profit, profit_margin, orders, customers
           FROM regional_performance ORDER BY profit_margin DESC, region LIMIT :limit""",
        ("regional_performance",),
    ),
    AnalyticsIntent.REVENUE_LAST_QUARTER: ApprovedQuery(
        """WITH boundary AS (
               SELECT DATE_TRUNC('quarter', MAX(order_date))::date AS current_quarter FROM orders
           ), period AS (
               SELECT (current_quarter - INTERVAL '3 months')::date AS period_start,
                      (current_quarter - INTERVAL '1 day')::date AS period_end FROM boundary
           )
           SELECT period_start, period_end, ROUND(COALESCE(SUM(oi.sales), 0), 2) AS revenue,
                  ROUND(COALESCE(SUM(oi.profit), 0), 2) AS profit,
                  COUNT(DISTINCT o.order_id)::integer AS orders
           FROM period LEFT JOIN orders o
             ON o.order_date BETWEEN period.period_start AND period.period_end
           LEFT JOIN order_items oi ON oi.order_id = o.order_id
           GROUP BY period_start, period_end LIMIT :limit""",
        ("orders", "order_items"),
    ),
    AnalyticsIntent.TOP_CUSTOMERS: ApprovedQuery(
        """SELECT customer_name, segment, region, lifetime_revenue, lifetime_profit,
                  purchase_frequency, average_order_value, rfm_segment
           FROM customer_performance
           ORDER BY lifetime_profit DESC, customer_id LIMIT :limit""",
        ("customer_performance",),
    ),
    AnalyticsIntent.DISCOUNT_IMPACT: ApprovedQuery(
        """SELECT CASE WHEN discount = 0 THEN 'No discount'
                        WHEN discount <= 0.10 THEN 'Low (0-10%)'
                        WHEN discount <= 0.20 THEN 'Medium (10-20%)'
                        ELSE 'High (>20%)' END AS discount_band,
                  COUNT(*)::integer AS lines, ROUND(SUM(sales), 2) AS revenue,
                  ROUND(SUM(profit), 2) AS profit,
                  ROUND(SUM(profit) / NULLIF(SUM(sales), 0), 6) AS profit_margin,
                  ROUND(AVG(discount), 6) AS average_discount
           FROM order_items GROUP BY discount_band
           ORDER BY average_discount LIMIT :limit""",
        ("order_items",),
    ),
    AnalyticsIntent.CATEGORY_INVESTIGATION: ApprovedQuery(
        """SELECT category, ROUND(SUM(revenue), 2) AS revenue,
                  ROUND(SUM(profit), 2) AS profit,
                  ROUND(SUM(profit) / NULLIF(SUM(revenue), 0), 6) AS profit_margin,
                  COUNT(*)::integer AS products,
                  COUNT(*) FILTER (WHERE is_loss_making)::integer AS loss_making_products
           FROM product_performance GROUP BY category
           ORDER BY profit_margin ASC, category LIMIT :limit""",
        ("product_performance",),
    ),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def execute_approved_query(
    session: Session,
    intent: AnalyticsIntent,
    *,
    row_limit: int,
    timeout_ms: int,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Execute one catalog query with read-only mode, timeout, and a hard result cap."""
    if not 1 <= row_limit <= 20:
        raise ValueError("AI row limit must be between 1 and 20")
    if not 100 <= timeout_ms <= 10_000:
        raise ValueError("AI query timeout must be between 100 and 10000 milliseconds")

    approved = APPROVED_QUERIES[intent]
    session.execute(text("SET TRANSACTION READ ONLY"))
    session.execute(
        text("SELECT set_config('statement_timeout', :timeout, true)"),
        {"timeout": f"{timeout_ms}ms"},
    )
    rows = session.execute(text(approved.sql), {"limit": row_limit}).mappings().all()
    result = [{key: _json_value(value) for key, value in row.items()} for row in rows]
    if len(result) > row_limit:
        raise RuntimeError("Approved query exceeded its row limit")
    return result, approved.sources
