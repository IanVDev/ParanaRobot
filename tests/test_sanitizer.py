from pathlib import Path

from modules.sanitizer import Sanitizer
from modules.utils import ValidationStatus


def make_record(code: str) -> str:
    return (code + "X" * 20).ljust(240)


def test_sanitizer_removes_bom_and_non_ascii(tmp_path: Path) -> None:
    sanitizer = Sanitizer()
    header = make_record("100")
    detail = make_record("200")
    trailer = make_record("300")

    payload = "\n".join([header, detail, trailer]) + "\n"
    # Introduce BOM and a latin character
    data = "\ufeff" + payload.replace("X", "Ç", 1)

    target = tmp_path / "sample.d"
    target.write_text(data, encoding="utf-8")

    result = sanitizer.sanitize(target)

    assert result.section.status in {ValidationStatus.OK, ValidationStatus.WARN}
    assert result.lines[0].startswith("100")
    assert result.offending_codepoints
    assert result.newline == "LF"
