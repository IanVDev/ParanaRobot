"""Generate ParanaRobot reports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import datetime as _dt

from .utils import (
    IssueSeverity,
    SectionReport,
    ValidationSummary,
    ensure_reports_dir,
    write_json,
    write_text,
)


@dataclass
class ReportPaths:
    """Location for generated artifacts."""

    json_path: Path
    txt_path: Path


class Reporter:
    """Materialize validation results into human-readable reports."""

    def render(self, summary: ValidationSummary, base_dir: Path) -> ReportPaths:
        reports_dir = ensure_reports_dir(base_dir)
        # create a subdirectory per lote/arquivo stem for better organization
        stem = summary.metadata.working_path.stem
        target_dir = reports_dir / stem
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
        json_path = target_dir / f"{stem}.{timestamp}.json"
        txt_path = target_dir / f"{stem}.{timestamp}.txt"

        json_payload = self._build_json(summary)
        text_payload = self._build_text(summary)

        write_json(json_path, json_payload)
        write_text(txt_path, text_payload)

        # If the validation produced a generated RET (MAC x CON), write it to disk
        generated = getattr(summary.metadata, "generated_ret_lines", None)
        if generated:
            # write as .FHMLRET11.d file under the same target dir
            ret_name = f"{stem}.{timestamp}.FHMLRET11.d"
            ret_path = target_dir / ret_name
            # join lines with newline and persist
            write_text(ret_path, "\n".join(generated) + "\n")
            # augment the json payload on disk with ret metadata (rewrite)
            # compute simple stats: counts of occurrences 16 and 17
            count_16 = sum(1 for line in generated if line[111:113] == "16")
            count_17 = sum(1 for line in generated if line[111:113] == "17")
            json_payload.setdefault("ret11", {})
            json_payload["ret11"]["path"] = str(ret_path)
            json_payload["ret11"]["count_16"] = count_16
            json_payload["ret11"]["count_17"] = count_17
            json_payload["ret11"]["detail_count"] = len([l for l in generated if l.startswith("2")])
            write_json(json_path, json_payload)

        return ReportPaths(json_path=json_path, txt_path=txt_path)

    def _build_json(self, summary: ValidationSummary) -> Dict[str, object]:
        return {
            "arquivo": summary.metadata.working_path.name,
            "origem": str(summary.metadata.original_path),
            "validacao": {
                "estrutura": summary.structure.status.value,
                "encoding": summary.encoding.status.value,
                "conteudo": summary.content.status.value,
                "erros": self._collect_messages(summary, IssueSeverity.CRITICAL),
                "avisos": self._collect_messages(summary, IssueSeverity.WARNING),
                "total_registros": summary.record_counters.total,
                "detalhes": summary.record_counters.details,
                "newline": summary.newline,
                "codepoints_invalidos": summary.offending_codepoints,
            },
            "totalizadores": {
                "soma_detalhes": summary.totalizers.detail_sum,
                "trailer": summary.totalizers.trailer_sum,
            },
            # ret11 will be injected if present during render()
        }

    def _build_text(self, summary: ValidationSummary) -> str:
        lines: List[str] = []
        lines.append(f"Arquivo: {summary.metadata.working_path.name}")
        lines.append(f"Origem: {summary.metadata.original_path}")
        lines.append("")
        lines.append("[Validação]")
        lines.append(f"- Estrutura: {summary.structure.status.value}")
        lines.append(f"- Encoding: {summary.encoding.status.value}")
        lines.append(f"- Conteúdo: {summary.content.status.value}")
        lines.append(f"- Total registros: {summary.record_counters.total}")
        lines.append(f"- Detalhes: {summary.record_counters.details}")
        lines.append(f"- Nova linha: {summary.newline}")
        if summary.offending_codepoints:
            lines.append(
                "- Codepoints substituídos: "
                + ", ".join(str(cp) for cp in summary.offending_codepoints)
            )
        lines.append("")

        criticals = self._collect_messages(summary, IssueSeverity.CRITICAL)
        warnings = self._collect_messages(summary, IssueSeverity.WARNING)

        if criticals:
            lines.append("[Erros]")
            lines.extend(f"- {msg}" for msg in criticals)
            lines.append("")
        if warnings:
            lines.append("[Avisos]")
            lines.extend(f"- {msg}" for msg in warnings)
            lines.append("")

        lines.append("[Totais]")
        lines.append(f"- Soma detalhes: {summary.totalizers.detail_sum}")
        lines.append(
            "- Valor trailer: "
            + (str(summary.totalizers.trailer_sum) if summary.totalizers.trailer_sum is not None else "não informado")
        )

        return "\n".join(lines) + "\n"

    def _collect_messages(self, summary: ValidationSummary, severity: IssueSeverity) -> List[str]:
        messages: List[str] = []
        for section in (summary.structure, summary.encoding, summary.content):
            for issue in section.issues:
                if issue.severity is severity:
                    message = issue.message
                    if issue.line_number is not None:
                        message = f"Linha {issue.line_number}: {message}"
                    messages.append(message)
        return messages


__all__ = ["Reporter", "ReportPaths"]
