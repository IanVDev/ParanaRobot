from modules.fhml_irr_validator import FHMLIrrValidator
from modules.utils import IssueSeverity


def make_record(code: str, fields=None) -> str:
    buf = [" "] * 240
    buf[0:3] = list(code)
    if fields:
        for start, end, val in fields:
            s = val.ljust(end - start + 1)[: end - start + 1]
            buf[start - 1:end] = list(s)
    return "".join(buf)


def test_irr_detects_critical_and_warning():
    v = FHMLIrrValidator()

    header = make_record("100", [(10,17,"20251106")])
    # detail with critical code E1 at 38-39 and desc
    d1 = make_record("200", [(10,17,"20251106"), (38,39,"E1"), (40,59,"Erro critico")])
    # detail with non-critical code Z1
    d2 = make_record("200", [(10,17,"20251106"), (38,39,"Z1"), (40,59,"Erro menor")])
    trailer = make_record("300", [(10,17,str(2).rjust(8))])

    lines = [header, d1, d2, trailer]
    out = v.validate(lines)

    assert out["irr_lines"] == [2, 3]
    severities = [iss.severity for iss in out["section"].issues]
    assert IssueSeverity.CRITICAL in severities
    assert IssueSeverity.WARNING in severities
