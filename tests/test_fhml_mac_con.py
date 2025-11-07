"""Unit tests for FHML MAC x CON comparison validator."""
from modules.fhml_mac_con_validator import FHMLMacConValidator


def _pad(s: str, length: int = 240) -> str:
    s = s[:length]
    return s + (" " * (length - len(s)))


def _make_header() -> str:
    rec = list(" " * 240)
    rec[0:3] = list("100")
    # data at 16-23 (index 15:23)
    rec[15:23] = list("20251107")
    return _pad("".join(rec))


def _make_trailer(count: int, total: int) -> str:
    rec = list(" " * 240)
    rec[0:3] = list("300")
    rec[13:21] = list(str(count).rjust(8, "0"))
    rec[21:38] = list(str(total).rjust(17, "0"))
    return _pad("".join(rec))


def _make_detail(nb: str, cpf: str, conta: str, value: int) -> str:
    rec = list(" " * 240)
    rec[0:3] = list("200")
    # NU-NB 11-20 -> index 10:20
    rec[10:20] = list(nb.ljust(10))
    # CPF 49-59 -> index 48:59
    rec[48:59] = list(cpf.ljust(11))
    # value 51-62 -> index 50:62 (cents)
    rec[50:62] = list(str(value).rjust(12, "0"))
    # conta 83-92 -> index 82:92
    rec[82:92] = list(conta.ljust(10))
    return _pad("".join(rec))


def test_mac_con_rules_16_and_17():
    validator = FHMLMacConValidator()

    header = _make_header()
    # MAC details
    mac_d1 = _make_detail(nb="0000000001", cpf="11111111111", conta="0000000001", value=1000)
    mac_d2 = _make_detail(nb="0000000002", cpf="22222222222", conta="0000000002", value=2000)
    mac_d3 = _make_detail(nb="0000000003", cpf="00000000000", conta="0000000000", value=3000)
    trailer = _make_trailer(3, 6000)
    mac_lines = [header, mac_d1, mac_d2, mac_d3, trailer]

    # CON details: for d1 both conta and cpf different -> expect 16
    con_d1 = _make_detail(nb="0000000001", cpf="99999999999", conta="0000000099", value=1000)
    # for d2 cpf different and at least one conta non-zero -> expect 17
    con_d2 = _make_detail(nb="0000000002", cpf="33333333333", conta="0000000002", value=2000)
    # for d3 both cpfs zero -> valid, no occurrence
    con_d3 = _make_detail(nb="0000000003", cpf="00000000000", conta="0000000000", value=3000)
    con_header = _make_header()
    con_trailer = _make_trailer(3, 6000)
    con_lines = [con_header, con_d1, con_d2, con_d3, con_trailer]

    result = validator.validate_pair(mac_lines, con_lines)

    # Expect 1 header + 3 details + 1 trailer
    assert result.counters.details == 3
    assert len(result.ret_lines) == 5

    # Check occurrences in ret_lines details at positions 1..n (ret_lines: header=0, details 1-3, trailer last)
    r_d1 = result.ret_lines[1]
    r_d2 = result.ret_lines[2]
    r_d3 = result.ret_lines[3]

    # occurrence positions 112-113 -> slice 111:113
    assert r_d1[111:113] == "16"
    assert r_d2[111:113] == "17"
    assert r_d3[111:113].strip() == ""
