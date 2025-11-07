"""Validator for FHML IRR (Irregularidades).

This initial implementation assumes the IRR error code for a detail
is found at positions 38-39 (slice 37:39) and a short description at 40-59.

It reports detected irregular lines and classifies severity depending on code.
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


class FHMLIrrValidator:
    """Detect irregularidades in detail records.

    Assumptions (documented in code):
    - Error code: positions 38-39 (slice 37:39)
    - Error description: 40-59 (slice 39:59)
    """

    CRITICAL_CODES = {"IR", "E1", "E2"}

    def validate(self, lines: List[str]) -> Dict[str, object]:
        issues: List[ValidationIssue] = []
        irr_lines: List[int] = []

        counters = RecordCounters(total=len(lines), headers=0, details=0, trailers=0)

        for idx, line in enumerate(lines, start=1):
            rec = line[:3]
            if rec == DETAIL_CODE:
                counters.details += 1
                code = line[37:39]
                desc = line[39:59].strip()
                if code.strip():
                    # consider as irregularity when an error code is present
                    irr_lines.append(idx)
                    severity = IssueSeverity.CRITICAL if code in self.CRITICAL_CODES else IssueSeverity.WARNING
                    issues.append(
                        ValidationIssue(
                            severity=severity,
                            message=f"Irregularidade detectada (codigo={code.strip()}) descricao='{desc}'",
                            line_number=idx,
                            record_type=DETAIL_CODE,
                        )
                    )

        if not irr_lines:
            issues.append(ValidationIssue(IssueSeverity.WARNING, "Nenhuma irregularidade detectada"))

        section = SectionReport(status=compute_status(issues), issues=issues)
        return {"section": section, "counters": counters, "irr_lines": irr_lines}


__all__ = ["FHMLIrrValidator"]
