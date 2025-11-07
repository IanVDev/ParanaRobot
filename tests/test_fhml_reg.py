from modules.fhml_reg_validator import FHMLRegValidator
from modules.utils import IssueSeverity


def make_record(code: str, fields=None) -> str:
    buf = [" "] * 240
    buf[0:3] = list(code)
    if fields:
        for start, end, val in fields:
            s = val.ljust(end - start + 1)[: end - start + 1]
            buf[start - 1:end] = list(s)
    return "".join(buf)


def test_reg_detects_corrected_and_missing():
    v = FHMLRegValidator()

    header = make_record("100", [(10,17,"20251106")])
    # irregular details at lines 2 and 3
    d1 = make_record("200", [(10,17,"20251106"), (40,42,"COR")])  # corrected
    d2 = make_record("200", [(10,17,"20251106")])  # not corrected
    trailer = make_record("300", [(10,17,str(2).rjust(8))])

    lines = [header, d1, d2, trailer]
    # pass irr_lines as [2,3]
    out = v.validate(lines, irr_lines=[2,3])

    assert out["corrected"] == [2]
    assert out["missing"] == [3]
    severities = [iss.severity for iss in out["section"].issues]
    assert IssueSeverity.CRITICAL in severities
    assert IssueSeverity.WARNING in severities
