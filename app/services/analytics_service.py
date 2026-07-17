"""Read-only, parameterized SQL analytics service."""

from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import AnalyticsFilters

ProductSort = Literal["revenue", "profit", "units"]
CustomerSort = Literal["lifetime_revenue", "lifetime_profit", "purchase_frequency"]


class AnalyticsService:
    """Execute allowlisted analytical queries through one read-only session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(self, filters: AnalyticsFilters) -> dict[str, Any]:
        where, parameters = _fact_filters(filters)
        query = text(
            f"""
            SELECT
                COALESCE(ROUND(SUM(oi.sales), 2), 0) AS total_revenue,
                COALESCE(ROUND(SUM(oi.profit), 2), 0) AS total_profit,
                COALESCE(ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6), 0)
                    AS profit_margin,
                COUNT(DISTINCT o.order_id)::integer AS total_orders,
                COUNT(DISTINCT o.customer_id)::integer AS unique_customers,
                COALESCE(
                    ROUND(SUM(oi.sales) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2), 0
                ) AS average_order_value,
                COALESCE(
                    ROUND(SUM(oi.quantity)::numeric / NULLIF(COUNT(DISTINCT o.order_id), 0), 2),
                    0
                ) AS average_units_per_order
            FROM order_items AS oi
            JOIN orders AS o ON o.order_id = oi.order_id
            JOIN customers AS c ON c.customer_id = o.customer_id
            JOIN products AS p ON p.product_id = oi.product_id
            WHERE {where}
            """
        )
        return dict(self.session.execute(query, parameters).mappings().one())

    def monthly(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = _fact_filters(filters)
        query = text(
            f"""
            WITH monthly AS (
                SELECT
                    DATE_TRUNC('month', o.order_date)::date AS month_start,
                    SUM(oi.sales) AS revenue,
                    SUM(oi.profit) AS profit,
                    SUM(oi.quantity) AS units,
                    COUNT(DISTINCT o.order_id) AS orders,
                    COUNT(DISTINCT o.customer_id) AS customers
                FROM order_items AS oi
                JOIN orders AS o ON o.order_id = oi.order_id
                JOIN customers AS c ON c.customer_id = o.customer_id
                JOIN products AS p ON p.product_id = oi.product_id
                WHERE {where}
                GROUP BY DATE_TRUNC('month', o.order_date)::date
            ), compared AS (
                SELECT
                    monthly.*,
                    LAG(revenue, 1) OVER (ORDER BY month_start) AS previous_month,
                    LAG(revenue, 12) OVER (ORDER BY month_start) AS previous_year
                FROM monthly
            )
            SELECT
                month_start,
                ROUND(revenue, 2) AS revenue,
                ROUND(profit, 2) AS profit,
                ROUND(profit / NULLIF(revenue, 0), 6) AS profit_margin,
                units::integer,
                orders::integer,
                customers::integer,
                ROUND(100 * (revenue - previous_month) / NULLIF(previous_month, 0), 2)
                    AS month_over_month_growth_pct,
                ROUND(100 * (revenue - previous_year) / NULLIF(previous_year, 0), 2)
                    AS year_over_year_growth_pct
            FROM compared
            ORDER BY month_start
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def products(
        self,
        filters: AnalyticsFilters,
        *,
        limit: int,
        sort_by: ProductSort,
        loss_making_only: bool = False,
    ) -> list[dict[str, Any]]:
        where, parameters = _fact_filters(filters)
        sort_columns = {"revenue": "revenue", "profit": "profit", "units": "units"}
        direction = "ASC" if loss_making_only else "DESC"
        having = "HAVING SUM(oi.profit) < 0" if loss_making_only else ""
        parameters["limit"] = limit
        query = text(
            f"""
            SELECT
                p.product_id,
                p.product_name,
                p.category,
                p.subcategory,
                ROUND(SUM(oi.sales), 2) AS revenue,
                ROUND(SUM(oi.profit), 2) AS profit,
                ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin,
                SUM(oi.quantity)::integer AS units,
                COUNT(DISTINCT o.order_id)::integer AS orders,
                ROUND(AVG(oi.discount), 6) AS average_discount
            FROM order_items AS oi
            JOIN orders AS o ON o.order_id = oi.order_id
            JOIN customers AS c ON c.customer_id = o.customer_id
            JOIN products AS p ON p.product_id = oi.product_id
            WHERE {where}
            GROUP BY p.product_id, p.product_name, p.category, p.subcategory
            {having}
            ORDER BY {sort_columns[sort_by]} {direction}, p.product_id
            LIMIT :limit
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def customers(
        self,
        *,
        region: str | None,
        limit: int,
        sort_by: CustomerSort,
    ) -> list[dict[str, Any]]:
        sort_columns = {
            "lifetime_revenue": "lifetime_revenue",
            "lifetime_profit": "lifetime_profit",
            "purchase_frequency": "purchase_frequency",
        }
        parameters: dict[str, Any] = {"limit": limit}
        where = "TRUE"
        if region:
            where = "LOWER(region) = LOWER(:region)"
            parameters["region"] = region
        query = text(
            f"""
            SELECT
                customer_id, customer_name, segment, region, lifetime_revenue,
                lifetime_profit, purchase_frequency, last_purchase_date,
                average_order_value, recency_days, rfm_segment
            FROM customer_performance
            WHERE {where}
            ORDER BY {sort_columns[sort_by]} DESC, customer_id
            LIMIT :limit
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def customer_segments(self, *, region: str | None) -> list[dict[str, Any]]:
        parameters: dict[str, Any] = {}
        where = "TRUE"
        if region:
            where = "LOWER(region) = LOWER(:region)"
            parameters["region"] = region
        query = text(
            f"""
            SELECT
                rfm_segment,
                COUNT(*)::integer AS customers,
                ROUND(SUM(lifetime_revenue), 2) AS revenue,
                ROUND(SUM(lifetime_profit), 2) AS profit
            FROM customer_performance
            WHERE {where}
            GROUP BY rfm_segment
            ORDER BY revenue DESC
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def regions(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        where, parameters = _fact_filters(filters, include_region=False)
        query = text(
            f"""
            SELECT
                c.region,
                ROUND(SUM(oi.sales), 2) AS revenue,
                ROUND(SUM(oi.profit), 2) AS profit,
                ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin,
                COUNT(DISTINCT o.order_id)::integer AS orders,
                COUNT(DISTINCT o.customer_id)::integer AS customers,
                SUM(oi.quantity)::integer AS units
            FROM order_items AS oi
            JOIN orders AS o ON o.order_id = oi.order_id
            JOIN customers AS c ON c.customer_id = o.customer_id
            JOIN products AS p ON p.product_id = oi.product_id
            WHERE {where}
            GROUP BY c.region
            ORDER BY revenue DESC, c.region
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def leakage(self, filters: AnalyticsFilters, *, limit: int) -> list[dict[str, Any]]:
        conditions = ["TRUE"]
        parameters: dict[str, Any] = {"limit": limit}
        fields = {
            "start_date": "order_date >= :start_date",
            "end_date": "order_date <= :end_date",
            "region": "LOWER(region) = LOWER(:region)",
            "category": "LOWER(category) = LOWER(:category)",
            "subcategory": "LOWER(subcategory) = LOWER(:subcategory)",
        }
        for field, condition in fields.items():
            value = getattr(filters, field)
            if value is not None:
                conditions.append(condition)
                parameters[field] = value
        query = text(
            f"""
            SELECT * FROM profit_leakage
            WHERE {" AND ".join(conditions)}
            ORDER BY profit ASC, sales DESC, order_item_key
            LIMIT :limit
            """
        )
        return _mapping_rows(self.session.execute(query, parameters))

    def latest_quality(self) -> dict[str, Any]:
        query = text(
            """
            SELECT
                er.etl_run_id, er.source_file, er.started_at, er.completed_at,
                er.total_rows, er.valid_rows, er.invalid_rows, er.quality_score,
                dqr.issue_counts
            FROM etl_runs AS er
            JOIN data_quality_results AS dqr ON dqr.etl_run_id = er.etl_run_id
            WHERE er.status = 'completed'
            ORDER BY er.completed_at DESC
            LIMIT 1
            """
        )
        row = self.session.execute(query).mappings().one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No completed ETL quality result exists",
            )
        return dict(row)

    def etl_runs(self, *, limit: int, offset: int) -> dict[str, Any]:
        total = self.session.execute(text("SELECT COUNT(*) FROM etl_runs")).scalar_one()
        rows = self.session.execute(
            text(
                """
                SELECT
                    etl_run_id, source_file, status, started_at, completed_at,
                    duration_seconds, total_rows, valid_rows, invalid_rows,
                    quality_score, error_details
                FROM etl_runs
                ORDER BY started_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        )
        return {"items": _mapping_rows(rows), "total": total, "limit": limit, "offset": offset}


def _fact_filters(
    filters: AnalyticsFilters,
    *,
    include_region: bool = True,
) -> tuple[str, dict[str, Any]]:
    conditions = ["TRUE"]
    parameters: dict[str, Any] = {}
    fields = {
        "start_date": "o.order_date >= :start_date",
        "end_date": "o.order_date <= :end_date",
        "category": "LOWER(p.category) = LOWER(:category)",
        "subcategory": "LOWER(p.subcategory) = LOWER(:subcategory)",
    }
    if include_region:
        fields["region"] = "LOWER(c.region) = LOWER(:region)"
    for field, condition in fields.items():
        value = getattr(filters, field)
        if value is not None:
            conditions.append(condition)
            parameters[field] = value
    return " AND ".join(conditions), parameters


def _mapping_rows(result: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in result.mappings().all()]
