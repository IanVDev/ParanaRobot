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
import json
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
    files = [f for f in INPUT_DIR.iterdir() if f.is_file() and not f.name.startswith('.')]
    if len(files) != 2:
        raise RuntimeError("Coloque exatamente 2 arquivos (MAC e CON) na pasta input/")

    # Preferência por nomes: se um arquivo tem 'MAC' no nome, considere-o MAC; se tem 'CON', considere CON.
    names = {f.name.lower(): f for f in files}
    mac_candidate = None
    con_candidate = None
    for name, path in names.items():
        if 'mac' in name:
            mac_candidate = path
        if 'con' in name:
            con_candidate = path

    # Se ambos identificados por nome, use as escolhas.
    if mac_candidate and con_candidate:
        mac_file = mac_candidate
        con_file = con_candidate
    else:
        # Fallback para heurística por contagem de linhas tipo '2' em diferentes encodings
        def try_open_count(path, encoding):
            try:
                with open(path, 'r', encoding=encoding, errors='ignore') as f:
                    lines = [line for line in f.readlines() if line.strip()]
                return sum(1 for l in lines if l.strip().startswith('2'))
            except Exception:
                return 0

        results = []
        for file in files:
            count_latin = try_open_count(file, 'latin-1')
            count_cp500 = try_open_count(file, 'cp500')
            if count_latin >= count_cp500:
                encoding = 'latin-1'
                count_final = count_latin
            else:
                encoding = 'cp500'
                count_final = count_cp500
            results.append((file, encoding, count_final))

        # Ordena: o arquivo com mais linhas tipo "2" é o MAC
        results.sort(key=lambda x: x[2], reverse=True)
        mac_file, mac_enc, _ = results[0]
        con_file, con_enc, _ = results[1]

        # recompute encodings for the chosen pair (ensure both encoding values are set)
        # if name-based selection wasn't possível, return computed encodings
        print(f"[INFO] MAC file: {mac_file.name} (encoding={mac_enc})")
        print(f"[INFO] CON file: {con_file.name} (encoding={con_enc})")
        return mac_file, mac_enc, con_file, con_enc

    # Se chegamos aqui, usamos a identificação por nome; detectar encodings separadamente
    def detect_enc(path):
        # test latin-1 vs cp500
        for enc in ('latin-1', 'cp500'):
            try:
                with open(path, 'r', encoding=enc, errors='ignore') as f:
                    lines = [l for l in f.readlines() if l.strip()]
                # se houver pelo menos uma linha tipo '2' com esse encoding, aceite
                if any(l.strip().startswith('2') for l in lines):
                    return enc
            except Exception:
                continue
        return 'latin-1'

    mac_enc = detect_enc(mac_file)
    con_enc = detect_enc(con_file)
    print(f"[INFO] MAC file: {mac_file.name} (encoding={mac_enc})")
    print(f"[INFO] CON file: {con_file.name} (encoding={con_enc})")
    return mac_file, mac_enc, con_file, con_enc

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
def build_fhmlret11(mac, con, out_path: Path):
    """Build FHMLRET11 into the given out_path (Path). Returns (out_path, details_count, total_valor)."""
    now = datetime.now()
    data_geracao = now.strftime("%Y%m%d")
    competencia = now.strftime("%Y%m")

    seq = 1
    total_valor = 0
    details_written = 0

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
            details_written += 1

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
    return out_path, details_written, total_valor

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

    # prepare run directories
    now = datetime.now()
    run_ts = now.strftime("%Y%m%d_%H%M%S")
    run_dir = BASE_DIR / "runs" / f"{run_ts}_TESTE_RET11"
    inputs_dir = run_dir / "inputs"
    outputs_dir = run_dir / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # copy original input files into run inputs
    shutil.copy(mac_path, inputs_dir / mac_path.name)
    shutil.copy(con_path, inputs_dir / con_path.name)

    # debug print and comparison (console)
    debug_show_records(mac, con)
    debug_compare(mac, con)

    # compute inconsistencies using comparar() and filter only 16/17
    inconsistencias = comparar(mac, con)
    inconsistencias_16_17 = [ (k, c, v) for (k,c,v) in inconsistencias if c in ("16","17") ]

    # build RET11 into run outputs
    out_filename = f"{STEM}.{run_ts}.FHMLRET11_final.d"
    out_path = outputs_dir / out_filename
    written_path, details_count, total_val = build_fhmlret11(mac, con, out_path)

    # copy final RET11 to ready/ for quick access
    READY_DIR.mkdir(exist_ok=True)
    shutil.copy(written_path, READY_DIR / written_path.name)

    # write CSV report of inconsistencies (only 16/17)
    csv_path = outputs_dir / "relatorio_inconsistencias.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("lote,nb,cs_ocorrencia,valor\n")
        for (lote_nb, cs, valor) in inconsistencias_16_17:
            lote, nb = lote_nb
            val_digits = "".join(ch for ch in (valor or "") if ch.isdigit())
            f.write(f"{lote},{nb},{cs},{val_digits}\n")

    # write summary.json
    summary = {
        "run": run_ts,
        "inputs": {"mac": mac_path.name, "con": con_path.name, "records_mac": len(mac), "records_con": len(con)},
        "details_written": details_count,
        "total_valor": total_val,
        "breakdown": {
            "16": sum(1 for _ in inconsistencias_16_17 if _[1]=="16"),
            "17": sum(1 for _ in inconsistencias_16_17 if _[1]=="17"),
        }
    }
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # write a simple README_run.txt and logs.txt
    with open(run_dir / "README_run.txt", "w", encoding="utf-8") as f:
        f.write(f"Run: {run_ts}\n")
        f.write(f"MAC input: {mac_path.name}\n")
        f.write(f"CON input: {con_path.name}\n")
        f.write(f"RET11 produced: outputs/{written_path.name}\n")
        f.write(f"Details written: {details_count}\n")

    with open(outputs_dir / "logs.txt", "w", encoding="utf-8") as f:
        f.write("DEBUG compare summary:\n")
        for (lote_nb, cs, valor) in inconsistencias_16_17:
            lote, nb = lote_nb
            f.write(f"{lote},{nb},{cs},{valor}\n")

    print(f"✅ Run artifacts written to: {run_dir}")
    print(f"✅ RET11 copied to ready/{written_path.name}")

if __name__ == "__main__":
    main()
