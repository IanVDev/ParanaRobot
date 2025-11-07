from modules.fhml_blq_validator import FHMLBlqValidator
from modules.utils import IssueSeverity


from typing import Optional, List, Tuple


def make_record(code: str, fields: Optional[List[Tuple[int, int, str]]] = None) -> str:
    buf = [" "] * 240
    buf[0:3] = list(code)
    if fields:
        for start, end, value in fields:
            length = end - start + 1
            s = value.ljust(length)[:length]
            buf[start - 1:end] = list(s)
    return "".join(buf)


def test_blq_detects_block_and_response():
    v = FHMLBlqValidator()

    header = make_record("100", [(10,17,"20251106")])

    # detail with code '02' at positions 36-37 and expected response 'OK2' at 38-40
    d1 = make_record("200", [(10,17,"20251106"), (36,37,"02"), (38,40,"OK2")])
    # detail with code '09' but wrong response
    d2 = make_record("200", [(10,17,"20251106"), (36,37,"09"), (38,40,"BAD")])
    # detail without relevant code
    d3 = make_record("200", [(10,17,"20251106"), (36,37,"00"), (38,40,"")])

    trailer = make_record("300", [(10,17,str(3).rjust(8)), (18,32,str(0).rjust(15))])

    lines = [header, d1, d2, d3, trailer]
    out = v.validate(lines)

    assert "blocked_lines" in out
    assert out["blocked_lines"] == [2, 3]  # d1 at line 2, d2 at line 3
    # one mismatch (d2)
    assert out["mismatches"] == [3]
    # check issues contain one CRITICAL for mismatch and WARNING for detection
    severities = [iss.severity for iss in out["section"].issues]
    assert IssueSeverity.CRITICAL in severities
    assert IssueSeverity.WARNING in severities
