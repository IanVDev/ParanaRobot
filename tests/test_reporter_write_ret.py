from pathlib import Path

from modules.reporter import Reporter
from modules.utils import (
    FileMetadata,
    SectionReport,
    ValidationIssue,
    IssueSeverity,
    ValidationStatus,
    RecordCounters,
    Totalizers,
    ValidationSummary,
)


def _make_dummy_metadata(tmp_path: Path) -> FileMetadata:
    original = tmp_path / "MAC123.zip"
    working = tmp_path / "MAC123.d"
    tempdir = tmp_path / "tmp"
    tempdir.mkdir()
    original.write_text("")
    working.write_text("")
    return FileMetadata(original_path=original, working_path=working, temp_dir=tempdir, extracted_from_zip=False)


def test_reporter_writes_ret_and_json(tmp_path: Path):
    reporter = Reporter()
    metadata = _make_dummy_metadata(tmp_path)

    # create fake generated RET lines (header + 2 details + trailer)
    header = "100" + " " * 237
    d1 = ("200" + " " * 108 + "16" + " " * 111)[:240]
    d2 = ("200" + " " * 108 + "17" + " " * 111)[:240]
    trailer = "300" + " " * 237
    generated = [header, d1, d2, trailer]

    # fabricate minimal summary
    section = SectionReport(status=ValidationStatus.OK, issues=[])
    counters = RecordCounters(total=4, headers=1, details=2, trailers=1)
    totals = Totalizers(detail_sum=3000, trailer_sum=3000)

    summary = ValidationSummary(
        metadata=metadata,
        structure=section,
        encoding=section,
        content=section,
        record_counters=counters,
        totalizers=totals,
        newline="LF",
        offending_codepoints=[],
    )

    # attach generated_ret_lines
    metadata.generated_ret_lines = generated

    paths = reporter.render(summary, tmp_path)

    # verify files exist
    assert Path(paths.json_path).exists()
    assert Path(paths.txt_path).exists()

    # ret file should be under reports/<stem>/ and present in JSON
    import json

    data = json.loads(Path(paths.json_path).read_text(encoding="utf-8"))
    assert "ret11" in data
    assert data["ret11"]["count_16"] == 1
    assert data["ret11"]["count_17"] == 1
    assert data["ret11"]["detail_count"] == 2
