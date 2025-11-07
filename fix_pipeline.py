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
import datetime as _dt

# reuse split_into_batches from project
from modules.utils import split_into_batches


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

        batch_name = f"{ret_file.stem}_fix_{idx:03}.d"
        batch_path = fixed_dir / batch_name
        with batch_path.open("w", encoding="utf-8") as fh:
            for l in fixed_lines:
                fh.write(l + "\n")
        generated_fixed.append(batch_path)

    # Save logs
    Path("fix_pipeline.log").write_text("\n".join(report_lines), encoding="utf-8")
    Path("resumo_leigo.txt").write_text("\n".join(resumo_leigo), encoding="utf-8")

    print(f"✅ {len(generated_fixed)} arquivos corrigidos gerados em {fixed_dir}")
    return generated_fixed


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

    # Re-run paranarobot on the fixed file(s) to update reports/summary
    fixed_dir = Path(json_path).parent.parent / "corrigido"
    summary_entries = []
    for f in (fixed if isinstance(fixed, list) else [fixed]):
        try:
            print(f"🔁 Reexecutando paranarobot (main.py) sobre {f} ...")
            subprocess.run(["python3", "main.py", str(f)], check=False)
        except Exception as exc:
            print(f"Falha ao reexecutar main.py sobre {f}: {exc}")

        # try to find the generated JSON that references this file in its 'origem'
        status = "UNKNOWN"
        found_json = None
        for jf in Path("reports").rglob("*.json"):
            try:
                with jf.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                origem_val = payload.get("origem")
                if origem_val == str(f) or origem_val == str(Path(f).resolve()):
                    found_json = jf
                    status = payload.get("validacao", {}).get("conteudo", "UNKNOWN")
                    break
            except Exception:
                continue

        entry = {
            "fixed_file": str(f),
            "status": status,
            "report_json": str(found_json) if found_json else None,
        }
        summary_entries.append(entry)

    # write a summary_multilot.json in the corrigido directory
    summary_path = fixed_dir / "summary_multilot.json"
    overall = "OK"
    for e in summary_entries:
        if e["status"] == "ERROR":
            overall = "ERROR"
            break
        if e["status"] == "WARN" and overall != "ERROR":
            overall = "WARN"

    summary_payload = {
        "arquivo": Path(json_path).parent.parent.name,
        "generated": summary_entries,
        "status_geral": overall,
    }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary_payload, fh, indent=2, ensure_ascii=False)

    print(f"✅ summary_multilot escrito em {summary_path}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
