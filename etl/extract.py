"""Extract retail sales records from supported local file formats."""

import logging
from collections.abc import Mapping
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException
from pandas.errors import EmptyDataError, ParserError

from etl.exceptions import (
    DataEncodingError,
    EmptyDataFileError,
    NoUsableWorksheetError,
    SourceFileNotFoundError,
    UnreadableDataFileError,
    UnsupportedFileTypeError,
)
from etl.mapping import apply_column_mapping

LOGGER = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = frozenset({".csv", ".xlsx"})


def extract_sales_data(
    file_path: Path,
    *,
    column_mapping: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Read a CSV or XLSX source and return an independently owned DataFrame."""
    path = Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        raise SourceFileNotFoundError(f"Sales data file does not exist: {path}")

    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported sales data extension '{extension or '<none>'}'; expected {supported}"
        )
    if path.stat().st_size == 0:
        raise EmptyDataFileError(f"Sales data file is empty: {path}")

    data = _read_csv(path) if extension == ".csv" else _read_excel(path)
    if data.empty or len(data.columns) == 0:
        raise EmptyDataFileError(f"Sales data file contains no rows: {path}")

    mapped = apply_column_mapping(data, column_mapping)
    LOGGER.info(
        "sales_data_extracted",
        extra={
            "source_file": path.name,
            "source_type": extension,
            "row_count": len(mapped),
            "columns": list(mapped.columns),
        },
    )
    return mapped


def _read_csv(path: Path) -> pd.DataFrame:
    """Read one UTF-8 CSV with domain-specific error translation."""
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DataEncodingError(f"CSV is not valid UTF-8: {path}") from exc
    except EmptyDataError as exc:
        raise EmptyDataFileError(f"CSV contains no columns or rows: {path}") from exc
    except (OSError, ParserError) as exc:
        raise UnreadableDataFileError(f"CSV could not be read: {path}") from exc


def _read_excel(path: Path) -> pd.DataFrame:
    """Return the first non-empty worksheet in an XLSX workbook."""
    try:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            for sheet_name in workbook.sheet_names:
                worksheet = pd.read_excel(workbook, sheet_name=sheet_name)
                if not worksheet.empty and len(worksheet.columns) > 0:
                    LOGGER.info(
                        "excel_worksheet_selected",
                        extra={"source_file": path.name, "worksheet": sheet_name},
                    )
                    return worksheet
    except (BadZipFile, InvalidFileException, OSError, ValueError) as exc:
        raise UnreadableDataFileError(f"Excel workbook could not be read: {path}") from exc

    raise NoUsableWorksheetError(f"Excel workbook has no usable worksheets: {path}")
