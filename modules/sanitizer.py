"""Sanitize FHML files before structural validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import logging

from .utils import (
    IssueSeverity,
    RECORD_LENGTH,
    SectionReport,
    ValidationIssue,
    compute_status,
    detect_newline,
    ensure_ascii,
    strip_bom,
)

logger = logging.getLogger(__name__)


@dataclass
class SanitizeResult:
    """Outcome of the sanitization pipeline."""

    section: SectionReport
    lines: list[str]
    newline: str
    offending_codepoints: list[int]


class Sanitizer:
    """Prepare raw FHML payloads for subsequent validation."""

    def sanitize(self, file_path: Path) -> SanitizeResult:
        file_path = file_path.expanduser().resolve()
        logger.info("Sanitizando arquivo %s", file_path)

        try:
            raw_bytes = file_path.read_bytes()
        except OSError as exc:
            issue = ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                message=f"Não foi possível ler o arquivo: {exc}",
            )
            section = SectionReport(status=compute_status([issue]), issues=[issue])
            return SanitizeResult(section=section, lines=[], newline="NONE", offending_codepoints=[])

        issues: List[ValidationIssue] = []
        newline = detect_newline(raw_bytes)

        if b"\x00" in raw_bytes:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Bytes nulos detectados no arquivo",
                )
            )

        stripped_bytes = strip_bom(raw_bytes)
        if stripped_bytes is not raw_bytes:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    message="BOM UTF-8 removido automaticamente",
                )
            )

        try:
            decoded = stripped_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"Falha ao decodificar arquivo (latin-1): {exc}",
                )
            )
            section = SectionReport(status=compute_status(issues), issues=issues)
            return SanitizeResult(section=section, lines=[], newline=newline, offending_codepoints=[])

        ascii_text, offending = ensure_ascii(decoded)
        if offending:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    message="Caracteres fora da faixa ASCII substituídos por '?'",
                )
            )

        lines: list[str]
        if newline == "NONE":
            if len(ascii_text) % RECORD_LENGTH == 0:
                lines = [
                    ascii_text[idx : idx + RECORD_LENGTH]
                    for idx in range(0, len(ascii_text), RECORD_LENGTH)
                ]
            else:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        message="Não foi possível identificar quebras de linha; registros podem estar desalinhados",
                    )
                )
                lines = [ascii_text]
        else:
            lines = [line for line in ascii_text.splitlines() if line]

        if not lines:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Arquivo não contém registros após sanitização",
                )
            )

        section = SectionReport(status=compute_status(issues), issues=issues)
        return SanitizeResult(section=section, lines=lines, newline=newline, offending_codepoints=offending)


__all__ = ["Sanitizer", "SanitizeResult"]
