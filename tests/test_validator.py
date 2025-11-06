from modules.validator import Validator
from modules.utils import ValidationStatus


def make_valid_line(code: str) -> str:
    return (code + "".ljust(237)).ljust(240)


def test_validator_detects_length_issue() -> None:
    validator = Validator()

    header = make_valid_line("100")
    detail = ("200" + "A" * 10)  # too short
    trailer = make_valid_line("300")

    result = validator.validate([header, detail, trailer])

    assert result.section.status is ValidationStatus.ERROR
    assert result.length_issues == [2]
    assert any("Linha 2" in issue.message for issue in result.section.issues)


def test_validator_requires_trailer() -> None:
    validator = Validator()

    header = make_valid_line("100")
    detail = make_valid_line("200")

    result = validator.validate([header, detail])

    assert result.section.status is ValidationStatus.ERROR
    assert any("trailer" in issue.message.lower() for issue in result.section.issues)
