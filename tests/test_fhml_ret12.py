from modules.fhml_ret12_validator import FHMLRet12Validator
from modules.utils import IssueSeverity


def make_record(code: str, fields=None) -> str:
    buf = [" "] * 240
    buf[0:3] = list(code)
    if fields:
        for start, end, val in fields:
            s = val.ljust(end - start + 1)[: end - start + 1]
            buf[start - 1:end] = list(s)
    return "".join(buf)


def test_ret12_detects_cancellations_and_unmatched():
    v = FHMLRet12Validator()

    header = make_record("100", [(10,17,"20251106")])
    # detail representing original with id 'ORIG0001' at 50-59
    orig = make_record("200", [(10,17,"20251106"), (50,59,"ORIG0001")])
    # cancellation detail with marker 'CX' at 36-37 and original id ORIG0001
    cancel = make_record("200", [(10,17,"20251106"), (36,37,"CX"), (50,59,"ORIG0001")])
    # cancellation with unmatched original
    cancel2 = make_record("200", [(10,17,"20251106"), (36,37,"CX"), (50,59,"NOTFOUND")])
    trailer = make_record("300", [(10,17,str(3).rjust(8))])

    lines = [header, orig, cancel, cancel2, trailer]
    out = v.validate(lines, original_ids=["ORIG0001"]) 

    assert out["canceled_lines"] == [3,4]
    assert out["unmatched"] == [4]
    severities = [iss.severity for iss in out["section"].issues]
    assert IssueSeverity.CRITICAL in severities
    assert IssueSeverity.WARNING in severities
