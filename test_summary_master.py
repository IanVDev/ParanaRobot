#!/usr/bin/env python3
"""
ParanaRobot — Geração de summary_master.json + Teste completo

Este script:
1. Gera arquivos MAC e CON sintéticos (para teste seguro)
2. Executa o pipeline completo via `python3 paranarobot.py --run`
3. Garante que o robô moveu os arquivos testados corretamente
4. Cria ou atualiza um arquivo reports/summary_master.json
   consolidando todos os lotes processados, com data, nomes e status
"""

import os
import json
from datetime import datetime
from pathlib import Path
import subprocess

BASE = Path(__file__).parent
INPUT_DIR = BASE / "input" / "arquivos_para_comparacao"
TESTED_DIR = BASE / "input" / "ja_testados"
REPORTS_DIR = BASE / "reports"
SUMMARY_MASTER = REPORTS_DIR / "summary_master.json"

# 1️⃣ Garantir estrutura de pastas
for d in [INPUT_DIR, TESTED_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 2️⃣ Gerar arquivos sintéticos de teste
mac_file = INPUT_DIR / "HMLMAC12.TESTE001.txt"
con_file = INPUT_DIR / "HMLCON12.TESTE001.txt"


def make_header():
    return "100TESTHEADER".ljust(240)


def make_detail(value: int) -> str:
    # create a 240-char record, code '200' and numeric value in slice 17:32 (15 chars)
    arr = [" "] * 240
    arr[0:3] = list("200")
    sval = str(value).rjust(15, "0")
    for i, ch in enumerate(sval):
        arr[17 + i] = ch
    return "".join(arr)


def make_trailer():
    return "300TESTTRAILER".ljust(240)

# create header, 10 details with numeric values, and trailer
header = make_header()
details = [make_detail(1000 + i) for i in range(10)]
trailer = make_trailer()

mac_file.write_text("\n".join([header] + details + [trailer]) + "\n")
con_file.write_text("\n".join([header] + details + [trailer]) + "\n")

print(f"🧩 Arquivos sintéticos criados:\n- {mac_file.name}\n- {con_file.name}")

# 3️⃣ Executar o pipeline completo
print("\n🚀 Rodando ParanaRobot...")
subprocess.run(["python3", "paranarobot.py", "--run"], check=False)

# 4️⃣ Localizar resultado do tested.log
tested_log = TESTED_DIR / "tested.log"
if tested_log.exists():
    last_line = tested_log.read_text().splitlines()[-1]
    print(f"\n📄 Último registro em tested.log:\n{last_line}")
    parts = last_line.split("\t")
    if len(parts) >= 4:
        status = parts[3].strip()
    else:
        status = "UNKNOWN"
else:
    print("\n⚠️ Nenhum tested.log encontrado. Verifique se o robô rodou corretamente.")
    status = "UNKNOWN"

# 5️⃣ Atualizar ou criar summary_master.json
entry = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "mac": mac_file.name,
    "con": con_file.name,
    "status": status,
}

summary = []
if SUMMARY_MASTER.exists():
    try:
        summary = json.loads(SUMMARY_MASTER.read_text())
    except Exception:
        pass

summary.append(entry)
SUMMARY_MASTER.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(f"\n✅ summary_master.json atualizado em {SUMMARY_MASTER}")

# 6️⃣ Mostrar resumo final
print("\n📊 Últimas execuções registradas:")
for row in summary[-5:]:
    print(f"• {row['timestamp']} — {row['mac']} x {row['con']} → {row['status']}")

# 7️⃣ Verificações automáticas de comportamento (para CI)
import sys

ok = True
errors = []

# tested.log exists and last line references our files
if not tested_log.exists():
    ok = False
    errors.append("tested.log not found")
else:
    try:
        last_line = tested_log.read_text().splitlines()[-1]
        if mac_file.name not in last_line or con_file.name not in last_line:
            ok = False
            errors.append("tested.log last line does not reference test files")
    except Exception as e:
        ok = False
        errors.append(f"failed reading tested.log: {e}")

# originals moved: check latest subfolder in ja_testados contains the files
moved_ok = False
try:
    subs = [p for p in TESTED_DIR.iterdir() if p.is_dir()]
    subs = sorted(subs, key=lambda p: p.stat().st_mtime, reverse=True)
    if subs:
        latest = subs[0]
        names = [p.name for p in latest.iterdir()]
        if mac_file.name in names and con_file.name in names:
            moved_ok = True
        else:
            errors.append(f"originals not found in latest ja_testados subdir: {latest}")
            ok = False
    else:
        errors.append("no subfolders in ja_testados found")
        ok = False
except Exception as e:
    ok = False
    errors.append(f"error checking ja_testados: {e}")

# summary_master.json contains an entry for our run (last entry)
try:
    if SUMMARY_MASTER.exists():
        sm = json.loads(SUMMARY_MASTER.read_text(encoding="utf-8"))
        if isinstance(sm, list) and sm:
            last = sm[-1]
            if last.get("mac") == mac_file.name and last.get("con") == con_file.name:
                pass
            else:
                ok = False
                errors.append("summary_master.json last entry does not match test files")
        else:
            ok = False
            errors.append("summary_master.json empty or invalid")
    else:
        ok = False
        errors.append("summary_master.json not found")
except Exception as e:
    ok = False
    errors.append(f"failed reading summary_master.json: {e}")

# Print final colored result and exit accordingly
GREEN = "\u001b[32m"
RED = "\u001b[31m"
RESET = "\u001b[0m"

if ok:
    print(f"\n{GREEN}🟢 Fluxo completo OK{RESET}")
    sys.exit(0)
else:
    print(f"\n{RED}🔴 Falha em alguma etapa — veja erros abaixo{RESET}")
    for e in errors:
        print(" - ", e)
    sys.exit(1)
