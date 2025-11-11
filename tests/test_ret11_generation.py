import subprocess
from pathlib import Path
import time


def run(cmd):
    r = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    return r.stdout


def latest_ret11_path():
    p = Path('ready')
    files = sorted(p.glob('HMLMAC12.TESTE_FINAL.*.FHMLRET11_final.d'))
    return files[-1] if files else None


def test_ret11_generation():
    # 1) generate test files
    run('python3 scripts/generate_test_files.py')
    # small sleep to ensure filesystem timestamps differ
    time.sleep(0.1)

    # 2) run pipeline
    run('python3 finalize_pipeline.py')

    # 3) find latest RET11
    path = latest_ret11_path()
    assert path is not None, 'RET11 file not generated'

    lines = path.read_text(encoding='utf-8').splitlines()
    details = [ln for ln in lines if ln.startswith('2')]
    # Expect 3 details (cpf diff, conta diff, both -> cpf precedence)
    assert len(details) == 3, f'Expected 3 detail lines, found {len(details)}'

    # Check occurrence codes: builder places code followed by '01' (e.g., '1701' or '1601')
    joined = '\n'.join(details)
    count_17 = joined.count('1701')
    count_16 = joined.count('1601')
    assert count_17 == 2, f'Expected two 17 codes (cpf), found {count_17}'
    assert count_16 == 1, f'Expected one 16 code (conta), found {count_16}'
