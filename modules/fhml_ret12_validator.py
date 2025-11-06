"""Validator for FHML RET12 (Cancelamentos / reversões).

This implementation assumes a cancellation marker is placed at positions 36-37
with code 'CX' and that the original transaction id is available at positions
50-59 (slice 49:59) to match against an input list of original detail ids.
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


class FHMLRet12Validator:
    """Validate cancelamentos / reversões.

    For tests we assume canceled records include an original id at 50-59
    and have a marker 'CX' at 36-37.
    """

    CANCEL_MARKER = 'CX'

    def validate(self, lines: List[str], original_ids: List[str] = None) -> Dict[str, object]:
        issues: List[ValidationIssue] = []
        canceled_lines: List[int] = []
        unmatched: List[int] = []

        original_ids = original_ids or []
        counters = RecordCounters(total=len(lines), headers=0, details=0, trailers=0)

        for idx, line in enumerate(lines, start=1):
            rec = line[:3]
            if rec == DETAIL_CODE:
                counters.details += 1
                marker = line[35:37]
                if marker == self.CANCEL_MARKER:
                    canceled_lines.append(idx)
                    orig = line[49:59].strip()
                    if original_ids and orig not in original_ids:
                        unmatched.append(idx)
                        issues.append(ValidationIssue(IssueSeverity.CRITICAL, f"Cancelamento linha {idx}: original id '{orig}' não encontrado", line_number=idx, record_type=DETAIL_CODE))
                    else:
                        issues.append(ValidationIssue(IssueSeverity.WARNING, f"Cancelamento detectado na linha {idx} (original id={orig})", line_number=idx, record_type=DETAIL_CODE))

        if not canceled_lines:
            issues.append(ValidationIssue(IssueSeverity.WARNING, "Nenhum cancelamento (RET12) detectado"))

        section = SectionReport(status=compute_status(issues), issues=issues)
        return {"section": section, "counters": counters, "canceled_lines": canceled_lines, "unmatched": unmatched}


__all__ = ["FHMLRet12Validator"]
