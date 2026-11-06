"""Command-line orchestration for the complete RetailPulse ETL workflow."""

import argparse
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import get_engine
from etl.exceptions import ExtractionError, ValidationError
from etl.extract import extract_sales_data
from etl.load import (
    LoadSummary,
    create_etl_run,
    load_pipeline_results,
    mark_etl_run_failed,
)
from etl.quality_report import QualityOutputPaths, write_quality_outputs
from etl.transform import transform_sales_data
from etl.validate import validate_sales_data

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Successful pipeline outcome returned to callers and the CLI."""

    etl_run_id: UUID
    source_file_hash: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    quality_score: float
    load: LoadSummary
    outputs: QualityOutputPaths


def run_pipeline(
    file_path: Path,
    *,
    output_root: Path = Path("data"),
    column_mapping: Mapping[str, str] | None = None,
    engine: Engine | None = None,
) -> PipelineResult:
    """Run extraction through transactional loading and return the audited result."""
    source_path = Path(file_path)
    started_at = datetime.now(UTC)
    etl_run_id = uuid4()
    source_hash = file_sha256(source_path)
    database_engine = engine or get_engine()
    run_created = False

    try:
        with Session(database_engine) as session:
            create_etl_run(
                session,
                etl_run_id=etl_run_id,
                source_file=source_path.name,
                source_file_hash=source_hash,
                started_at=started_at,
            )
            run_created = True

        extracted = extract_sales_data(source_path, column_mapping=column_mapping)
        validation = validate_sales_data(extracted)
        transformed = transform_sales_data(
            validation.valid_rows,
            etl_run_id=etl_run_id,
            source_file_hash=source_hash,
            loaded_at=started_at,
        )
        report_time = datetime.now(UTC)
        outputs = write_quality_outputs(
            validation,
            output_root=output_root,
            etl_run_id=etl_run_id,
            source_file=source_path,
            source_file_hash=source_hash,
            started_at=started_at,
            completed_at=report_time,
        )

        with Session(database_engine) as session, session.begin():
            completed_at = datetime.now(UTC)
            load_summary = load_pipeline_results(
                session,
                transformed_rows=transformed,
                validation=validation,
                etl_run_id=etl_run_id,
                started_at=started_at,
                completed_at=completed_at,
            )

        metrics = validation.metrics
        LOGGER.info(
            "etl_pipeline_completed",
            extra={
                "etl_run_id": str(etl_run_id),
                "source_file": source_path.name,
                "total_rows": metrics.total_rows,
                "valid_rows": metrics.valid_rows,
                "invalid_rows": metrics.invalid_rows,
                "quality_score": metrics.quality_score,
                "order_items_inserted": load_summary.order_items_inserted,
            },
        )
        return PipelineResult(
            etl_run_id=etl_run_id,
            source_file_hash=source_hash,
            total_rows=metrics.total_rows,
            valid_rows=metrics.valid_rows,
            invalid_rows=metrics.invalid_rows,
            quality_score=metrics.quality_score,
            load=load_summary,
            outputs=outputs,
        )
    except Exception as exc:
        if run_created:
            _record_failure(database_engine, etl_run_id, started_at, exc)
        LOGGER.error(
            "etl_pipeline_failed",
            extra={"etl_run_id": str(etl_run_id), "source_file": source_path.name},
        )
        raise


def file_sha256(file_path: Path) -> str:
    """Calculate a source file hash without loading the whole file into memory."""
    digest = sha256()
    with Path(file_path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_failure(
    engine: Engine, etl_run_id: UUID, started_at: datetime, error: Exception
) -> None:
    """Best-effort failure audit after the main transaction has rolled back."""
    completed_at = datetime.now(UTC)
    try:
        with Session(engine) as session:
            mark_etl_run_failed(
                session,
                etl_run_id=etl_run_id,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                error_details=type(error).__name__,
            )
    except SQLAlchemyError:
        LOGGER.error("etl_failure_status_could_not_be_saved", extra={"etl_run_id": str(etl_run_id)})


def _load_column_mapping(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
    ):
        raise ValueError("Column mapping JSON must be an object of string source/target pairs")
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description="Run the RetailPulse sales ETL pipeline")
    parser.add_argument("--file", required=True, type=Path, help="CSV or XLSX source file")
    parser.add_argument(
        "--output-root", type=Path, default=Path("data"), help="Quality artifact root"
    )
    parser.add_argument("--column-map", type=Path, help="Optional source-to-canonical JSON map")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the CLI and return a documented process exit code."""
    configure_logging(get_settings().log_level)
    options = build_parser().parse_args(arguments)
    try:
        result = run_pipeline(
            options.file,
            output_root=options.output_root,
            column_mapping=_load_column_mapping(options.column_map),
        )
    except (ExtractionError, ValidationError, FileNotFoundError, ValueError) as exc:
        print(f"ETL input error: {exc}")
        return 2
    except SQLAlchemyError as exc:
        print(f"ETL database error: {exc}")
        return 3
    except Exception as exc:
        print(f"ETL failed: {exc}")
        return 1

    print(
        f"ETL run {result.etl_run_id} completed: {result.valid_rows} valid, "
        f"{result.invalid_rows} rejected, quality score {result.quality_score:.2f}, "
        f"{result.load.order_items_inserted} new order items."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
