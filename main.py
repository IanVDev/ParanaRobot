"""CLI entry point for ParanaRobot."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence
import argparse
import logging
import shutil

from modules.analyzer import Analyzer
from modules.fhml_mac_validator import FHMLMacValidator
from modules.fhml_mac_validator_full import FHMLMacValidatorFull
from modules.fhml_mac_con_validator import FHMLMacConValidator
from modules.reporter import Reporter
from modules.sanitizer import Sanitizer
from modules.unzipper import Unzipper
from modules.validator import Validator
from modules.utils import (
    ValidationStatus,
    ValidationSummary,
    configure_logging,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validador automático FHML Dataprev")
    parser.add_argument("input", help="Arquivo FHML ou ZIP a ser validado")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        help="Diretório base para salvar relatórios (default: ./reports)",
    )
    parser.add_argument(
        "--no-cleanup",
        dest="cleanup",
        action="store_false",
        help="Não remove a pasta temporária gerada durante o processamento",
    )
    parser.set_defaults(cleanup=True)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Nível de log",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(getattr(logging, args.log_level.upper(), logging.INFO))

    logger = logging.getLogger(__name__)

    unzipper = Unzipper()
    sanitizer = Sanitizer()
    validator = Validator()
    analyzer = Analyzer()
    mac_validator = FHMLMacValidator()
    reporter = Reporter()

    extraction = unzipper.extract(Path(args.input))
    if extraction.error or extraction.metadata is None:
        logging.error("Falha durante extração: %s", extraction.error)
        return 2

    metadata = extraction.metadata
    sanitize_result = sanitizer.sanitize(metadata.working_path)
    structure_result = validator.validate(sanitize_result.lines)
    # detect layout by filename and pick the right semantic validator
    filename = metadata.working_path.name.upper()
    if "MAC" in filename:
        # prefer the full MAC validator when available
        mac_full = FHMLMacValidatorFull()
        mac_result = mac_full.validate(sanitize_result.lines)
        # ensure we always have an analysis_result object for later totalizers
        analysis_result = mac_result
        analysis_section = mac_result.section

        # attempt to locate a corresponding CON file in the same working directory
        con_lines = None
        try:
            working_dir = metadata.working_path.parent
            # look for any file containing 'CON' in the name (case-insensitive) and acceptable extensions
            candidate = next(
                (f for f in Path(working_dir).iterdir()
                 if "CON" in f.name.upper() and f.suffix.lower() in (".txt", ".d", "")),
                None,
            )
            if candidate:
                # Use Unzipper + Sanitizer to robustly prepare the CON file (handles ZIPs too)
                con_extraction = unzipper.extract(candidate)
                if con_extraction.error or con_extraction.metadata is None:
                    logging.getLogger(__name__).warning("Não foi possível extrair CON candidato %s: %s", candidate, con_extraction.error)
                else:
                    con_sanitize = sanitizer.sanitize(con_extraction.metadata.working_path)
                    if con_sanitize.section.status.name == 'ERROR':
                        logging.getLogger(__name__).warning("Sanitização CON retornou erro: %s", con_sanitize.section.issues)
                    con_lines = con_sanitize.lines
        except Exception as exc:
            logging.getLogger(__name__).exception("Erro ao localizar/ler arquivo CON: %s", exc)
            con_lines = None

        if con_lines:
            maccon = FHMLMacConValidator()
            try:
                mac_con_result = maccon.validate_pair(sanitize_result.lines, con_lines)
                # prefer mac_con_result when available
                analysis_result = mac_con_result
                analysis_section = mac_con_result.section
                # write RET11 generated to reports dir later via reporter (we'll attach to metadata as extra)
                metadata.generated_ret_lines = mac_con_result.ret_lines  # type: ignore[attr-defined]
                logger.info("Arquivo CON encontrado e comparado: %s", getattr(metadata, 'generated_ret_lines', None) and 'RET gerado')
            except Exception as exc:
                logger.exception('Erro ao validar MAC x CON: %s', exc)
                # keep analysis_result as mac_result
        else:
            logger.warning("Nenhum arquivo CON correspondente encontrado — usando análise MAC apenas.")
    else:
        analysis_result = analyzer.analyze(sanitize_result.lines)
        analysis_section = analysis_result.section

    summary = ValidationSummary(
        metadata=metadata,
        structure=structure_result.section,
        encoding=sanitize_result.section,
    content=analysis_section,
        record_counters=structure_result.record_counters,
        totalizers=analysis_result.totalizers,
        newline=sanitize_result.newline,
        offending_codepoints=sanitize_result.offending_codepoints,
    )

    base_dir = args.reports_dir.resolve() if args.reports_dir else Path(__file__).resolve().parent
    report_paths = reporter.render(summary, base_dir)

    print("Relatórios gerados:")
    print(f"- JSON: {report_paths.json_path}")
    print(f"- TXT: {report_paths.txt_path}")

    if args.cleanup:
        shutil.rmtree(metadata.temp_dir, ignore_errors=True)

    sections = [summary.structure, summary.encoding, summary.content]
    if any(section.status is ValidationStatus.ERROR for section in sections):
        return 2
    if any(section.status is ValidationStatus.WARN for section in sections):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
