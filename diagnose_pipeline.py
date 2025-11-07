#!/usr/bin/env python3
"""Diagnosis pipeline (renamed from fix_pipeline.py).

Reads ParanaRobot JSON reports, produces diagnostics and (optionally) generates
corrected RET files per sub-lote.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List
import datetime as _dt

# reuse split_into_batches from project
from modules.utils import split_into_batches


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def diagnose_and_fix(json_path: Path) -> List[Path]:
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

    # Read original lines
    with ret_file.open("r", encoding="utf-8") as fh:
        raw_lines = [ln.rstrip("\n") for ln in fh]

    # Split into batches using project's util
    batches = split_into_batches(raw_lines)
    if not batches:
        batches = [raw_lines]

    generated_fixed: List[Path] = []

    for idx, batch in enumerate(batches, start=1):
        headers = [ln for ln in batch if ln.startswith("100")]
        details = [ln for ln in batch if ln.startswith("200")]
        trailers = [ln for ln in batch if ln.startswith("300")]

        header = headers[0] if headers else None

        # ensure header date is valid (pos 9:17)
        if header:
            hd = header[:240]
            date_field = hd[9:17]
            try:
                _dt.datetime.strptime(date_field, "%Y%m%d")
            except Exception:
                today = _dt.datetime.now().strftime("%Y%m%d")
                hd = hd[:9] + today + hd[17:]
                header = hd
        else:
            today = _dt.datetime.now().strftime("%Y%m%d")
            header = ("100" + " " * 6 + today + " " * (240 - 17))[:240]

        # compute totals from details
        total_details = len(details)
        total_value = 0
        for ln in details:
            val_slice = ln[17:32]
            val_str = val_slice.strip()
            if val_str.isdigit():
                total_value += int(val_str)

        total_registros_field = str(total_details).rjust(8, "0")
        total_valor_field = str(total_value).rjust(15, "0")

        if trailers:
            trailer_template = trailers[-1].ljust(240)
            new_trailer = trailer_template[:9] + total_registros_field + total_valor_field + trailer_template[32:240]
        else:
            new_trailer = ("300" + " " * 6 + total_registros_field + total_valor_field + " " * (240 - 32))[:240]

        fixed_lines = [header[:240].ljust(240)]
        fixed_lines.extend([ln[:240].ljust(240) for ln in details])
        fixed_lines.append(new_trailer[:240].ljust(240))

        batch_name = f"{ret_file.stem}_fixed_{idx:03}.d"
        batch_path = fixed_dir / batch_name
        with batch_path.open("w", encoding="utf-8") as fh:
            for l in fixed_lines:
                fh.write(l + "\n")
        generated_fixed.append(batch_path)

    # Persist logs
    with Path("fix_pipeline.log").open("w", encoding="utf-8") as fh:
        fh.write("\n".join(report_lines))
    with Path("resumo_leigo.txt").open("w", encoding="utf-8") as fh:
        fh.write("\n".join(resumo_leigo))

    print(f"✅ {len(generated_fixed)} arquivos corrigidos gerados em {fixed_dir}")
    return generated_fixed


def main(argv: List[str] | None = None) -> int:
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    if not argv or len(argv) != 1:
        print("Uso: python3 diagnose_pipeline.py <path_para_json>")
        return 2

    json_path = Path(argv[0])
    if not json_path.exists():
        print(f"Arquivo JSON não encontrado: {json_path}")
        return 2

    fixed = diagnose_and_fix(json_path)

    # Re-run paranarobot on the fixed file(s)
    for f in fixed:
        try:
            print(f"🔁 Reexecutando paranarobot (main.py) sobre {f} ...")
            subprocess.run(["python3", "main.py", str(f)], check=False)
        except Exception as exc:
            print(f"Falha ao reexecutar main.py sobre {f}: {exc}")

    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
