"""Utility helpers for ParanaRobot."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Optional
import datetime as _dt
import logging
import tempfile

RECORD_LENGTH = 240
HEADER_CODE = "100"
DETAIL_CODE = "200"
TRAILER_CODE = "300"


class IssueSeverity(str, Enum):
    """Enumeration of validation severities."""

    WARNING = "warning"
    CRITICAL = "critical"


class ValidationStatus(str, Enum):
    """High-level status for validation sections."""

    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class ValidationIssue:
    """Container for individual validation issues."""

    severity: IssueSeverity
    message: str
    line_number: Optional[int] = None
    record_type: Optional[str] = None
    code: Optional[str] = None


@dataclass
class SectionReport:
    """Summary for a validation section."""

    status: ValidationStatus
    issues: list[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity is IssueSeverity.CRITICAL for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity is IssueSeverity.WARNING for issue in self.issues)


@dataclass
class FileMetadata:
    """Metadata about the processed file."""

    original_path: Path
    working_path: Path
    temp_dir: Path
    extracted_from_zip: bool


@dataclass
class RecordCounters:
    """Track record counts for the processed payload."""

    total: int
    headers: int
    details: int
    trailers: int


@dataclass
class Totalizers:
    """Summaries for numeric totals collected from details and trailer."""

    detail_sum: int
    trailer_sum: Optional[int]


@dataclass
class ValidationSummary:
    """Aggregate validation outcome for reporting."""

    metadata: FileMetadata
    structure: SectionReport
    encoding: SectionReport
    content: SectionReport
    record_counters: RecordCounters
    totalizers: Totalizers
    newline: str
    offending_codepoints: list[int]


def ensure_reports_dir(base_dir: Path) -> Path:
    """Ensure that the reports directory exists."""

    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger when the CLI runs."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def timestamped_tempdir(prefix: str = "paranarobot") -> Path:
    """Create a timestamped temporary directory for processing."""

    ts = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
    temp_root = Path(tempfile.gettempdir()) / f"{prefix}-{ts}"
    temp_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def chunk_records(payload: Iterable[str]) -> Iterator[tuple[int, str]]:
    """Yield 1-indexed records from an iterable of 240-char strings."""

    for index, line in enumerate(payload, start=1):
        yield index, line


def write_text(path: Path, content: str) -> None:
    """Persist text content to disk ensuring parent directories exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    """Persist JSON content to disk with UTF-8 encoding."""

    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def detect_newline(data: bytes) -> str:
    """Detect newline type used in the byte buffer."""

    if b"\r\n" in data:
        return "CRLF"
    if b"\n" in data:
        return "LF"
    return "NONE"


def strip_bom(data: bytes) -> bytes:
    """Remove UTF-8 BOM when present."""

    bom = b"\xef\xbb\xbf"
    if data.startswith(bom):
        return data[len(bom) :]
    return data


def ensure_ascii(text: str) -> tuple[str, list[int]]:
    """Convert text to ASCII, tracking offending code points."""

    offending: list[int] = []
    result_chars: list[str] = []
    for char in text:
        if ord(char) > 127:
            offending.append(ord(char))
            result_chars.append("?")
        else:
            result_chars.append(char)
    return "".join(result_chars), offending


def safe_unlink(path: Path) -> None:
    """Delete a path without raising when it is missing."""

    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        logging.getLogger(__name__).debug("Could not remove %s: %s", path, exc)


def compute_status(issues: list[ValidationIssue]) -> ValidationStatus:
    """Compute section status based on collected issues."""

    if any(issue.severity is IssueSeverity.CRITICAL for issue in issues):
        return ValidationStatus.ERROR
    if any(issue.severity is IssueSeverity.WARNING for issue in issues):
        return ValidationStatus.WARN
    return ValidationStatus.OK


__all__ = [
    "FileMetadata",
    "HEADER_CODE",
    "DETAIL_CODE",
    "TRAILER_CODE",
    "IssueSeverity",
    "SectionReport",
    "ValidationIssue",
    "ValidationStatus",
    "RecordCounters",
    "Totalizers",
    "ValidationSummary",
    "compute_status",
    "chunk_records",
    "configure_logging",
    "detect_newline",
    "ensure_ascii",
    "ensure_reports_dir",
    "RECORD_LENGTH",
    "strip_bom",
    "timestamped_tempdir",
    "write_json",
    "write_text",
    "safe_unlink",
]
