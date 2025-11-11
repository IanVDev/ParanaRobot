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

def detect_encoding_and_type():
    """Detecta qual arquivo é MAC e qual é CON, com fallback para cp500 (EBCDIC).

    Retorna: (mac_path, mac_encoding, con_path, con_encoding)
    """
    files = [f for f in INPUT_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
    if len(files) != 2:
        raise RuntimeError("Coloque exatamente 2 arquivos (MAC e CON) na pasta input/")

    def try_open(path, encoding):
        try:
            with open(path, "r", encoding=encoding, errors="ignore") as f:
                lines = [line for line in f.readlines() if line.strip()]
            count_2 = sum(1 for l in lines if l.strip().startswith("2"))
            return count_2
        except Exception:
            return 0

    results = []
    for file in files:
        count_latin = try_open(file, "latin-1")
        count_cp500 = try_open(file, "cp500")
        if count_latin >= count_cp500:
            encoding = "latin-1"
            count_final = count_latin
        else:
            encoding = "cp500"
            count_final = count_cp500
        results.append((file, encoding, count_final))

    # Ordena: o arquivo com mais linhas tipo "2" é o MAC
    results.sort(key=lambda x: x[2], reverse=True)
    mac_file, mac_enc, _ = results[0]
    con_file, con_enc, _ = results[1]

    print(f"[INFO] MAC file: {mac_file.name} (encoding={mac_enc})")
    print(f"[INFO] CON file: {con_file.name} (encoding={con_enc})")
    return mac_file, mac_enc, con_file, con_enc

def read_details(path: Path, encoding: str):
    """Lê linhas tipo 200 e extrai campos conforme doc (com codificação detectada)."""
    regs = {}
    with open(path, "r", encoding=encoding, errors="ignore") as f:
        for line in f:
            if not line.strip().startswith("2"):
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
    """Aplica Regras A e B da doc e retorna inconsistências (key, CS-OCORRENCIA, valor).

    Regras:
      - se CON ausente -> CS-OCORRENCIA = '99'
      - se tipo lote '20' e conta diferente -> '16'
      - se tipo lote '21' e cpf diferente -> '17'
      - registros consistentes (00) não são retornados
    """
    inconsistentes = []
    for key, reg_mac in mac.items():
        reg_con = con.get(key)
        if not reg_con:
            inconsistentes.append((key, "99", reg_mac.get("valor")))
            continue
        if key[0] == "20" and reg_mac.get("conta") != reg_con.get("conta"):
            inconsistentes.append((key, "16", reg_mac.get("valor")))
        elif key[0] == "21" and reg_mac.get("cpf") != reg_con.get("cpf"):
            inconsistentes.append((key, "17", reg_mac.get("valor")))
    return inconsistentes

def pad(line: str) -> str:
    return line[:240].ljust(240)

# ---------------- BUILDER FHMLRET11 ----------------
def build_fhmlret11(mac, con):
    now = datetime.now()
    data_geracao = now.strftime("%Y%m%d")
    competencia = now.strftime("%Y%m")
    timestamp = now.strftime("%Y%m%d%H%M%S")

    out_path = READY_DIR / f"{STEM}.{timestamp}.FHMLRET11_final.d"
    seq = 1
    total_valor = 0

    with open(out_path, "w", encoding="utf-8") as f:
        # HEADER
        header = (
            "1" + "0000001" + "03" + "254" + "01" +
            data_geracao + "03" + competencia +
            "CONPAG" + " " * 57 + "000001" + " " * 140
        )
        f.write(pad(header) + "\n")
        seq += 1

        # DETALHES – apenas inconsistentes
        for (lote, nu_nb), mac_data in mac.items():
            # ignora MAC consistente (00)
            if mac_data.get("cs_ocorrencia", "").strip() == "00":
                continue

            reg_con = con.get((lote, nu_nb))
            if not reg_con:
                continue  # ignora ausente no CON (não gera 99 mais)

            # Determina código de ocorrência com precedência conforme documento:
            # - se lote == '21' verifica CPF (17)
            # - se lote == '20' verifica Conta (16)
            cod = None
            if lote == '21' and mac_data.get("cpf") != reg_con.get("cpf"):
                cod = "17"
            elif lote == '20' and mac_data.get("conta") != reg_con.get("conta"):
                cod = "16"
            else:
                # sem divergência relevante para a regra do lote
                continue

            valor = int("".join(filter(str.isdigit, mac_data["valor"]))) if mac_data["valor"] else 0
            total_valor += valor

            detalhe = (
                "2" + f"{seq:07d}" +
                nu_nb.ljust(10) +
                "20250228" + "20250201" + "01" +
                data_geracao + "000001" +
                f"{valor:012d}" + "8" + "20250331" +
                " " * 40 + f"{cod}" + "01" + " " * 125
            )
            f.write(pad(detalhe) + "\n")
            seq += 1

        # TRAILER
        qtd = seq - 2  # desconta header
        trailer = (
            "3" + "0000001" + "03" + "254" +
            f"{qtd:08d}" + f"{total_valor:017d}" +
            "03" + f"{qtd:08d}" + f"{total_valor:017d}" +
            "00000000" + "00000000000000000" +
            "00000000" + "00000000000000000" +
            "00000000" + "00000000000000000" +
            " " * 100
        )
        f.write(pad(trailer) + "\n")

    print(f"✅ FHMLRET11 (somente inconsistentes) gerado: {out_path}")
    print("   ➤ Somente ocorrências 16 e 17 incluídas")
    print("   ➤ Linhas 240 bytes garantidas")
    return out_path

# ---------------- DEBUG: MOSTRAR CAMPOS EXTRAÍDOS ----------------
def debug_show_records(mac, con):
    print("\n🧭 DEBUG: primeiros registros extraídos (tipo 200)\n")
    print("Arquivo MAC:")
    for i, ((lote, nb), data) in enumerate(mac.items()):
        if i >= 5:
            break
        print(f"  Lote={lote} | NB={nb} | Conta={data['conta']} | CPF={data['cpf']} | Valor={data['valor']}")
    print("\nArquivo CON:")
    for i, ((lote, nb), data) in enumerate(con.items()):
        if i >= 5:
            break
        print(f"  Lote={lote} | NB={nb} | Conta={data['conta']} | CPF={data['cpf']} | Valor={data['valor']}")


def debug_compare(mac, con):
    print("\n🧩 DEBUG: comparando campos MAC × CON\n")
    for key, reg_mac in mac.items():
        reg_con = con.get(key)
        if not reg_con:
            print(f"  ❌ Ausente no CON: {key}")
            continue
        diff = []
        if reg_mac['conta'] != reg_con['conta']:
            diff.append(f"Conta: {reg_mac['conta']} ≠ {reg_con['conta']}")
        if reg_mac['cpf'] != reg_con['cpf']:
            diff.append(f"CPF: {reg_mac['cpf']} ≠ {reg_con['cpf']}")
        if reg_mac['valor'] != reg_con['valor']:
            diff.append(f"Valor: {reg_mac['valor']} ≠ {reg_con['valor']}")
        if diff:
            print(f"  ⚠️ Diferença em {key}: {', '.join(diff)}")
    print("\n✔️ Fim da verificação de divergências.\n")


# ---------------- MAIN ----------------
def main():
    clean_environment()
    mac_path, mac_enc, con_path, con_enc = detect_encoding_and_type()
    mac = read_details(mac_path, mac_enc)
    con = read_details(con_path, con_enc)
    # Opcional: mostrar debug resumido
    debug_show_records(mac, con)
    debug_compare(mac, con)

    # Gera arquivo contendo apenas inconsistências (a função build_fhmlret11
    # faz a filtragem interna por 16/17 conforme nova regra)
    build_fhmlret11(mac, con)

if __name__ == "__main__":
    main()
