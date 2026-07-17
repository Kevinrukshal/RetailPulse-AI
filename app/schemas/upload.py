"""Contracts for browser-driven sales file ingestion."""

from pydantic import BaseModel


class UploadResult(BaseModel):
    """ETL outcome returned after a CSV or XLSX upload."""

    etl_run_id: str
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    quality_score: float
    order_items_inserted: int
    message: str
