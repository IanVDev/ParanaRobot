from typing import Optional, List, Tuple

from modules.fhml_mac_validator_full import FHMLMacValidatorFull as FHMLMacValidator
from modules.utils import ValidationStatus, IssueSeverity


def make_record(code: str, fields: Optional[List[Tuple[int, int, str]]] = None) -> str:
    # create 240-char buffer and set code at 1-3
    buf = [" "] * 240
    buf[0:3] = list(code)
    if fields:
        for start, end, value in fields:
            length = end - start + 1
            val = value.ljust(length)[:length]
            buf[start - 1:end] = list(val)
    return "".join(buf)


def test_mac_validator_detects_inconsistidos_and_expected_count():
    validator = FHMLMacValidator()

    # Build header with generation date
    header = make_record("100", [(10,17,"20251106"),(18,27,"0000000001"),(28,35,"MACTEST")])

    details = []
    values = [100,200,300,400,500,600,700,800,900,1000]  # cents
    for v in values:
        # value in positions 18-32 (15 chars)
        fields = [ (10,17,"20251106"), (18,32,str(v).rjust(15)) ]
        details.append(make_record("200", fields))

    # Trailer: total registros = 10 (pos 10-17), valor total = sum(values)
    total = sum(values)
    trailer = make_record("300", [(10,17,str(10).rjust(8)), (18,32,str(total).rjust(15))])

    lines = [header] + details + [trailer]

    result = validator.validate(lines)

    assert result.counters.details == 10
    assert result.totalizers.detail_sum == total
    assert len(result.inconsistidos) == 2
    # trailer should match sum => no critical about totals
    assert not any(issue.severity == IssueSeverity.CRITICAL for issue in result.section.issues)