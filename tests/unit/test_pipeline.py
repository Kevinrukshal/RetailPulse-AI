"""Unit tests for pipeline utilities and CLI exit behavior."""

from hashlib import sha256
from pathlib import Path

from etl.pipeline import file_sha256, main


def test_file_sha256_streams_exact_file_content(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    content = b"order_id,sales\nA-1,10.00\n"
    source.write_bytes(content)

    assert file_sha256(source) == sha256(content).hexdigest()


def test_cli_returns_input_exit_code_for_missing_source(tmp_path: Path) -> None:
    exit_code = main(["--file", str(tmp_path / "missing.csv")])

    assert exit_code == 2
