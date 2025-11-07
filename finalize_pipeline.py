#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FINALIZE_PIPELINE FHMLRET11 — VERSÃO DEFINITIVA (GERA SEMPRE)
--------------------------------------------------------------
Gera o arquivo FHMLRET11 completo e conforme a doc oficial.

Estrutura:
  • HEADER (tipo 1)
  • DETALHES (tipo 2)
  • TRAILER (tipo 3)

Regras:
  - Gera o arquivo mesmo se não houver inconsistências.
  - Cada linha possui 240 bytes exatos.
  - Layout conforme documento oficial FHMLRET11.
  - Salva apenas o arquivo final em ./ready/.

Origem:
  ./input/ → dois arquivos: MAC (maciça) e CON (concessão)
Destino:
  ./ready/HMLMAC12.TESTE_FINAL.<timestamp>.FHMLRET11_final.d
"""

from pathlib import Path
import shutil
from datetime import datetime

# ---------------- CONFIGURAÇÕES ----------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
READY_DIR = BASE_DIR / "ready"
UNUSED_DIRS = ["reports", "tmp", "output", "outputs", "ret", "logs", "tests"]
STEM = "HMLMAC12.TESTE_FINAL"

# ---------------- FUNÇÕES AUXILIARES ----------------
def clean_environment():
    """Remove pastas antigas e mantém apenas input/ e ready/"""
    for folder in UNUSED_DIRS:
        path = BASE_DIR / folder
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
    READY_DIR.mkdir(exist_ok=True)

def list_input_files():
    """Lista exatamente 2 arquivos na pasta input (MAC e CON)"""
    files = [f for f in INPUT_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
    if not files:
        from os import listdir
        from os.path import join, isfile
        files = [Path(join(INPUT_DIR, n)) for n in listdir(INPUT_DIR)
                 if isfile(join(INPUT_DIR, n)) and not n.startswith(".")]
    if len(files) != 2:
        raise RuntimeError("Coloque exatamente 2 arquivos (MAC e CON) na pasta input/")
    return sorted(files)

def read_details(path: Path):
    """Lê linhas tipo 200 e extrai campos conforme doc"""
    regs = {}
    # Alguns arquivos de entrada podem ter encoding legacy (ISO-8859-1). Abrimos com latin-1 para robustez.
    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            if not line.startswith("2"):
                continue
            line = line.rstrip("\r\n").ljust(240)
            lote = line[8:10]
            nu_nb = line[10:20]
            conta = line[82:92]
            cpf = line[48:59]
            valor = line[50:62]
            regs[(lote, nu_nb)] = dict(line=line, conta=conta, cpf=cpf, valor=valor)
    return regs

def comparar(mac, con):
    """Aplica Regras A e B da doc, retorna inconsistências (key, CS-OCORRENCIA, valor)"""
    inconsistentes = []
    for key, reg_mac in mac.items():
        reg_con = con.get(key)
        if not reg_con:
            continue
        if key[0] == "20" and reg_mac["conta"] != reg_con["conta"]:
            inconsistentes.append((key, 16, reg_mac["valor"]))
        elif key[0] == "21" and reg_mac["cpf"] != reg_con["cpf"]:
            inconsistentes.append((key, 17, reg_mac["valor"]))
    return inconsistentes

def pad(line: str) -> str:
    return line[:240].ljust(240)

# ---------------- BUILDER FHMLRET11 ----------------
def build_fhmlret11(inconsistentes):
    now = datetime.now()
    data_geracao = now.strftime("%Y%m%d")
    competencia = now.strftime("%Y%m")
    timestamp = now.strftime("%Y%m%d%H%M%S")

    out_path = READY_DIR / f"{STEM}.{timestamp}.FHMLRET11_final.d"

    qtd = len(inconsistentes)
    total_valor = sum(
        int("".join(filter(str.isdigit, v))) if v else 0
        for (_, _, v) in inconsistentes
    )

    with open(out_path, "w", encoding="utf-8") as f:
        # HEADER ----------------------------------------------------
        header = (
            "1"                       # 01 CS-TIPO-REGISTRO
            + "0000001"               # 02–08 NU-SEQ-REGISTRO
            + "03"                    # 09–10 CS-TIPO-LOTE
            + "254"                   # 11–13 ID-BANCO
            + "01"                    # 14–15 CS-MEIO-PAGTO
            + data_geracao            # 16–23 DT-GRAVACAO-LOTE
            + "03"                    # 24–25 NU-SEQ-LOTE
            + competencia             # 26–31 DT-COMP-VENCIMEN
            + "CONPAG"                # 32–37 NM-SISTEMA
            + " " * 57                # 38–94 FILLER
            + "000001"                # 95–100 NU-CTRL-TRANS
            + " " * 140               # 101–240 FILLER
        )
        f.write(pad(header) + "\n")

        # DETALHES -------------------------------------------------
        seq = 1
        for (lote, nu_nb), cod, valor_str in inconsistentes:
            valor = int("".join(filter(str.isdigit, valor_str))) if valor_str else 0
            detalhe = (
                "2"                           # 01 CS-TIPO-REGISTRO
                + f"{seq:07d}"                # 02–08 NU-SEQ-REGISTRO
                + nu_nb.ljust(10)             # 09–18 NU-NB
                + "20250228"                  # 19–26 DT-FIM-PERIODO
                + "20250201"                  # 27–34 DT-INI-PERIODO
                + "01"                        # 35–36 CS-NATUR-CREDITO
                + data_geracao                # 37–44 DT-MOV-CREDITO
                + "000001"                    # 45–50 ID-ORGAO-PAGADOR
                + f"{valor:012d}"             # 51–62 VL-LIQ-CREDITO
                + "8"                         # 63 CS-UNID-MONET
                + "20250331"                  # 64–71 DT-FIM-VALIDADE
                + " " * 40                    # 72–111 FILLER
                + f"{cod:02d}"                # 112–113 CS-OCORRENCIA
                + "01"                        # 114–115 CS-ORIGEM-ORCAMENTO
                + " " * 125                   # 116–240 FILLER
            )
            f.write(pad(detalhe) + "\n")
            seq += 1

        # TRAILER --------------------------------------------------
        trailer = (
            "3"                             # 01 CS-TIPO-REGISTRO
            + "0000001"                     # 02–08 NU-SEQ-REGISTRO
            + "03"                          # 09–10 CS-TIPO-LOTE
            + "254"                         # 11–13 ID-BANCO
            + f"{qtd:08d}"                  # 14–21 QT-REG-DETALHE
            + f"{total_valor:017d}"         # 22–38 VL-REG-DETALHE
            + "03"                          # 39–40 NU-SEQ-LOTE
            + f"{qtd:08d}"                  # 41–48 QT-REG-DETALHE-FRGPS
            + f"{total_valor:017d}"         # 49–65 VL-REG-DETALHE-FRGPS
            + "00000000"                    # 66–73 QT-REG-DETALHE-LOAS
            + "00000000000000000"           # 74–90 VL-REG-DETALHE-LOAS
            + "00000000"                    # 91–98 QT-REG-DETALHE-EPU
            + "00000000000000000"           # 99–115 VL-REG-DETALHE-EPU
            + "00000000"                    # 116–123 QT-REG-DETALHE-EPEX
            + "00000000000000000"           # 124–140 VL-REG-DETALHE-EPEX
            + " " * 100                     # 141–240 FILLER
        )
        f.write(pad(trailer) + "\n")

    print(f"✅ FHMLRET11 final gerado: {out_path}")
    print("   ➤ Conforme DOC FHMLRET11 – Pronto para envio ao Connect")
    print("   ➤ Linhas 240 bytes garantidas")
    return out_path

# ---------------- MAIN ----------------
def main():
    clean_environment()
    mac_path, con_path = list_input_files()
    mac = read_details(mac_path)
    con = read_details(con_path)
    inconsistentes = comparar(mac, con)
    # Gera sempre o arquivo, mesmo se não houver inconsistências
    build_fhmlret11(inconsistentes)

if __name__ == "__main__":
    main()
