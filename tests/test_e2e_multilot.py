import subprocess
from pathlib import Path
import shutil
import sys


def test_e2e_multilot(tmp_path: Path):
    # prepare input dir
    input_dir = tmp_path / "input" / "lote"
    input_dir.mkdir(parents=True)

    # copy sample real files from workspace
    base = Path(__file__).resolve().parents[1]
    src_mac = base / "input" / "lote_20251107_002" / "HMLMAC12.B254.D0000001.txt"
    src_con = base / "input" / "lote_20251107_002" / "HMLCON12.B254.D0000003.txt"
    assert src_mac.exists() and src_con.exists()
    shutil.copy(src_mac, input_dir / src_mac.name)
    shutil.copy(src_con, input_dir / src_con.name)

    # run upload_manager in once mode
    cmd = [sys.executable, str(base / "upload_manager.py"), "--watch", str(tmp_path / "input"), "--reports", str(tmp_path / "reports"), "--logs", str(tmp_path / "logs"), "--once"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    assert res.returncode in (0, 1)

    # expect reports folder with at least one RET file
    reports = tmp_path / "reports"
    assert reports.exists()
    # find any .FHMLRET11_*.d file
    found = list(reports.rglob("*.FHMLRET11*.d"))
    assert found, "No RET files generated"
