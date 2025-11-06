"""Validador específico para arquivos FHMLMAC1n (Maciça)."""
from __future__ import annotations

from typing import List
import logging

from .utils import (
    DETAIL_CODE,
    HEADER_CODE,
    TRAILER_CODE,
    IssueSeverity,
    SectionReport,
    ValidationIssue,
    RecordCounters,
    compute_status,
)

logger = logging.getLogger(__name__)


class FHMLMacValidator:
    """Validations targeted at 'Maciça' submissions (MAC1n).

    Rules implemented (simulated, following user's request):
    - Expect exactly 10 detalhe (200) registros.
    - Simulate 2 inconsistidos (detalhes marcado como inconsistentes).
    - Verificar campos numéricos básicos e presença de possíveis bloqueios.
    """

    def validate(self, lines: List[str]) -> dict:
        issues: List[ValidationIssue] = []

        detail_indices: List[int] = []
        header_seen = False
        trailer_seen = False

        for idx, line in enumerate(lines, start=1):
            rec = line[:3]
            if rec == HEADER_CODE:
                header_seen = True
            elif rec == DETAIL_CODE:
                detail_indices.append(idx)
            elif rec == TRAILER_CODE:
                trailer_seen = True

        counters = RecordCounters(total=len(lines), headers=1 if header_seen else 0, details=len(detail_indices), trailers=1 if trailer_seen else 0)

        # Expect 10 creditos for MAC files
        expected_credits = 10
        if counters.details != expected_credits:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    message=f"MAC: esperado {expected_credits} registros de detalhe; encontrado {counters.details}",
                )
            )

        # Basic numeric checks on detail values (positions 18:32)
        for i, line_no in enumerate(detail_indices, start=1):
            line = lines[line_no - 1]
            val_field = line[17:32]
            if not val_field.strip().isdigit():
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Detalhe {i} (linha {line_no}): valor não numérico",
                        line_number=line_no,
                        record_type=DETAIL_CODE,
                    )
                )

        # Simular dois inconsistidos — determinístico: marcar o 2º e o 5º detalhe quando existir
        inconsistidos: List[int] = []
        targets = [2, 5]
        for t in targets:
            if t <= len(detail_indices):
                ln = detail_indices[t - 1]
                inconsistidos.append(ln)
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        message=f"Detalhe inconsistente simulado (linha {ln})",
                        line_number=ln,
                        record_type=DETAIL_CODE,
                    )
                )

        # Verificar presença de marca de bloqueio simulada (posição 36:38 == 'BLQ')
        bloqueios = []
        for ln in detail_indices:
            marker = lines[ln - 1][35:38]
            if marker == "BLQ":
                bloqueios.append(ln)

        if not bloqueios:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    message="MAC: nenhum bloqueio identificado (esperado alguns registros marcados)",
                )
            )

        section = SectionReport(status=compute_status(issues), issues=issues)
        return {"section": section, "counters": counters, "inconsistidos": inconsistidos, "bloqueios": bloqueios}


__all__ = ["FHMLMacValidator"]
