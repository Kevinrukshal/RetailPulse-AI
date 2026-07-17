"""Row-level validation with complete, machine-readable rejection reasons."""

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from etl.exceptions import EmptyDatasetError, MissingRequiredColumnsError
from etl.mapping import CANONICAL_COLUMNS

ALLOWED_REGIONS = frozenset({"central", "east", "south", "west"})
UNREASONABLE_PROFIT_ABSOLUTE = 10_000
UNREASONABLE_PROFIT_MULTIPLIER = 5


@dataclass(frozen=True)
class QualityMetrics:
    """Aggregated quality results for one extracted dataset."""

    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    missing_order_ids: int
    missing_customer_ids: int
    missing_product_ids: int
    invalid_dates: int
    negative_sales: int
    invalid_quantities: int
    invalid_discounts: int
    invalid_numeric_values: int
    unknown_regions: int
    unreasonable_profit_rows: int
    quality_score: float
    issue_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    """Valid and rejected rows together with aggregate metrics."""

    valid_rows: pd.DataFrame
    rejected_rows: pd.DataFrame
    metrics: QualityMetrics


def validate_sales_data(data: pd.DataFrame) -> ValidationResult:
    """Validate retail rows without mutating the extracted DataFrame.

    Quality score = round(100 * valid row count / total row count, 2).
    Each rejected row is counted once even when it has several rejection reasons.
    """
    missing_columns = sorted(set(CANONICAL_COLUMNS) - set(data.columns))
    if missing_columns:
        raise MissingRequiredColumnsError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )
    if data.empty:
        raise EmptyDatasetError("Dataset contains no rows to validate")

    working = data.copy(deep=True).reset_index(drop=True)
    working.insert(0, "source_row_number", range(2, len(working) + 2))
    rejection_reasons: list[list[str]] = [[] for _ in range(len(working))]
    validation_warnings: list[list[str]] = [[] for _ in range(len(working))]

    def reject(mask: pd.Series, reason: str) -> None:
        for position, is_invalid in enumerate(mask.fillna(False).tolist()):
            if is_invalid:
                rejection_reasons[position].append(reason)

    missing_order = _missing_text(working["order_id"])
    missing_customer = _missing_text(working["customer_id"])
    missing_product = _missing_text(working["product_id"])
    duplicates = data.reset_index(drop=True).duplicated(keep="first")

    order_dates = pd.to_datetime(working["order_date"], errors="coerce")
    ship_dates = pd.to_datetime(working["ship_date"], errors="coerce")
    invalid_order_dates = order_dates.isna()
    invalid_ship_dates = ship_dates.isna()
    ship_before_order = order_dates.notna() & ship_dates.notna() & (ship_dates < order_dates)

    sales = pd.to_numeric(working["sales"], errors="coerce")
    quantity = pd.to_numeric(working["quantity"], errors="coerce")
    discount = pd.to_numeric(working["discount"], errors="coerce")
    profit = pd.to_numeric(working["profit"], errors="coerce")
    invalid_sales = sales.isna()
    invalid_quantity = quantity.isna()
    invalid_discount = discount.isna()
    invalid_profit = profit.isna()
    negative_sales = sales.notna() & sales.lt(0)
    nonpositive_quantity = quantity.notna() & quantity.le(0)
    discount_out_of_range = discount.notna() & (discount.lt(0) | discount.gt(1))

    normalized_regions = working["region"].astype("string").str.strip().str.casefold()
    unknown_regions = ~normalized_regions.isin(ALLOWED_REGIONS)
    unreasonable_threshold = (
        sales.abs().mul(UNREASONABLE_PROFIT_MULTIPLIER).clip(lower=UNREASONABLE_PROFIT_ABSOLUTE)
    )
    unreasonable_profit = sales.notna() & profit.notna() & profit.abs().gt(unreasonable_threshold)

    reject(missing_order, "missing_order_id")
    reject(missing_customer, "missing_customer_id")
    reject(missing_product, "missing_product_id")
    reject(duplicates, "duplicate_row")
    reject(invalid_order_dates, "invalid_order_date")
    reject(invalid_ship_dates, "invalid_ship_date")
    reject(ship_before_order, "ship_date_before_order_date")
    reject(invalid_sales, "invalid_sales")
    reject(negative_sales, "negative_sales")
    reject(invalid_quantity, "invalid_quantity")
    reject(nonpositive_quantity, "nonpositive_quantity")
    reject(invalid_discount, "invalid_discount")
    reject(discount_out_of_range, "discount_out_of_range")
    reject(invalid_profit, "invalid_profit")
    reject(unknown_regions, "unknown_region")

    for position, is_warning in enumerate(unreasonable_profit.fillna(False).tolist()):
        if is_warning:
            validation_warnings[position].append("unreasonable_profit")

    rejected_mask = pd.Series([bool(reasons) for reasons in rejection_reasons])
    working["validation_warnings"] = validation_warnings
    working["rejection_reasons"] = rejection_reasons
    valid_rows = (
        working.loc[~rejected_mask].drop(columns="rejection_reasons").reset_index(drop=True)
    )
    rejected_rows = working.loc[rejected_mask].reset_index(drop=True)

    reason_names = sorted({reason for reasons in rejection_reasons for reason in reasons})
    issue_counts = {
        reason: sum(reason in reasons for reasons in rejection_reasons) for reason in reason_names
    }
    total_rows = len(working)
    valid_count = len(valid_rows)
    invalid_numeric = invalid_sales | invalid_quantity | invalid_discount | invalid_profit
    invalid_date_rows = invalid_order_dates | invalid_ship_dates | ship_before_order
    metrics = QualityMetrics(
        total_rows=total_rows,
        valid_rows=valid_count,
        invalid_rows=len(rejected_rows),
        duplicate_rows=int(duplicates.sum()),
        missing_order_ids=int(missing_order.sum()),
        missing_customer_ids=int(missing_customer.sum()),
        missing_product_ids=int(missing_product.sum()),
        invalid_dates=int(invalid_date_rows.sum()),
        negative_sales=int(negative_sales.sum()),
        invalid_quantities=int((invalid_quantity | nonpositive_quantity).sum()),
        invalid_discounts=int((invalid_discount | discount_out_of_range).sum()),
        invalid_numeric_values=int(invalid_numeric.sum()),
        unknown_regions=int(unknown_regions.sum()),
        unreasonable_profit_rows=int(unreasonable_profit.sum()),
        quality_score=round(100 * valid_count / total_rows, 2),
        issue_counts=issue_counts,
    )
    return ValidationResult(valid_rows=valid_rows, rejected_rows=rejected_rows, metrics=metrics)


def _missing_text(values: pd.Series) -> pd.Series:
    """Identify null, empty, or whitespace-only identifiers."""
    return values.isna() | values.astype("string").str.strip().eq("").fillna(True)
