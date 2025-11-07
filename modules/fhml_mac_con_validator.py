"""Validador que compara FHMLMAC12 (Maciça) com FHMLCON12 (Concessão) e gera FHMLRET11.

Regras principais implementadas (resumidas):
- Regra A (CS-OCORRENCIA=16): quando NU-CONTA-CORRENTE diferente entre Maciça e Concessão
  e NU-CPF-RECEBEDOR também diferente. Ambos os CPFs zerados (11 zeros) -> válido.
- Regra B (CS-OCORRENCIA=17): quando o CPF do recebedor for diferente e pelo menos uma das
  contas for não-zero (conta corrente), marca 17. Regra 16 tem precedência quando aplicável.

Gera uma lista de registros RET11 (240 bytes) contendo header, detalhes e trailer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

from .utils import (
    HEADER_CODE,
    DETAIL_CODE,
    TRAILER_CODE,
    IssueSeverity,
    SectionReport,
    ValidationIssue,
    RecordCounters,
    Totalizers,
    compute_status,
)

logger = logging.getLogger(__name__)


@dataclass
class FHMLMacConResult:
    section: SectionReport
    counters: RecordCounters
    totalizers: Totalizers
    ret_lines: List[str]


class FHMLMacConValidator:
    """Compara listas de linhas MAC x CON e produz RET11 com inconsistências 16/17.

    Expectativa: as listas já vêm como arrays de strings com 240 chars cada.
    """

    CPF_ZERO = "0" * 11
    CONTA_ZERO = "0" * 10

    def _extract_key(self, line: str) -> str:
        # NU-NB positions 11-20 (1-based) -> slice 10:20
        return line[10:20]

    def _extract_cpf(self, line: str) -> str:
        # NU-CPF-RECEBEDOR positions 49-59 -> slice 48:59
        return line[48:59]

    def _extract_conta(self, line: str) -> str:
        # NU-CONTA-CORRENTE positions 83-92 -> slice 82:92
        return line[82:92]

    def _make_ret_header(self, template_header: Optional[str] = None) -> str:
        # Build a simple RET11 header of 240 chars. Place required fields per spec.
        rec = [" "] * 240
        rec[0:3] = list(HEADER_CODE)
        # CS-TIPO-LOTE 9-10 -> positions 8:10, default "03" for inconsistentes
        rec[8:10] = list("03")
        # DT-GRAVAÇÃO-LOTE 16-23 -> leave spaces or copy from template if present
        if template_header:
            rec[15:23] = list(template_header[15:23])
        # NM-SISTEMA 32-37 -> "CONPAG"
        name = "CONPAG"
        rec[31:31+len(name)] = list(name)
        return "".join(rec)

    def _make_ret_detail(self, source_line: str, occurrence_code: Optional[str]) -> str:
        rec = list(source_line)
        # ensure length 240
        if len(rec) < 240:
            rec.extend([" "] * (240 - len(rec)))
        # CS-TIPO-REGISTRO stays as '2'
        # CS-OCORRENCIA positions 112-113 -> slice 111:113
        if occurrence_code:
            code = occurrence_code.rjust(2, "0")
            rec[111:113] = list(code)
        return "".join(rec[:240])

    def _make_ret_trailer(self, detail_count: int, total_value: int, template_trailer: Optional[str] = None) -> str:
        rec = [" "] * 240
        rec[0:3] = list(TRAILER_CODE)
        # QT-REG-DETALHE 14-21 -> slice 13:21 numeric right justified
        count_s = str(detail_count).rjust(8, "0")
        rec[13:21] = list(count_s)
        # VL-REG-DETALHE 22-38 -> slice 21:38 numeric right justified
        val_s = str(total_value).rjust(17, "0")
        rec[21:38] = list(val_s)
        # NUSEQLOTE 39-40 -> leave as '03'
        rec[38:40] = list("03")
        return "".join(rec)

    def validate_pair(self, mac_lines: List[str], con_lines: List[str]) -> FHMLMacConResult:
        issues: List[ValidationIssue] = []

        # Index CON by NU-NB
        con_map = {self._extract_key(line): line for line in con_lines if line[:3] == DETAIL_CODE}

        ret_lines: List[str] = []
        detail_values: List[int] = []
        detail_count = 0

        header_template = next((l for l in mac_lines if l[:3] == HEADER_CODE), None)
        trailer_template = next((l for l in mac_lines if l[:3] == TRAILER_CODE), None)

        # Emit header (RET header)
        ret_header = self._make_ret_header(header_template)
        ret_lines.append(ret_header)

        # Iterate mac details and compare with con
        for idx, line in enumerate(mac_lines, start=1):
            if line[:3] != DETAIL_CODE:
                continue
            detail_count += 1
            key = self._extract_key(line)
            mac_cpf = self._extract_cpf(line)
            mac_conta = self._extract_conta(line)
            con_line = con_map.get(key)
            occurrence: Optional[str] = None

            if con_line:
                con_cpf = self._extract_cpf(con_line)
                con_conta = self._extract_conta(con_line)

                # skip if both cpfs are zero
                if mac_cpf == self.CPF_ZERO and con_cpf == self.CPF_ZERO:
                    occurrence = None
                else:
                    # Rule A: both account AND cpf different -> 16
                    if mac_conta != con_conta and mac_cpf != con_cpf:
                        occurrence = "16"
                        issues.append(ValidationIssue(IssueSeverity.WARNING, f"Regra A: conta e CPF diferentes para NB {key}", record_type=DETAIL_CODE))
                    else:
                        # Rule B: CPF different and at least one account non-zero -> 17
                        if mac_cpf != con_cpf and (mac_conta != self.CONTA_ZERO or con_conta != self.CONTA_ZERO):
                            occurrence = "17"
                            issues.append(ValidationIssue(IssueSeverity.WARNING, f"Regra B: CPF diferente para NB {key}", record_type=DETAIL_CODE))
            else:
                # no matching concessão found; warn but do not mark occurrence
                issues.append(ValidationIssue(IssueSeverity.WARNING, f"Sem registro correspondente em CON para NB {key}", record_type=DETAIL_CODE))

            # build RET detail line based on mac line and occurrence
            ret_detail = self._make_ret_detail(line, occurrence)
            ret_lines.append(ret_detail)

            # parse value from mac detail for totals (positions 51-62 per RET spec -> slice 50:62)
            raw_val = line[50:62].strip()
            if raw_val.isdigit():
                detail_values.append(int(raw_val))
            else:
                detail_values.append(0)

        # build trailer with totals
        total_sum = sum(detail_values)
        ret_trailer = self._make_ret_trailer(detail_count, total_sum, trailer_template)
        ret_lines.append(ret_trailer)

        counters = RecordCounters(total=len(ret_lines), headers=1, details=detail_count, trailers=1)
        totalizers = Totalizers(detail_sum=total_sum, trailer_sum=total_sum)

        section = SectionReport(status=compute_status(issues), issues=issues)
        return FHMLMacConResult(section=section, counters=counters, totalizers=totalizers, ret_lines=ret_lines)


__all__ = ["FHMLMacConValidator", "FHMLMacConResult"]
