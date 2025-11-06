from modules.analyzer import Analyzer
from modules.utils import ValidationStatus


def create_record(code: str, fields: list[tuple[int, int, str]]) -> str:
    buffer = [" "] * 240
    buffer[:3] = list(code)
    for start, end, value in fields:
        length = end - start + 1
        assert len(value) <= length, "Field value exceeds configured length"
        padded = value.ljust(length)
        buffer[start - 1 : end] = list(padded[:length])
    return "".join(buffer)


def test_analyzer_detects_trailer_mismatch() -> None:
    analyzer = Analyzer()

    header = create_record(
        "100",
        [
            (10, 17, "20250101"),
            (18, 27, "0000123456"),
            (28, 35, "SERV0001"),
        ],
    )
    detail_a = create_record(
        "200",
        [
            (10, 17, "20250102"),
            (18, 32, "000000000010000"),
        ],
    )
    detail_b = create_record(
        "200",
        [
            (10, 17, "20250103"),
            (18, 32, "000000000020000"),
        ],
    )
    trailer = create_record(
        "300",
        [
            (10, 17, "00000003"),
            (18, 32, "000000000030000"),
        ],
    )

    result = analyzer.analyze([header, detail_a, detail_b, trailer])

    assert result.section.status is ValidationStatus.ERROR
    assert result.totalizers.detail_sum == 30000
    assert any("total de registros" in issue.message for issue in result.section.issues)
