#!/usr/bin/env python3
"""ParanaRobot single-command runner.

Usage:
    python3 paranarobot.py --run

This will scan `input/arquivos_para_comparacao/`, detect MAC×CON pairs,
run the validation pipeline (via main.py), run diagnosis and fixes, finalize
and copy final artifacts to `input/arquivo_pronto_para_envio_connect/`.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from upload_manager import find_lots, detect_mac_con_pair, setup_logger

import diagnose_pipeline
import finalize_pipeline


def find_report_for_origin(origin: Path) -> Optional[Path]:
    """Search reports/ for a JSON whose 'origem' points to origin (or has origin name)."""
    origin_str = str(origin)
    candidate = None
    for jf in Path("reports").rglob("*.json"):
        try:
            payload = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        # only consider JSON objects (not arrays like summary_master.json)
        if not isinstance(payload, dict):
            continue
        origem = payload.get("origem") or payload.get("arquivo")
        if not origem:
            continue
        # match full path or filename
        if origem == origin_str or origem.endswith(origin.name) or str(jf.name).startswith(origin.name):
            if candidate is None or jf.stat().st_mtime > candidate.stat().st_mtime:
                candidate = jf
    return candidate


def process_lot(lot: Path, logger: logging.Logger) -> Dict[str, str]:
    """Process a lot and move originals to `ja_testados` with logging.

    Returns a dict with lot/status/reason.
    """
    logger.info("Processing lot: %s", lot)
    pair = detect_mac_con_pair(lot, logger)
    if not pair:
        logger.warning("No MAC×CON pair detected in %s", lot)
        return {"lot": str(lot), "status": "ERROR", "reason": "no_pair"}

    mac, con = pair
    logger.info("Detected MAC=%s CON=%s", mac.name, con.name)

    final_status = "ERROR"
    reason = "unhandled"

    try:
        # Run main.py on the MAC file to generate the initial report
        try:
            subprocess.run(["python3", "main.py", str(mac)], check=False)
        except Exception as exc:
            logger.exception("Failed to run main.py on %s: %s", mac, exc)
            return {"lot": str(lot), "status": "ERROR", "reason": "main_fail"}

        # Find the generated JSON for this MAC
        json_path = find_report_for_origin(mac)
        if not json_path:
            logger.error("Report JSON not found for %s", mac)
            return {"lot": str(lot), "status": "ERROR", "reason": "no_json"}

        # Diagnose & generate corrected files
        try:
            fixed_files = diagnose_pipeline.diagnose_and_fix(json_path)
        except SystemExit as se:
            logger.warning("Diagnose pipeline exited early: %s", se)
            fixed_files = []
        except Exception as exc:
            logger.exception("Diagnose pipeline failed for %s: %s", json_path, exc)
            return {"lot": str(lot), "status": "ERROR", "reason": "diagnose_fail"}

        if not fixed_files:
            logger.info("No fixed files generated for %s; skipping finalize", lot)
            final_status = "WARN"
            reason = "no_fixed"
            return {"lot": str(lot), "status": final_status, "reason": reason}

        # Re-validate each fixed file and finalize
        final_status = "ERROR"
        for f in fixed_files:
            try:
                subprocess.run(["python3", "main.py", str(f)], check=False)
            except Exception as exc:
                logger.exception("Failed to re-run main.py on fixed file %s: %s", f, exc)
                continue

            # find JSON for the fixed file
            jf = find_report_for_origin(f)
            if not jf:
                logger.warning("No report JSON found after re-validation for %s", f)
                continue

            # finalize using the revalidation JSON
            try:
                finalize_pipeline.finalize_and_revalidate(str(jf))
            except Exception as exc:
                logger.exception("Finalize pipeline failed for %s: %s", jf, exc)
                continue

            # read summary_final.json if present
            corr = Path(jf).parent.parent / "corrigido"
            summary = corr / "summary_final.json"
            if summary.exists():
                try:
                    payload = json.loads(summary.read_text(encoding="utf-8"))
                    st = payload.get("status") or "ERROR"
                    final_status = st
                    reason = "finalized"
                except Exception:
                    final_status = "ERROR"
    finally:
        # Ensure we move original files into ja_testados and log the attempt
        try:
            tested_dir = Path("input") / "ja_testados"
            tested_dir.mkdir(parents=True, exist_ok=True)

            # use timestamped subfolder to avoid collisions
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            dest_sub = tested_dir / ts
            dest_sub.mkdir(parents=True, exist_ok=True)

            # move mac and con
            moved = []
            for p in (mac, con):
                try:
                    if p.exists():
                        target = dest_sub / p.name
                        shutil.move(str(p), str(target))
                        moved.append(target.name)
                except Exception as exc:
                    logger.exception("Failed to move %s to %s: %s", p, dest_sub, exc)

            # if lot is a directory and is empty after moving, remove it
            try:
                if lot.is_dir() and not any(lot.iterdir()):
                    lot.rmdir()
            except Exception:
                pass

            # append to tested.log
            log_path = tested_dir / "tested.log"
            entry = f"{datetime.utcnow().isoformat()}\t{mac.name}\t{con.name}\t{final_status}\n"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(entry)
        except Exception:
            logger.exception("Failed to record tested.log or move originals for %s", lot)

    return {"lot": str(lot), "status": final_status, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser(description="ParanaRobot single-run processor")
    parser.add_argument("--run", action="store_true", help="Process all available lots")
    args = parser.parse_args()

    logger = setup_logger(Path("logs"))

    if not args.run:
        parser.print_help()
        return 0

    base = Path("input") / "arquivos_para_comparacao"
    # ensure the input directory exists to avoid confusion for operators
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        logger.warning("Diretório %s não existia — criado automaticamente. Coloque lotes dentro dele e reexecute.", base)

    lots = find_lots(base)
    if not lots:
        logger.info("No lots found in %s", base)
        return 0

    summary = []
    for lot in lots:
        try:
            res = process_lot(lot, logger)
            summary.append(res)
        except Exception:
            logger.exception("Unhandled error processing lot %s", lot)
            summary.append({"lot": str(lot), "status": "ERROR", "reason": "unhandled"})

    # print a compact summary
    print("\n=== SUMMARY ===")
    for s in summary:
        status = s.get("status")
        lot = s.get("lot")
        icon = "❌"
        if status == "OK":
            icon = "✅"
        elif status == "WARN":
            icon = "⚠️"
        print(f"{icon} {lot} -> {status} ({s.get('reason')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
