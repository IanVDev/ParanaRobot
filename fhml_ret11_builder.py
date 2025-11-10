"""
fhml_ret11_builder.py
Gera arquivos FHMLRET11 com 240 posições fixas conforme layout oficial.
"""
from datetime import datetime
from pathlib import Path


def pad(value: str, length: int, align: str = "left", filler: str = " "):
    """Preenche um campo para tamanho fixo."""
    value = str(value or "")
    if len(value) > length:
        value = value[:length]
    if align == "right":
        return value.rjust(length, filler)
    return value.ljust(length, filler)


def build_header(bank_id="254", date=None, system_name="CONPAG"):
    """Gera linha 100 (header)."""
    today = datetime.now().strftime("%Y%m%d")
    date = date or today
    line = (
        "100"                               # Tipo registro
        + pad(bank_id, 3, "left")           # ID Banco
        + pad("03", 2, "left")              # Código tipo lote / meio pagamento
        + pad(date, 8, "left")              # Data gravação lote
        + pad("01", 2, "left")              # Nº seq lote
        + pad(date, 8, "left")              # Data competência
        + pad(system_name, 10)              # Nome sistema
        + pad("", 240 - 3 - 3 - 2 - 8 - 2 - 8 - 10)  # Filler até 240
    )
    return line[:240]


def build_detail(nu_nb: str, valor: float, seq: int):
    """Gera linha 200 (detalhe)."""
    # valor em centavos como inteiro de 15 posições
    valor_cents = int(round(valor * 100))
    valor_str = f"{valor_cents:015d}"
    # make NB 10 chars (pos 11-20 per project conventions)
    nb_field = str(nu_nb).rjust(10, "0")[:10]
    line = (
        "200"
        + pad(nb_field, 10)                    # Nº Benefício (NB) positions 11-20
        + pad(datetime.now().strftime('%Y%m%d'), 8)  # Data fim período fictícia
        + pad(valor_str, 15, "right", "0")   # Valor
        + pad(str(seq).rjust(7, "0"), 7)      # NU-SEQ-REGISTRO (pos 2-8 in some layouts) - filler here
        + pad("", 240 - 3 - 10 - 8 - 15 - 7)  # Completa até 240
    )
    return line[:240]


def build_trailer(total_registros: int, total_valor: float):
    """Gera linha 300 (trailer)."""
    valor_cents = int(round(total_valor * 100))
    valor_str = f"{valor_cents:015d}"
    line = (
        "300"
        + pad("", 10)
        + pad(str(total_registros), 8, "right", "0")
        + pad(valor_str, 15, "right", "0")
        + pad("03", 2)
        + pad("", 240 - 3 - 10 - 8 - 15 - 2)
    )
    return line[:240]


def generate_fhmlret11(output_path: Path, registros: list):
    """
    Gera um arquivo FHMLRET11 completo.
    registros: lista de dicionários {"nu_nb": str, "valor": float}
    """
    lines = []
    lines.append(build_header())

    total_valor = 0.0
    for i, reg in enumerate(registros, start=1):
        nu_nb = reg.get("nu_nb") or str(70000000000 + i)
        valor = float(reg.get("valor", 0.0))
        total_valor += valor
        lines.append(build_detail(nu_nb, valor, i))

    lines.append(build_trailer(len(registros), total_valor))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    print(f"✅ Arquivo FHMLRET11 gerado em: {output_path}")
    return output_path


if __name__ == "__main__":
    # Exemplo de uso local
    base = Path("reports/HMLMAC12.TESTE_FINAL/corrigido")
    output = base / "HMLMAC12.TESTE_FINAL.FHMLRET11_final.d"
    registros_teste = [
        {"nu_nb": "207008244097", "valor": 1518.00},
        {"nu_nb": "207008244100", "valor": 1518.00},
        {"nu_nb": "207008244127", "valor": 1518.00},
        {"nu_nb": "207008244054", "valor": 1518.00},
        {"nu_nb": "207008244062", "valor": 3039.85},
        {"nu_nb": "207008244070", "valor": 1518.00},
        {"nu_nb": "207008244089", "valor": 1518.00},
        {"nu_nb": "207008244135", "valor": 1518.00},
        {"nu_nb": "207405159126", "valor": 1518.00},
        {"nu_nb": "217008244003", "valor": 1518.00},
    ]
    generate_fhmlret11(output, registros_teste)
