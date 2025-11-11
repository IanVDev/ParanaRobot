#!/usr/bin/env python3
"""
Gerador sintético de arquivos MAC e CON para testar cenários de inconsistência.

Gera dois arquivos em ./input/:
 - HMLMAC12.TESTE_MAC.txt (arquivo MAC)
 - HMLCON12.TESTE_CON.txt (arquivo CON)

Cria 10 registros tipo '2' no formato esperado por `finalize_pipeline.read_details`.

Uso:
  python3 scripts/generate_test_files.py

"""
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "input"
INPUT.mkdir(exist_ok=True)

def make_line(lote: str, nb: str, conta: str, cpf: str, valor: str) -> str:
    # cria uma linha de 240 caracteres com campos em posições esperadas por finalize_pipeline
    # índices (conforme read_details): lote [8:10], nu_nb [10:20], cpf [48:59], valor [50:62], conta [82:92]
    line = list(" " * 240)
    line[0] = "2"
    # lote at 8:10
    for i, ch in enumerate(lote[:2]):
        line[8 + i] = ch
    # nu_nb at 10:20 (10 chars)
    for i, ch in enumerate(nb.ljust(10)[:10]):
        line[10 + i] = ch
    # cpf at 48:59 (11 chars)
    for i, ch in enumerate(cpf.ljust(11)[:11]):
        line[48 + i] = ch
    # valor at 50:62 (12 chars) - fill only digits
    for i, ch in enumerate(valor.rjust(12, "0")[:12]):
        line[50 + i] = ch
    # conta at 82:92 (10 chars)
    for i, ch in enumerate(conta.ljust(10)[:10]):
        line[82 + i] = ch
    return "".join(line)

def alter_cpf(cpf: str) -> str:
    # muda o último dígito (simples)
    if not cpf or not cpf[-1].isdigit():
        return cpf
    last = int(cpf[-1])
    new_last = (last + 1) % 10
    return cpf[:-1] + str(new_last)

def alter_conta(conta: str) -> str:
    # altera 1 dígito no meio da conta
    if len(conta) < 5:
        return conta
    lst = list(conta.ljust(10, "0"))
    idx = 2
    if not lst[idx].isdigit():
        lst[idx] = "9"
    else:
        lst[idx] = str((int(lst[idx]) + 1) % 10)
    return "".join(lst)

def main():
    # base values
    base_conta = "0001234567"
    base_cpf = "12345678901"  # 11 dígitos
    base_valor = "000000001234"  # 12 dígitos

    records = []
    # We'll create 10 NBs; first 3 are the target scenarios (CPF diff, Conta diff, Both);
    # remaining 7 are consistent (copiados)
    now = datetime.now()
    data_tag = now.strftime("%Y%m%d%H%M%S")

    # Scenario 1: CPF different (lote '21') -> CS 17
    records.append(("21", "7000000001", base_conta, alter_cpf(base_cpf), base_valor, 'cpf_diff'))
    # Scenario 2: Conta different (lote '20') -> CS 16
    records.append(("20", "7000000002", alter_conta(base_conta), base_cpf, base_valor, 'conta_diff'))
    # Scenario 3: Both different (lote '21') -> CS 17 (precedence CPF)
    records.append(("21", "7000000003", alter_conta(base_conta), alter_cpf(base_cpf), base_valor, 'both_diff'))

    # Remaining records: consistent
    for i in range(4, 11):
        nb = f"70000000{i:02d}"
        records.append(("20" if i % 2 == 0 else "21", nb, base_conta, base_cpf, base_valor, 'consistent'))

    mac_lines = []
    con_lines = []

    # optional header (tipo 1)
    header = "1" + " " * 239
    mac_lines.append(header)
    con_lines.append(header)

    for lote, nb, mac_conta, mac_cpf, mac_valor, tag in records:
        # MAC record
        mac_line = make_line(lote, nb, mac_conta, mac_cpf, mac_valor)
        mac_lines.append(mac_line)

        # CON: for inconsistent scenarios, create the divergent or identical counterpart
        if tag == 'cpf_diff':
            # CON will have original CPF (so differs)
            con_conta = mac_conta
            con_cpf = '12345678901'  # original
        elif tag == 'conta_diff':
            con_conta = '0001234567'
            con_cpf = mac_cpf
        elif tag == 'both_diff':
            # CON stays original to force both differences
            con_conta = '0001234567'
            con_cpf = '12345678901'
        else:
            con_conta = mac_conta
            con_cpf = mac_cpf

        con_line = make_line(lote, nb, con_conta, con_cpf, mac_valor)
        con_lines.append(con_line)

    # optional trailer (tipo 3)
    trailer = "3" + " " * 239
    mac_lines.append(trailer)
    con_lines.append(trailer)

    mac_path = INPUT / "HMLMAC12.TESTE_MAC.txt"
    con_path = INPUT / "HMLCON12.TESTE_CON.txt"

    with open(mac_path, "w", encoding="utf-8") as f:
        f.write("\n".join(mac_lines))

    with open(con_path, "w", encoding="utf-8") as f:
        f.write("\n".join(con_lines))

    print(f"🟢 Arquivos gerados: {mac_path}, {con_path}")
    print("   ➤ 10 registros (3 inconsistentes: cpf_diff, conta_diff, both_diff; 7 consistentes)")

if __name__ == '__main__':
    main()
