"""Extract retail sales records from supported local file formats."""

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

import pandas as pd
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import iterparse
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
MAX_ROWS = 100_000
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 1000
MAX_COLUMNS = 256
MAX_CELLS = 2_000_000

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
    if len(data) > MAX_ROWS:
        raise UnreadableDataFileError("The file exceeds the row limit")
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
        return pd.read_csv(path, encoding="utf-8", nrows=MAX_ROWS + 1)
    except UnicodeDecodeError as exc:
        raise DataEncodingError(f"CSV is not valid UTF-8: {path}") from exc
    except EmptyDataError as exc:
        raise EmptyDataFileError(f"CSV contains no columns or rows: {path}") from exc
    except (OSError, ParserError) as exc:
        raise UnreadableDataFileError(f"CSV could not be read: {path}") from exc


def _read_excel(path: Path) -> pd.DataFrame:
    """Return the first non-empty worksheet in an XLSX workbook."""
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_ZIP_ENTRIES
                or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES
            ):
                raise UnreadableDataFileError("Workbook exceeds expanded archive limits")
            total_cells = 0
            for entry in entries:
                if not entry.filename.startswith("xl/worksheets/") or not entry.filename.endswith(
                    ".xml"
                ):
                    continue
                rows = 0
                with archive.open(entry) as source:
                    for _, element in iterparse(source, events=("end",)):
                        tag = element.tag.rsplit("}", 1)[-1]
                        if tag == "row":
                            rows += 1
                            if rows > MAX_ROWS + 1:
                                raise UnreadableDataFileError("Workbook exceeds row limit")
                        elif tag == "c":
                            total_cells += 1
                            reference = element.get("r", "")
                            match = re.fullmatch(r"([A-Z]+)([0-9]+)", reference)
                            if not match:
                                raise UnreadableDataFileError(
                                    "Workbook has invalid cell references"
                                )
                            column = 0
                            for letter in match[1]:
                                column = column * 26 + ord(letter) - ord("A") + 1
                            if (
                                column > MAX_COLUMNS
                                or int(match[2]) > MAX_ROWS + 1
                                or total_cells > MAX_CELLS
                            ):
                                raise UnreadableDataFileError("Workbook exceeds cell bounds")
                        element.clear()
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            for sheet_name in workbook.sheet_names:
                worksheet = pd.read_excel(workbook, sheet_name=sheet_name, nrows=MAX_ROWS + 1)
                if not worksheet.empty and len(worksheet.columns) > 0:
                    LOGGER.info(
                        "excel_worksheet_selected",
                        extra={"source_file": path.name, "worksheet": sheet_name},
                    )
                    return worksheet
    except (
        BadZipFile,
        InvalidFileException,
        OSError,
        ValueError,
        DefusedXmlException,
        ParseError,
    ) as exc:
        raise UnreadableDataFileError(f"Excel workbook could not be read: {path}") from exc

    raise NoUsableWorksheetError(f"Excel workbook has no usable worksheets: {path}")
