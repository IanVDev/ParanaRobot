"""Validator for FHML REG (Regularização).

This module confirms that previously-flagged IRR records were corrected.
We assume a correction marker is placed at positions 40-42 (slice 39:42) with value 'COR'.
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


class FHMLRegValidator:
    """Validate that IRR records were regularized (corrected).

    Input expected: list of lines. It will search detail lines for 'COR' marker.
    """

    def validate(self, lines: List[str], irr_lines: List[int] = None) -> Dict[str, object]:
        issues: List[ValidationIssue] = []
        corrected: List[int] = []
        missing: List[int] = []

        irr_lines = irr_lines or []
        counters = RecordCounters(total=len(lines), headers=0, details=0, trailers=0)

        for idx, line in enumerate(lines, start=1):
            rec = line[:3]
            if rec == DETAIL_CODE:
                counters.details += 1
                if idx in irr_lines:
                    marker = line[39:42]
                    if marker == 'COR':
                        corrected.append(idx)
                        issues.append(ValidationIssue(IssueSeverity.WARNING, f"Detalhe linha {idx} marcado como regularizado (COR)", line_number=idx, record_type=DETAIL_CODE))
                    else:
                        missing.append(idx)
                        issues.append(ValidationIssue(IssueSeverity.CRITICAL, f"Detalhe linha {idx} irregular não regularizado", line_number=idx, record_type=DETAIL_CODE))

        if not irr_lines:
            issues.append(ValidationIssue(IssueSeverity.WARNING, "Nenhuma irregularidade fornecida para regularização"))

        section = SectionReport(status=compute_status(issues), issues=issues)
        return {"section": section, "counters": counters, "corrected": corrected, "missing": missing}


__all__ = ["FHMLRegValidator"]
