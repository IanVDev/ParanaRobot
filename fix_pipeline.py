#!/usr/bin/env python3
"""Simple fix pipeline for ParanaRobot reports.

Usage:
    python3 fix_pipeline.py reports/<lote>/json/<file>.json

This script reads the ParanaRobot JSON, extracts errors/warnings, builds a
human-readable diagnostic, attempts an automatic correction of the RET file
under reports/<lote>/ret/, writes the corrected file to reports/<lote>/corrigido/
and emits logs: fix_pipeline.log and resumo_leigo.txt.

It also attempts to re-run paranarobot (`main.py`) on the corrected file.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def diagnose_and_fix(json_path: Path) -> Path:
    base = json_path.parent.parent
    data = load_json(json_path)

    # project JSON places messages under `validacao` as created by Reporter
    valid = data.get("validacao", {})
    errors: List[str] = valid.get("erros", []) or []
    warnings: List[str] = valid.get("avisos", []) or []

    report_lines: List[str] = []
    report_lines.append("=== DIAGNÓSTICO TÉCNICO ===\n")
    if errors:
        for e in errors:
            report_lines.append(f"[ERROR] {e}")
    if warnings:
        for w in warnings:
            report_lines.append(f"[WARN] {w}")

    # Diagnóstico leigo
    resumo_leigo: List[str] = []
    resumo_leigo.append("🟢 RESUMO LEIGO - ANÁLISE DO LOTE")
    if not errors:
        resumo_leigo.append("✅ Nenhum erro crítico encontrado. O arquivo está pronto para envio ao Connect.")
    else:
        resumo_leigo.append(f"⚠️ Foram encontrados {len(errors)} erros:")
        resumo_leigo.append("- Estruturais (ordem de registros, headers/trailers) se mencionados.")
        resumo_leigo.append("- Soma de trailer incorreta ou registros fora da ordem.")
        resumo_leigo.append("💡 O ParanaRobot irá gerar um arquivo corrigido automaticamente.")

    # Find RET file
    ret_dir = base / "ret"
    ret_files = sorted(ret_dir.glob("*.d")) if ret_dir.exists() else []
    if not ret_files:
        raise SystemExit(f"Nenhum arquivo RET encontrado em {ret_dir}")

    ret_file = ret_files[0]

    # Prepare output dir
    fixed_dir = base / "corrigido"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    fixed_path = fixed_dir / (ret_file.stem + "_fix.d")

    # Read original lines
    with ret_file.open("r", encoding="utf-8") as fh:
        raw_lines = [ln.rstrip("\n") for ln in fh]

    headers: List[str] = []
    details: List[str] = []
    trailers: List[str] = []

    for ln in raw_lines:
        if not ln:
            continue
        code = ln[:3]
        if code == "100":
            headers.append(ln)
        elif code == "200":
            details.append(ln)
        elif code == "300":
            trailers.append(ln)
        else:
            # ignore unknown record types
            continue

    # If multiple headers, keep first; if none, try to use first line as header
    header = headers[0] if headers else (raw_lines[0] if raw_lines and raw_lines[0].startswith("100") else None)

    # Compute sums from details (positions per Analyzer: valor_cents = line[17:32])
    total_details = len(details)
    total_value = 0
    for ln in details:
        val_slice = ln[17:32]
        val_str = val_slice.strip()
        if val_str.isdigit():
            total_value += int(val_str)

    # Build trailer: if existing trailer template use it, else create a simple one
    if trailers:
        trailer_template = trailers[-1]
        # replace total_registros (9:17) and valor_total (17:32)
        total_registros_field = str(total_details).rjust(8, "0")
        total_valor_field = str(total_value).rjust(15, "0")
        new_trailer = (
            trailer_template[:9]
            + total_registros_field
            + total_valor_field
            + trailer_template[32:240].ljust(240)
        )
    else:
        # minimal trailer: start with '300', pad to 240 and insert counts
        total_registros_field = str(total_details).rjust(8, "0")
        total_valor_field = str(total_value).rjust(15, "0")
        # positions: 0-3 type, 3-9 filler, 9-17 total_registros, 17-32 valor_total
        new_trailer = (
            "300" + " " * 6 + total_registros_field + total_valor_field + " " * (240 - 32)
        )

    fixed_lines: List[str] = []
    if header:
        fixed_lines.append(header[:240].ljust(240))
    fixed_lines.extend([ln[:240].ljust(240) for ln in details])
    fixed_lines.append(new_trailer[:240].ljust(240))

    # Persist corrected file
    with fixed_path.open("w", encoding="utf-8") as fh:
        for l in fixed_lines:
            fh.write(l + "\n")

    # Save logs
    Path("fix_pipeline.log").write_text("\n".join(report_lines), encoding="utf-8")
    Path("resumo_leigo.txt").write_text("\n".join(resumo_leigo), encoding="utf-8")

    print(f"✅ Diagnóstico salvo em fix_pipeline.log")
    print(f"✅ Resumo leigo salvo em resumo_leigo.txt")
    print(f"✅ Arquivo corrigido salvo em {fixed_path}")

    return fixed_path


def main(argv: List[str] | None = None) -> int:
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    if not argv or len(argv) != 1:
        print("Uso: python3 fix_pipeline.py <path_para_json>")
        return 2

    json_path = Path(argv[0])
    if not json_path.exists():
        print(f"Arquivo JSON não encontrado: {json_path}")
        return 2

    fixed = diagnose_and_fix(json_path)

    # Re-run paranarobot on the fixed file to update reports/summary
    try:
        print(f"🔁 Reexecutando paranarobot (main.py) sobre {fixed} ...")
        subprocess.run(["python3", "main.py", str(fixed)], check=False)
    except Exception as exc:
        print(f"Falha ao reexecutar main.py: {exc}")

    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
