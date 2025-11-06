"""Semantic analysis for FHML records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import datetime as _dt
import logging

from .utils import (
    DETAIL_CODE,
    HEADER_CODE,
    TRAILER_CODE,
    IssueSeverity,
    RecordCounters,
    SectionReport,
    Totalizers,
    ValidationIssue,
    compute_status,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Outcome of the semantic validation stage."""

    section: SectionReport
    totalizers: Totalizers
    inferred_counters: RecordCounters


class Analyzer:
    """Validate header, detail and trailer semantics."""

    def analyze(self, lines: list[str]) -> AnalysisResult:
        issues: List[ValidationIssue] = []

        header_data: Optional[dict] = None
        trailer_data: Optional[dict] = None
        detail_sum = 0
        detail_count = 0

        for idx, line in enumerate(lines, start=1):
            record_type = line[:3]
            if record_type == HEADER_CODE and header_data is None:
                header_data = self._analyze_header(line, idx, issues)
            elif record_type == HEADER_CODE:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        message="Header adicional ignorado",
                        line_number=idx,
                        record_type=record_type,
                    )
                )
            elif record_type == DETAIL_CODE:
                detail_count += 1
                amount = self._analyze_detail(line, idx, issues)
                if amount is not None:
                    detail_sum += amount
            elif record_type == TRAILER_CODE and trailer_data is None:
                trailer_data = self._analyze_trailer(line, idx, issues)
            elif record_type == TRAILER_CODE:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        message="Trailer adicional detectado",
                        line_number=idx,
                        record_type=record_type,
                    )
                )
            else:
                # Unknown record types already flagged at structural stage, keep as info here
                continue

        if header_data is None:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Header não pôde ser analisado",
                )
            )
        if trailer_data is None:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message="Trailer não pôde ser analisado",
                )
            )

        # Consistency checks when trailer available
        if trailer_data is not None:
            trailer_total_registros = trailer_data.get("total_registros")
            trailer_valor_total = trailer_data.get("valor_total")

            if trailer_total_registros is not None:
                expected = detail_count
                if trailer_total_registros != expected:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message=(
                                "Trailer: total de registros não confere "
                                f"(esperado={expected}, encontrado={trailer_total_registros})"
                            ),
                        )
                    )
            if trailer_valor_total is not None:
                if trailer_valor_total != detail_sum:
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            message=(
                                "Trailer: valor total não confere "
                                f"(esperado={detail_sum}, encontrado={trailer_valor_total})"
                            ),
                        )
                    )

        totalizers = Totalizers(detail_sum=detail_sum, trailer_sum=trailer_data.get("valor_total") if trailer_data else None)
        inferred_counters = RecordCounters(
            total=len(lines),
            headers=1 if header_data else 0,
            details=detail_count,
            trailers=1 if trailer_data else 0,
        )

        section = SectionReport(status=compute_status(issues), issues=issues)
        return AnalysisResult(section=section, totalizers=totalizers, inferred_counters=inferred_counters)

    def _analyze_header(self, line: str, idx: int, issues: List[ValidationIssue]) -> dict:
        data = {
            "data_geracao": line[9:17],
            "codigo_empresa": line[17:27],
            "identificador_servico": line[27:35],
        }

        self._validate_date(data["data_geracao"], idx, "Header: campo Data Geração inválido", issues)
        self._validate_numeric(
            data["codigo_empresa"],
            idx,
            "Header: código da empresa deve ser numérico",
            issues,
            required=True,
        )
        if not data["identificador_servico"].strip():
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    message="Header: identificador do serviço em branco",
                    line_number=idx,
                    record_type=HEADER_CODE,
                )
            )
        return data

    def _analyze_detail(self, line: str, idx: int, issues: List[ValidationIssue]) -> Optional[int]:
        data_movimento = line[9:17]
        valor_cents = line[17:32]

        self._validate_date(
            data_movimento,
            idx,
            "Detalhe: data de movimento inválida",
            issues,
        )

        value = self._validate_numeric(
            valor_cents,
            idx,
            "Detalhe: valor inválido",
            issues,
            required=True,
        )
        return value

    def _analyze_trailer(self, line: str, idx: int, issues: List[ValidationIssue]) -> dict:
        total_registros = line[9:17]
        valor_total = line[17:32]

        total = self._validate_numeric(
            total_registros,
            idx,
            "Trailer: total de registros inválido",
            issues,
            required=True,
        )
        total_valor = self._validate_numeric(
            valor_total,
            idx,
            "Trailer: valor total inválido",
            issues,
            required=True,
        )
        return {
            "total_registros": total,
            "valor_total": total_valor,
        }

    def _validate_date(
        self,
        value: str,
        idx: int,
        message: str,
        issues: List[ValidationIssue],
    ) -> None:
        if not value.strip():
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"{message} (em branco)",
                    line_number=idx,
                )
            )
            return

        if not value.isdigit() or len(value) != 8:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"{message} ({value})",
                    line_number=idx,
                )
            )
            return

        try:
            _dt.datetime.strptime(value, "%Y%m%d")
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"{message} ({value})",
                    line_number=idx,
                )
            )

    def _validate_numeric(
        self,
        value: str,
        idx: int,
        message: str,
        issues: List[ValidationIssue],
        *,
        required: bool = False,
    ) -> Optional[int]:
        striped = value.strip()
        if not striped:
            if required:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        message=f"{message} (em branco)",
                        line_number=idx,
                    )
                )
            return None
        if not striped.isdigit():
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"{message} ({striped})",
                    line_number=idx,
                )
            )
            return None
        try:
            return int(striped)
        except ValueError:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"{message} ({striped})",
                    line_number=idx,
                )
            )
            return None


__all__ = ["Analyzer", "AnalysisResult"]
