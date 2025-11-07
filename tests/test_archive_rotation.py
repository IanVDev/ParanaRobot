import json
import types
from pathlib import Path

import finalize_pipeline


def test_archive_rotation(tmp_path, monkeypatch):
    """Simulate multiple old corrected files and ensure finalize archives older ones.

    - create reports/<stem>/corrigido with multiple `_fix*` and `_final*` variants
    - call finalize_pipeline.finalize_and_revalidate on the summary_final.json
    - assert that exactly one canonical `_final.d` remains in corrigido and others moved to archive/
    """
    stem = "TESTSTEM.B254.D0000001"
    base = tmp_path / "reports" / stem
    corrigido = base / "corrigido"
    corrigido.mkdir(parents=True)

    # create a few variants
    names = [
        f"{stem}.20251107.FHMLRET11_fix.d",
        f"{stem}.20251107.FHMLRET11_fix_001.d",
        f"{stem}.20251107.FHMLRET11_fix_001_final.d",
    ]
    for i, name in enumerate(names):
        p = corrigido / name
        p.write_text("dummy\n", encoding="utf-8")
        # set ascending modification times so the last is considered latest
        p.utime((100000 + i, 100000 + i))

    summary = {"arquivo": stem}
    summary_path = corrigido / "summary_final.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    # prevent finalize_pipeline from invoking main.py (subprocess.run)
    monkeypatch.setattr(finalize_pipeline.subprocess, "run", lambda *a, **k: None)

    # run finalizer
    finalize_pipeline.finalize_and_revalidate(str(summary_path))

    # expectations
    # corrigido should contain exactly one *_final.d (the canonical final)
    final_files = list(corrigido.glob("*_final.d"))
    assert len(final_files) == 1, f"Expected 1 final file in corrigido, found: {final_files}"

    # archive should exist and contain the other files
    archive = base / "archive"
    assert archive.exists(), "Archive directory should exist"
    archived = list(archive.iterdir())
    # at least two other files should have been moved into archive
    assert len(archived) >= 2, f"Expected archived files >=2, found {len(archived)}"
