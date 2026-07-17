"""Persist validation outputs and human- and machine-readable quality reports."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pandas as pd

from etl.validate import ValidationResult


@dataclass(frozen=True)
class QualityOutputPaths:
    """Files generated for one validation run."""

    valid_rows: Path
    rejected_rows: Path
    json_report: Path
    markdown_report: Path


def write_quality_outputs(
    result: ValidationResult,
    *,
    output_root: Path,
    etl_run_id: UUID,
    source_file: Path,
    source_file_hash: str,
    started_at: datetime,
    completed_at: datetime,
) -> QualityOutputPaths:
    """Write validated rows, rejected rows, and quality reports for one run."""
    processed_directory = output_root / "processed"
    rejected_directory = output_root / "rejected"
    processed_directory.mkdir(parents=True, exist_ok=True)
    rejected_directory.mkdir(parents=True, exist_ok=True)

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", source_file.stem).strip("-") or "sales"
    prefix = f"{safe_stem}-{etl_run_id}"
    paths = QualityOutputPaths(
        valid_rows=processed_directory / f"{prefix}-valid.csv",
        rejected_rows=rejected_directory / f"{prefix}-rejected.csv",
        json_report=processed_directory / f"{prefix}-quality.json",
        markdown_report=processed_directory / f"{prefix}-quality.md",
    )

    _csv_ready(result.valid_rows).to_csv(paths.valid_rows, index=False, encoding="utf-8")
    _csv_ready(result.rejected_rows).to_csv(paths.rejected_rows, index=False, encoding="utf-8")

    report = {
        "etl_run_id": str(etl_run_id),
        "source_file": source_file.name,
        "source_file_hash": source_file_hash,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        **result.metrics.to_dict(),
        "quality_score_formula": "round(100 * valid_rows / total_rows, 2)",
    }
    paths.json_report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    paths.markdown_report.write_text(_markdown_report(report), encoding="utf-8")
    return paths


def _csv_ready(data: pd.DataFrame) -> pd.DataFrame:
    """Serialize list-valued audit fields as JSON arrays for CSV output."""
    output = data.copy(deep=True)
    for column in ("validation_warnings", "rejection_reasons"):
        if column in output.columns:
            output[column] = output[column].map(json.dumps)
    return output


def _markdown_report(report: dict[str, object]) -> str:
    """Build a concise quality summary suitable for human review."""
    fields = (
        ("Total rows", "total_rows"),
        ("Valid rows", "valid_rows"),
        ("Rejected rows", "invalid_rows"),
        ("Duplicate rows", "duplicate_rows"),
        ("Invalid dates", "invalid_dates"),
        ("Invalid numeric rows", "invalid_numeric_values"),
        ("Unknown regions", "unknown_regions"),
        ("Unreasonable profit warnings", "unreasonable_profit_rows"),
        ("Quality score", "quality_score"),
    )
    metric_rows = "\n".join(f"| {label} | {report[key]} |" for label, key in fields)
    issues = report.get("issue_counts", {})
    issue_rows = (
        "\n".join(f"| `{reason}` | {count} |" for reason, count in sorted(issues.items()))
        if isinstance(issues, dict) and issues
        else "| None | 0 |"
    )
    return f"""# RetailPulse AI data quality report

**ETL run:** `{report["etl_run_id"]}`  
**Source:** `{report["source_file"]}`  
**SHA-256:** `{report["source_file_hash"]}`  
**Started:** {report["started_at"]}  
**Completed:** {report["completed_at"]}

## Summary

| Metric | Value |
|---|---:|
{metric_rows}

Quality score formula: `{report["quality_score_formula"]}`. A row with multiple issues is
counted once as rejected. Unreasonable profit is a warning and does not reject a row.

## Rejection reasons

| Reason code | Rows |
|---|---:|
{issue_rows}
"""
