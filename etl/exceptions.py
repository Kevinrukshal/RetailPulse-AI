"""Domain exceptions raised by the RetailPulse ETL pipeline."""


class ExtractionError(Exception):
    """Base exception for source-file extraction failures."""


class SourceFileNotFoundError(ExtractionError):
    """Raised when the requested source path does not exist or is not a file."""


class UnsupportedFileTypeError(ExtractionError):
    """Raised when a source file is not CSV or XLSX."""


class EmptyDataFileError(ExtractionError):
    """Raised when a source file contains no usable tabular data."""


class DataEncodingError(ExtractionError):
    """Raised when a CSV cannot be decoded as UTF-8."""


class UnreadableDataFileError(ExtractionError):
    """Raised when a source file cannot be opened or parsed."""


class NoUsableWorksheetError(ExtractionError):
    """Raised when an Excel workbook has no non-empty worksheet."""


class ColumnMappingError(ExtractionError):
    """Raised when source columns cannot be mapped unambiguously."""


class ValidationError(Exception):
    """Base exception for dataset-level validation failures."""


class MissingRequiredColumnsError(ValidationError):
    """Raised when a dataset lacks fields required for row validation."""


class EmptyDatasetError(ValidationError):
    """Raised when a dataset has columns but contains no records."""
