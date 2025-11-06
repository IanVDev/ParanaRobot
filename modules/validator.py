"""Structural validation for FHML 240-byte records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import logging

from .utils import (
    DETAIL_CODE,
    HEADER_CODE,
    RECORD_LENGTH,
    TRAILER_CODE,
    IssueSeverity,
    RecordCounters,
    SectionReport,
    ValidationIssue,
    compute_status,
)

logger = logging.getLogger(__name__)


@dataclass
class StructureResult:
    """Outcome of the structural validation stage."""

    section: SectionReport
    record_counters: RecordCounters
    length_issues: list[int]


class Validator:
    """Validate the overall structure of FHML files."""

    def validate(self, lines: list[str]) -> StructureResult:
        logger.info("Validando estrutura FHML (%d registros)", len(lines))

        issues: List[ValidationIssue] = []
        length_issues: list[int] = []

        counters = RecordCounters(total=len(lines), headers=0, details=0, trailers=0)

        if not lines:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Arquivo vazio após sanitização",
                )
            )
            section = SectionReport(status=compute_status(issues), issues=issues)
            return StructureResult(section=section, record_counters=counters, length_issues=length_issues)

        header_seen = False
        trailer_seen = False

        for index, line in enumerate(lines, start=1):
            if len(line) != RECORD_LENGTH:
                length_issues.append(index)
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        message=f"Linha {index} possui {len(line)} bytes (esperado=240)",
                        line_number=index,
                    )
                )

            record_type = line[:3]

            if record_type == HEADER_CODE:
                counters.headers += 1
                if index != 1:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message="Header (100) fora da primeira posição",
                            line_number=index,
                            record_type=record_type,
                        )
                    )
                if trailer_seen:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message="Header encontrado após trailer",
                            line_number=index,
                            record_type=record_type,
                        )
                    )
                header_seen = True
            elif record_type == DETAIL_CODE:
                counters.details += 1
                if trailer_seen:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message="Detalhe encontrado após trailer",
                            line_number=index,
                            record_type=record_type,
                        )
                    )
            elif record_type == TRAILER_CODE:
                counters.trailers += 1
                if trailer_seen:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message="Mais de um trailer encontrado",
                            line_number=index,
                            record_type=record_type,
                        )
                    )
                if not header_seen:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message="Trailer encontrado antes do header",
                            line_number=index,
                            record_type=record_type,
                        )
                    )
                trailer_seen = True
            else:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        message=f"Tipo de registro inválido '{record_type}' na linha {index}",
                        line_number=index,
                        record_type=record_type,
                    )
                )

        if counters.headers == 0:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Arquivo não possui header (100)",
                )
            )
        if counters.details == 0:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Arquivo não possui registros de detalhe (200)",
                )
            )
        if counters.trailers == 0:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Arquivo não possui trailer (300)",
                )
            )
        if counters.trailers > 0 and not trailer_seen:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Trailer não localizado ao final do arquivo",
                )
            )
        if lines and lines[-1][:3] != TRAILER_CODE:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Último registro não é trailer (300)",
                )
            )

        section = SectionReport(status=compute_status(issues), issues=issues)
        return StructureResult(section=section, record_counters=counters, length_issues=length_issues)


__all__ = ["Validator", "StructureResult"]
