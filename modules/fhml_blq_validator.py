"""Validador para arquivos FHMLBLQ11 — bloqueios.

Regras implementadas (inicial):
- Detecta detalhes (200) marcados com código de bloqueio nos campos esperados.
- Considera códigos de bloqueio relevantes: '02', '09', '14'.
- Reporta: lista de linhas bloqueadas, contagem e severidade quando respostas esperadas divergirem.

Observação: posições são baseadas nas convenções do projeto (1-based):
- Código de bloqueio (CS-ORIG-BLOQUEIO) assumido em 36-37 (slice 35:37)
- Resposta esperada simulada na posição 38-40 (slice 37:40)
"""
from __future__ import annotations

from typing import List, Dict
import logging

from .utils import (
    DETAIL_CODE,
    IssueSeverity,
    SectionReport,
    ValidationIssue,
    RecordCounters,
    compute_status,
)

logger = logging.getLogger(__name__)


class FHMLBlqValidator:
    """Validator for BLOQUEIO records (FHMLBLQ11).

    This is an initial implementation with deterministic checks used by tests.
    """

    RELEVANT_CODES = {"02", "09", "14"}

    def validate(self, lines: List[str]) -> Dict[str, object]:
        issues: List[ValidationIssue] = []
        blocked_lines: List[int] = []
        expected_responses_mismatch: List[int] = []

        counters = RecordCounters(total=len(lines), headers=0, details=0, trailers=0)

        for idx, line in enumerate(lines, start=1):
            rec = line[:3]
            if rec == DETAIL_CODE:
                counters.details += 1
                # code at 36-37 (slice 35:37)
                code = line[35:37]
                # simulated response at 38-40 (slice 37:40)
                response = line[37:40].strip()

                if code in self.RELEVANT_CODES:
                    blocked_lines.append(idx)
                    # simulate expected response mapping (for tests)
                    expected = self._expected_response_for(code)
                    if expected is not None and response != expected:
                        expected_responses_mismatch.append(idx)
                        issues.append(
                            ValidationIssue(
                                severity=IssueSeverity.CRITICAL,
                                message=(f"Detalhe linha {idx}: código bloqueio {code} com resposta inesperada '{response}' (esperado '{expected}')"),
                                line_number=idx,
                                record_type=DETAIL_CODE,
                            )
                        )
                    else:
                        issues.append(
                            ValidationIssue(
                                severity=IssueSeverity.WARNING,
                                message=(f"Detalhe linha {idx}: bloqueio detectado (codigo={code})"),
                                line_number=idx,
                                record_type=DETAIL_CODE,
                            )
                        )

        if not blocked_lines:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    message="Nenhum bloqueio detectado no arquivo",
                )
            )

        section = SectionReport(status=compute_status(issues), issues=issues)
        return {
            "section": section,
            "counters": counters,
            "blocked_lines": blocked_lines,
            "mismatches": expected_responses_mismatch,
        }

    def _expected_response_for(self, code: str) -> str | None:
        # Simple mapping used for validation tests
        mapping = {
            "02": "OK2",
            "09": "OK9",
            "14": "OK14",
        }
        return mapping.get(code)


__all__ = ["FHMLBlqValidator"]
