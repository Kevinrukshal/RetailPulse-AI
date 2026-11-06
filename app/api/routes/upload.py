"""Size-limited browser upload endpoint for the local analytics application."""

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.schemas.upload import UploadResult
from etl.exceptions import ExtractionError, ValidationError
from etl.pipeline import run_pipeline

router = APIRouter(prefix="/api/v1", tags=["Data Upload"])
UPLOAD_ROOT = Path("data/raw/uploads")
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


def _validate_filename(filename: str) -> tuple[str, str]:
    """Reject path components and return a safe basename and extension."""
    cleaned = filename.strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Filename must be a plain CSV or XLSX basename",
        )
    suffix = Path(cleaned).suffix.casefold()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .csv and .xlsx files are supported",
        )
    return cleaned, suffix


@router.post("/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_sales_file(
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
) -> UploadResult:
    """Stream one bounded file to a private temporary path and run the existing ETL."""
    settings = get_settings()
    if not settings.upload_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Browser file upload is disabled",
        )
    safe_name, _ = _validate_filename(filename)
    content_length = request.headers.get("content-length")
    try:
        declared_size = int(content_length) if content_length else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Content-Length header",
        ) from exc
    if declared_size is not None and declared_size > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.upload_max_mb:g} MB limit",
        )

    upload_directory = UPLOAD_ROOT / uuid4().hex
    upload_path = upload_directory / safe_name
    upload_directory.mkdir(parents=True, exist_ok=False)
    bytes_written = 0
    try:
        with upload_path.open("wb") as destination:
            async for chunk in request.stream():
                bytes_written += len(chunk)
                if bytes_written > settings.upload_max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File exceeds the {settings.upload_max_mb:g} MB limit",
                    )
                destination.write(chunk)
        if bytes_written == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Uploaded file is empty",
            )
        try:
            result = await run_in_threadpool(run_pipeline, upload_path)
        except (ExtractionError, ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The file could not be processed. Check its format and required columns.",
            ) from exc
    finally:
        shutil.rmtree(upload_directory, ignore_errors=True)

    return UploadResult(
        etl_run_id=str(result.etl_run_id),
        filename=safe_name,
        total_rows=result.total_rows,
        valid_rows=result.valid_rows,
        invalid_rows=result.invalid_rows,
        quality_score=result.quality_score,
        order_items_inserted=result.load.order_items_inserted,
        message=(
            f"Processed {result.total_rows} rows: {result.valid_rows} valid, "
            f"{result.invalid_rows} rejected, {result.load.order_items_inserted} new sales lines."
        ),
    )
