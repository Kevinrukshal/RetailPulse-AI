"""Unit tests for retail source extraction and column mapping."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from etl.exceptions import (
    ColumnMappingError,
    DataEncodingError,
    EmptyDataFileError,
    NoUsableWorksheetError,
    SourceFileNotFoundError,
    UnreadableDataFileError,
    UnsupportedFileTypeError,
)
from etl.extract import extract_sales_data
from etl.mapping import apply_column_mapping

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_extracts_csv_and_logs_shape(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        result = extract_sales_data(FIXTURES / "valid_sales.csv")

    assert len(result) == 12
    assert {"order_id", "product_id", "sales"}.issubset(result.columns)
    assert "sales_data_extracted" in caplog.text


def test_extracts_first_usable_excel_worksheet(tmp_path: Path) -> None:
    workbook = tmp_path / "sales.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame().to_excel(writer, sheet_name="Instructions", index=False)
        pd.DataFrame({"Order ID": ["A-1"], "Sales": [25.0]}).to_excel(
            writer, sheet_name="Sales", index=False
        )

    result = extract_sales_data(workbook)

    assert result.to_dict(orient="records") == [{"order_id": "A-1", "sales": 25}]


def test_applies_configurable_column_mapping(tmp_path: Path) -> None:
    source = tmp_path / "aliased.csv"
    source.write_text("Transaction Number,Revenue\nA-1,19.95\n", encoding="utf-8")

    result = extract_sales_data(
        source,
        column_mapping={"Transaction Number": "order_id", "Revenue": "sales"},
    )

    assert list(result.columns) == ["order_id", "sales"]


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SourceFileNotFoundError, match="does not exist"):
        extract_sales_data(tmp_path / "missing.csv")


def test_rejects_unsupported_extension(tmp_path: Path) -> None:
    source = tmp_path / "sales.json"
    source.write_text("[]", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError, match="Unsupported"):
        extract_sales_data(source)


def test_rejects_empty_csv(tmp_path: Path) -> None:
    source = tmp_path / "empty.csv"
    source.touch()

    with pytest.raises(EmptyDataFileError, match="empty"):
        extract_sales_data(source)


def test_rejects_non_utf8_csv(tmp_path: Path) -> None:
    source = tmp_path / "encoded.csv"
    source.write_bytes(b"order_id,customer_name\nA-1,\xff\n")

    with pytest.raises(DataEncodingError, match="UTF-8"):
        extract_sales_data(source)


def test_rejects_unreadable_excel(tmp_path: Path) -> None:
    source = tmp_path / "broken.xlsx"
    source.write_text("not an Excel archive", encoding="utf-8")

    with pytest.raises(UnreadableDataFileError, match="could not be read"):
        extract_sales_data(source)


def test_rejects_excel_without_usable_worksheet(tmp_path: Path) -> None:
    source = tmp_path / "empty.xlsx"
    pd.DataFrame().to_excel(source, index=False, engine="openpyxl")

    with pytest.raises(NoUsableWorksheetError, match="no usable worksheets"):
        extract_sales_data(source)


def test_rejects_ambiguous_or_noncanonical_mapping() -> None:
    source = pd.DataFrame(columns=["Order", "Transaction"])

    with pytest.raises(ColumnMappingError, match="same field"):
        apply_column_mapping(source, {"Order": "order_id", "Transaction": "order_id"})
    with pytest.raises(ColumnMappingError, match="not canonical"):
        apply_column_mapping(source, {"Order": "unknown_target"})


def test_security_row_bound_rejects_whole_file(tmp_path, monkeypatch):
    from etl import extract
    from etl.exceptions import UnreadableDataFileError

    monkeypatch.setattr(extract, "MAX_ROWS", 2)
    path = tmp_path / "bounded.csv"
    path.write_text("a\n1\n2\n3\n")
    with pytest.raises(UnreadableDataFileError, match="row limit"):
        extract.extract_sales_data(path)


def test_security_expanded_zip_bound(tmp_path, monkeypatch):
    from zipfile import ZIP_DEFLATED, ZipFile

    from etl import extract
    from etl.exceptions import UnreadableDataFileError

    monkeypatch.setattr(extract, "MAX_EXPANDED_BYTES", 100)
    path = tmp_path / "bounded.xlsx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("sheet.xml", "x" * 101)
    with pytest.raises(UnreadableDataFileError, match="expanded archive"):
        extract.extract_sales_data(path)


@pytest.mark.parametrize("reference", ["XFD1", "A1048576"])
def test_security_sparse_cell_bounds(tmp_path, reference):
    from zipfile import ZipFile

    from etl import extract
    from etl.exceptions import UnreadableDataFileError

    path = tmp_path / "sparse.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml", f'<worksheet><row><c r="{reference}"/></row></worksheet>'
        )
    with pytest.raises(UnreadableDataFileError, match="cell bounds"):
        extract.extract_sales_data(path)


def test_security_xml_entities_rejected(tmp_path):
    from zipfile import ZipFile

    from etl import extract
    from etl.exceptions import UnreadableDataFileError

    path = tmp_path / "entity.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<!DOCTYPE x [<!ENTITY x "secret">]><worksheet>&x;</worksheet>',
        )
    with pytest.raises(UnreadableDataFileError):
        extract.extract_sales_data(path)
