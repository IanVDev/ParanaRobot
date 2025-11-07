"""Upload manager: monitors an input directory for MAC×CON batches and runs ParanaRobot pipeline.

Behavior
- Watch a base input directory (default ./input) for subfolders or files containing MAC/CON zips.
- For each lot (a directory with zips or a pair of files sharing a common identifier),
  run: Unzipper -> Sanitizer -> FHMLMacConValidator -> Reporter
- Write a `.processed` marker file in the lot folder after successful processing to avoid reprocessing.
- Log to console and to `./logs/paranarobot_<YYYYMMDD>.log`.

Usage
    python3 upload_manager.py --watch ./input --once
    python3 upload_manager.py --watch ./input

"""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from modules.unzipper import Unzipper
from modules.sanitizer import Sanitizer
from modules.validator import Validator
from modules.reporter import Reporter
from modules.fhml_mac_con_validator import FHMLMacConValidator
from modules.utils import (
    ValidationSummary,
    FileMetadata,
    ValidationStatus,
    configure_logging,
)


@dataclass
class ManagerConfig:
    watch_dir: Path
    reports_dir: Path
    logs_dir: Path
    poll_interval: int
    once: bool


def setup_logger(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d")
    log_path = logs_dir / f"paranarobot_{ts}.log"

    logger = logging.getLogger("upload_manager")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(ch)
        logger.addHandler(fh)
    return logger


def find_lots(base: Path) -> List[Path]:
    """Return candidate lot directories under base.

    A lot is either a subdirectory of base or base itself if it contains zip(s).
    """
    lots: List[Path] = []
    if not base.exists():
        return lots
    # subdirectories are considered lots
    for p in base.iterdir():
        if p.is_dir():
            lots.append(p)
    # also consider files under base as a flat lot
    has_zips = any(p.suffix.lower() == ".zip" for p in base.iterdir())
    if has_zips:
        lots.append(base)
    return lots


def detect_mac_con_pair(lot_dir: Path, logger: logging.Logger) -> Optional[Tuple[Path, Path]]:
    """Try to discover a MAC and CON zip pair in lot_dir.

    Strategy:
    - Look for files containing 'MAC' and 'CON' in their names.
    - Prefer pairs where replacing 'MAC' with 'CON' (case-insensitive) yields an existing filename.
    - Otherwise, pick the first MAC and the first CON found.
    """
    files = [p for p in lot_dir.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]
    macs = [p for p in files if "MAC" in p.name.upper()]
    cons = [p for p in files if "CON" in p.name.upper()]
    if not macs:
        logger.debug("No MAC files in %s", lot_dir)
        return None
    if not cons:
        logger.debug("No CON files in %s", lot_dir)
        return None

    # try exact replace match
    for mac in macs:
        target_name = mac.name.upper().replace("MAC", "CON")
        for c in cons:
            if c.name.upper() == target_name:
                return mac, c

    # fallback: return first pair
    return macs[0], cons[0]


def mark_processed(lot_dir: Path, logger: logging.Logger) -> None:
    try:
        marker = lot_dir / ".processed"
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        logger.info("Marked %s as processed", lot_dir)
    except Exception as exc:
        logger.exception("Failed to mark processed for %s: %s", lot_dir, exc)


def is_processed(lot_dir: Path) -> bool:
    return (lot_dir / ".processed").exists()


def process_pair(mac_zip: Path, con_zip: Path, cfg: ManagerConfig, logger: logging.Logger) -> bool:
    logger.info("Processing pair: MAC=%s CON=%s", mac_zip.name, con_zip.name)
    unzipper = Unzipper()
    sanitizer = Sanitizer()
    validator = Validator()
    maccon_validator = FHMLMacConValidator()
    reporter = Reporter()

    # Extract MAC
    mac_extract = unzipper.extract(mac_zip)
    if mac_extract.error or mac_extract.metadata is None:
        logger.error("Failed to extract MAC %s: %s", mac_zip, mac_extract.error)
        return False
    mac_meta: FileMetadata = mac_extract.metadata

    # Extract CON
    con_extract = unzipper.extract(con_zip)
    if con_extract.error or con_extract.metadata is None:
        logger.error("Failed to extract CON %s: %s", con_zip, con_extract.error)
        return False
    con_meta: FileMetadata = con_extract.metadata

    # Sanitize both
    mac_s = sanitizer.sanitize(mac_meta.working_path)
    con_s = sanitizer.sanitize(con_meta.working_path)

    if mac_s.section.status == ValidationStatus.ERROR:
        logger.error("MAC sanitization failed for %s", mac_zip)
        return False
    if con_s.section.status == ValidationStatus.ERROR:
        logger.error("CON sanitization failed for %s", con_zip)
        return False

    # Structural validate MAC (to obtain record counters)
    structure_result = validator.validate(mac_s.lines)

    # Run MAC x CON comparison
    maccon_result = maccon_validator.validate_pair(mac_s.lines, con_s.lines)

    # Build summary (minimal) and render reports
    summary = ValidationSummary(
        metadata=mac_meta,
        structure=structure_result.section,
        encoding=mac_s.section,
        content=maccon_result.section,
        record_counters=structure_result.record_counters,
        totalizers=maccon_result.totalizers,
        newline=mac_s.newline,
        offending_codepoints=mac_s.offending_codepoints,
    )

    try:
        report_paths = reporter.render(summary, cfg.reports_dir)
        logger.info("Reports written: %s, %s", report_paths.json_path, report_paths.txt_path)
    except Exception as exc:
        logger.exception("Failed to render reports for %s: %s", mac_zip, exc)
        return False

    return True


def run_manager(cfg: ManagerConfig) -> None:
    logger = setup_logger(cfg.logs_dir)
    logger.info("Starting UploadManager watching %s", cfg.watch_dir)

    while True:
        lots = find_lots(cfg.watch_dir)
        for lot in lots:
            try:
                if is_processed(lot):
                    logger.debug("Skipping already processed lot %s", lot)
                    continue
                pair = detect_mac_con_pair(lot, logger)
                if not pair:
                    logger.debug("No MAC×CON pair detected in %s", lot)
                    continue
                mac_zip, con_zip = pair
                ok = process_pair(mac_zip, con_zip, cfg, logger)
                if ok:
                    mark_processed(lot, logger)
            except Exception:
                logger.exception("Unhandled exception processing lot %s", lot)

        if cfg.once:
            logger.info("Run-once requested — exiting")
            break
        time.sleep(cfg.poll_interval)


def parse_args(argv: Optional[list[str]] = None) -> ManagerConfig:
    parser = argparse.ArgumentParser(description="Upload manager for ParanaRobot")
    parser.add_argument("--watch", default="./input", help="Base input directory to watch")
    parser.add_argument("--reports", default="./reports", help="Base reports directory")
    parser.add_argument("--logs", default="./logs", help="Logs directory")
    parser.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run once and exit (no continuous watching)")
    args = parser.parse_args(argv)

    return ManagerConfig(
        watch_dir=Path(args.watch).expanduser().resolve(),
        reports_dir=Path(args.reports).expanduser().resolve(),
        logs_dir=Path(args.logs).expanduser().resolve(),
        poll_interval=args.poll_interval,
        once=args.once,
    )


if __name__ == "__main__":
    cfg = parse_args()
    # Configure root logging for library modules
    configure_logging()
    run_manager(cfg)
