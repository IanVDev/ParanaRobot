# -*- coding: utf-8 -*-

"""
FINALIZE_PIPELINE.PY
--------------------

Objetivo:
- Ler DOIS arquivos na pasta ./input (ex: MAC e CON).
- Comparar registros de detalhe (linhas tipo "200") entre eles.
- Manter apenas os registros CONSISTENTES (presentes nos dois arquivos com mesmo identificador).
- Gerar UM ÚNICO arquivo final FHMLRET11 no layout:
    - 100: Header
    - 200: Detalhes
    - 900: Trailer
  com TODAS as linhas com 240 bytes exatos.
- Salvar SOMENTE em ./ready, sem gerar lixo em outras pastas.
- Limpar pastas antigas usadas em testes (menos é mais).

Instruções:
- Coloque os dois arquivos de entrada em ./input
- Ajuste, se necessário, as posições de nu_nb e valor na função extract_detail_key().
- Rode:
    python3 finalize_pipeline.py

Resultado:
- ./ready/<stem>.<timestamp>.FHMLRET11_final.d
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

# ==============================
# CONFIGURAÇÃO BÁSICA
# ==============================

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
READY_DIR = BASE_DIR / "ready"

# Pastas antigas que vamos limpar para não poluir
UNUSED_DIRS = [
    "reports",
    "tmp",
    "output",
    "outputs",
    "ret",
    "logs",
    "test",
    "tests",
    "input/ja_testados",
]

# Prefixo genérico do arquivo final (pode ajustar se quiser)
STEM = "HMLMAC12.TESTE_FINAL"


# ==============================
# FUNÇÕES UTILITÁRIAS
# ==============================

def log(msg: str):
    print(msg)


def safe_rmtree(path: Path):
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def ensure_ready_dir():
    READY_DIR.mkdir(exist_ok=True)


def clean_environment():
    """
    Remove pastas antigas/lixo de testes.
    Não mexe na pasta input.
    """
    log("🧹 Limpando ambiente antigo...")
    for folder in UNUSED_DIRS:
        path = BASE_DIR / folder
        if path.exists():
            safe_rmtree(path)
            log(f"   - Removido: {path}")
    ensure_ready_dir()
    log("✅ Ambiente limpo. Mantidos apenas 'input/' e 'ready/'.")


def find_input_files() -> List[Path]:
    """
    Localiza os arquivos na pasta input.
    Esperamos DOIS arquivos para comparação (ex: MAC e CON).
    """
    if not INPUT_DIR.exists():
        raise FileNotFoundError("Pasta 'input/' não encontrada.")

    # primeira tentativa: pathlib.iterdir()
    files = [f for f in INPUT_DIR.iterdir() if f.is_file() and not f.name.startswith('.')]

    # fallback seguro: alguns ambientes persistentes/sandbox podem não expor arquivos via iterdir()
    if not files:
        from os import listdir
        from os.path import join, isfile

        # debug: report listdir results in environments where iterdir fails
        try:
            _ls = list(listdir(INPUT_DIR))
        except Exception:
            _ls = None
        # build fallback list
        files = [
            Path(join(INPUT_DIR, name))
            for name in (_ls or [])
            if isfile(join(INPUT_DIR, name)) and not name.startswith('.')
        ]
        # debug logging to help trace environment file visibility
        log(f"[debug] pathlib_iterdir_empty -> os.listdir returned: {_ls}")
        log(f"[debug] fallback files resolved: {[p.name for p in files]}")

    if len(files) != 2:
        raise ValueError(
            f"Esperado exatamente 2 arquivos em 'input/', encontrado {len(files)}. "
            f"Coloque somente os dois arquivos (MAC e CON) que serão comparados."
        )

    log("📂 Arquivos de entrada detectados:")
    for f in files:
        log(f"   - {f.name}")

    return files


# ==============================
# EXTRAÇÃO DE DETALHES (LINHA 200)
# ==============================

def extract_detail_key(line: str) -> Tuple[str, str]:
    """
    Extrai a chave de comparação a partir de uma linha tipo 200.

    IMPORTANTE:
    Ajuste AQUI as posições de acordo com o layout real do seu arquivo.
    Exemplo abaixo:
      - nu_nb: posições 3 a 18
      - valor: posições 92 a 107 (apenas exemplo!)
    """

    # Garante que a linha tenha pelo menos 240 chars (ou preenche)
    if len(line) < 240:
        line = line.rstrip("\n")
        line = line.ljust(240)

    nu_nb = line[3:18].strip()     # ajuste conforme layout oficial
    valor = line[92:107].strip()   # ajuste conforme layout oficial

    return nu_nb, valor


def collect_details(file_path: Path) -> Dict[Tuple[str, str], str]:
    """
    Lê um arquivo e retorna um dict:
      chave: (nu_nb, valor)
      valor: linha original (200...) normalizada com 240 bytes

    Somente linhas tipo '200' são consideradas.
    """
    details = {}
    with file_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("200"):
                if len(line) < 240:
                    line = line.ljust(240)
                key = extract_detail_key(line)
                details[key] = line[:240]
    return details


# ==============================
# BUILDER FHMLRET11
# ==============================

def pad_240(s: str) -> str:
    """
    Garante exatamente 240 bytes (caracteres) na linha.
    """
    s = s[:240]
    return s.ljust(240)


def generate_fhmlret11(stem: str, consistent_details: List[Tuple[str, str]], timestamp: str) -> Path:
    """
    Gera o arquivo FHMLRET11 completo com:
      - Header 100
      - Detalhes 200 para cada registro consistente
      - Trailer 900 com totalizadores
    Todos com 240 bytes.
    """

    output_path = READY_DIR / f"{stem}.{timestamp}.FHMLRET11_final.d"
    log(f"🧱 Gerando arquivo final FHMLRET11: {output_path.name}")

    lines = []

    # ---------- HEADER (100) ----------
    # Ajuste conforme doc FHMLRET11 se necessário.
    data_geracao = datetime.now().strftime("%Y%m%d")
    hora_geracao = datetime.now().strftime("%H%M%S")

    header = (
        "100"                       # Tipo de registro
        + "FHMLRET11"               # Identificação do layout / produto (exemplo)
        + data_geracao              # Data geração
        + hora_geracao              # Hora geração
        + stem.ljust(30)            # Identificação do arquivo / remetente
        + " " * 240                 # Padding
    )
    lines.append(pad_240(header))

    # ---------- DETALHES (200) ----------
    total_registros = 0
    soma_valores = 0

    for nu_nb, valor in consistent_details:
        # valor aqui vem como string; ajuste conforme doc (ex: centavos sem ponto)
        # Tenta normalizar para inteiro
        try:
            v_int = int("".join(filter(str.isdigit, valor))) if valor else 0
        except ValueError:
            v_int = 0

        soma_valores += v_int
        total_registros += 1

        # Montagem da linha 200 - AJUSTE conforme doc FHMLRET11
        detalhe = (
            "200"                           # Tipo de registro
            + nu_nb.ljust(20)               # Número NB / identificador
            + str(v_int).rjust(15, "0")     # Valor em centavos (exemplo)
            + " " * 240                     # Padding restante
        )
        lines.append(pad_240(detalhe))

    # ---------- TRAILER (900) ----------
    trailer = (
        "900"                                   # Tipo de registro
        + str(total_registros).rjust(9, "0")    # Quantidade de registros
        + str(soma_valores).rjust(18, "0")      # Soma dos valores (exemplo)
        + " " * 240                             # Padding
    )
    lines.append(pad_240(trailer))

    # ---------- GRAVAÇÃO ----------
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line + "\n")

    log(f"✅ FHMLRET11 completo gerado com {total_registros} registros consistentes.")
    log(f"   Soma dos valores: {soma_valores}")
    return output_path


# ==============================
# PIPELINE PRINCIPAL
# ==============================

def main():
    log("\n🚀 Iniciando pipeline FHMLRET11 (versão limpa, menos é mais)...")

    # 1. Limpa ambiente antigo (sem mexer em input)
    clean_environment()

    # 2. Localiza arquivos de entrada
    files = find_input_files()
    file_a, file_b = files[0], files[1]

    # 3. Coleta detalhes dos dois arquivos
    log("\n🔍 Coletando detalhes (linhas 200) dos arquivos...")
    details_a = collect_details(file_a)
    details_b = collect_details(file_b)

    # 4. Calcula interseção (apenas registros consistentes nos dois arquivos)
    log("🔄 Calculando registros consistentes entre os dois arquivos...")
    keys_consistentes = sorted(set(details_a.keys()) & set(details_b.keys()))

    if not keys_consistentes:
        raise RuntimeError("Nenhum registro consistente encontrado entre os dois arquivos (linhas 200).")

    consistent_details = list(keys_consistentes)
    log(f"✅ Registros consistentes encontrados: {len(consistent_details)}")

    # 5. Gera FHMLRET11 final único na pasta ready
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_path = generate_fhmlret11(STEM, consistent_details, timestamp)

    log("\n🏁 Pipeline concluído com sucesso.")
    log(f"📂 Arquivo pronto para envio ao Connect: {output_path}\n")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Finalize pipeline (renamed from fix_pipeline_final.py).

Removes inconsistent lines, recalculates trailer totals, produces a FINAL RET and
places final artifacts in `input/arquivo_pronto_para_envio_connect`.
"""
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime
import shutil

# FHMLRET11 builder (generates final .d ready for Connect)
from fhml_ret11_builder import generate_fhmlret11


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def finalize_and_revalidate(json_path):
    data = load_json(json_path)
    base = Path(json_path).parent.parent
    corrigido_dir = base / "corrigido"

    # Localiza arquivo corrigido .d correspondente
    candidates = []
    if corrigido_dir.exists():
        candidates = (
            list(corrigido_dir.glob("*_fixed_*.d"))
            + list(corrigido_dir.glob("*_fixed.d"))
            + list(corrigido_dir.glob("*_fix*.d"))
        )
        # sort by modification time so the latest appears last
        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime)

    # If no candidates in corrigido, try archive (previously moved versions)
    if not candidates:
        archive_dir = base / "archive"
        if archive_dir.exists():
            archive_candidates = (
                list(archive_dir.glob("*_fixed_*.d"))
                + list(archive_dir.glob("*_fixed.d"))
                + list(archive_dir.glob("*_fix*.d"))
            )
            archive_candidates = sorted(archive_candidates, key=lambda p: p.stat().st_mtime)
            if archive_candidates:
                # copy latest archived candidate back to corrigido for processing
                latest = archive_candidates[-1]
                corrigido_dir.mkdir(parents=True, exist_ok=True)
                restored = corrigido_dir / latest.name
                try:
                    shutil.copy2(latest, restored)
                    input_file = restored
                    print(f"♻️ Restaurado arquivo de archive para {restored}")
                except Exception as exc:
                    print(f"Falha ao restaurar {latest} de archive: {exc}")
                    input_file = None
            else:
                input_file = None
        else:
            input_file = None

    if not candidates and not (input_file):
        origem = data.get("origem") or (data.get("validacao", {}) and data.get("origem"))
        if origem:
            p = Path(origem)
            if p.exists():
                input_file = p
                corrigido_dir = p.parent
            else:
                pr = Path(origem).resolve()
                if pr.exists():
                    input_file = pr
                    corrigido_dir = pr.parent
                else:
                    print("❌ Nenhum arquivo corrigido encontrado (origem informado mas arquivo não existe):", origem)
                    return
        else:
            print("❌ Nenhum arquivo corrigido encontrado.")
            return
    elif candidates:
        input_file = candidates[-1]

    # Canonicalizar stem para evitar repetições como _final_final ou _fix_final
    # remove trailing _final ou _fix[_NNN] patterns iterativamente
    s = input_file.stem
    while True:
        new = re.sub(r"(_final|_fix(_\d+)?)$", "", s)
        if new == s:
            break
        s = new
    canonical_stem = s
    output_file = corrigido_dir / (canonical_stem + "_final.d")

    # Arquivo de archive dentro de reports/<stem>/archive/
    archive_dir = base / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Mover versões antigas (_final* e _fix*) para archive, exceto se for o futuro output
    for p in list(corrigido_dir.glob("*_final*.d")) + list(corrigido_dir.glob("*_fix*.d")):
        try:
            # don't archive the input_file we're about to read or the final output we'll write
            if p.resolve() in (output_file.resolve(), input_file.resolve()):
                continue
        except Exception:
            pass
        try:
            if not p.exists():
                # already moved or missing, skip silently
                continue
            target = archive_dir / p.name
            # avoid overwriting an existing archive entry: if exists, add timestamp
            if target.exists():
                ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                target = archive_dir / f"{p.stem}_{ts}{p.suffix}"
            print(f"📦 Arquivo antigo detectado e movendo para archive: {p.name} -> {target}")
            shutil.move(str(p), str(target))
        except Exception as exc:
            print(f"Falha ao mover {p} para archive: {exc}")

    # Identifica linhas inconsistentes a remover
    inconsistent_lines = []
    valid = data.get("validacao") or data
    warnings = valid.get("avisos") or valid.get("warnings") or []
    for w in warnings:
        if isinstance(w, str) and "Linha" in w and "inconsistente" in w:
            try:
                num = int(w.split("Linha")[1].split(":")[0].strip().split("/")[0])
                inconsistent_lines.append(num)
            except Exception:
                continue

    print(f"🔎 Linhas inconsistentes detectadas: {inconsistent_lines}")

    # Leitura e filtragem
    lines = [l.rstrip("\n") for l in open(input_file, "r", encoding="utf-8")]
    new_lines = []
    for idx, line in enumerate(lines, start=1):
        if idx in inconsistent_lines:
            print(f"🗑️ Removendo linha {idx}: {line[:20]}...")
            continue
        new_lines.append(line[:240].ljust(240))

    # Recalcular trailer usando slice 17:32
    header = new_lines[0]
    details = [l for l in new_lines if l.startswith("200")]
    trailer = [l for l in new_lines if l.startswith("300")][-1]

    total_registros = str(len(details)).rjust(8, "0")
    total_val = 0
    for l in details:
        slice_val = l[17:32].strip()
        slice_val = ''.join(ch for ch in slice_val if ch.isdigit())
        if not slice_val:
            continue
        try:
            total_val += int(slice_val)
        except Exception:
            continue
    total_val = str(total_val).rjust(15, "0")

    trailer_list = list(trailer)
    trailer_list[9:17] = list(total_registros)
    trailer_list[17:32] = list(total_val)
    trailer = "".join(trailer_list)[:240].ljust(240)

    # Substitui trailer final
    for i, l in enumerate(new_lines):
        if l.startswith("300"):
            new_lines[i] = trailer

    # Gravar arquivo final
    with open(output_file, "w", encoding="utf-8") as f:
        for l in new_lines:
            f.write(l + "\n")

    print(f"✅ Arquivo final salvo em {output_file}")

    # === Generate FHMLRET11 using builder from the cleaned final lines ===
    fhml_path = None
    try:
        detalhes = [l for l in new_lines if l.startswith("200")]
        registros = []
        for d in detalhes:
            # NU-NB positions 11-20 -> slice 10:20
            nu_nb = d[10:20].strip()
            # value cents at positions 18-32 -> slice 17:32
            raw = d[17:32].strip()
            val = 0.0
            if raw.isdigit():
                # treat as cents -> convert to reais
                val = int(raw) / 100.0
            registros.append({"nu_nb": nu_nb or None, "valor": val})

        # choose output path under reports/<stem>/ret/
        date_s = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        ret_dir = base / "ret"
        ret_dir.mkdir(parents=True, exist_ok=True)
        fhml_name = f"{canonical_stem}.{date_s}.FHMLRET11_final.d"
        fhml_path = ret_dir / fhml_name
        generate_fhmlret11(fhml_path, registros)
    except Exception as exc:
        print(f"Falha ao gerar FHMLRET11 via builder: {exc}")

    # After writing canonical final, ensure there are no other *_final*.d in corrigido
    for p in corrigido_dir.glob("*_final*.d"):
        try:
            if p.resolve() == output_file.resolve():
                continue
        except Exception:
            pass
        try:
            if not p.exists():
                continue
            target = archive_dir / p.name
            if target.exists():
                ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                target = archive_dir / f"{p.stem}_{ts}{p.suffix}"
            print(f"📦 Movendo final redundante para archive: {p.name} -> {target}")
            shutil.move(str(p), str(target))
        except Exception as exc:
            print(f"Falha ao mover {p} para archive: {exc}")

    # Revalidar automaticamente
    subprocess.run(["python3", "main.py", str(output_file)], check=False)

    # tentar localizar o JSON gerado que referencia este arquivo como 'origem'
    found_json = None
    for jf in Path("reports").rglob("*.json"):
        try:
            with jf.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            origem_val = payload.get("origem")
            if origem_val == str(output_file) or origem_val == str(Path(output_file).resolve()):
                found_json = jf
                break
        except Exception:
            continue

    # construir summary_final.json no diretório corrigido
    summary_payload = {
        "arquivo": base.name,
        "final_file": str(output_file),
        "status": None,
        "report_json": None,
    }
    # if the FHMLRET11 was created, include its path in the summary
    if fhml_path is not None:
        summary_payload["fhmlret11"] = str(fhml_path)
    if found_json:
        try:
            with found_json.open("r", encoding="utf-8") as fh:
                pj = json.load(fh)
            # Determine status intelligently from validation errors/warnings lists
            valid = pj.get("validacao", {})
            errs = valid.get("erros") or []
            avisos = valid.get("avisos") or []
            try:
                errs_len = len(errs)
            except Exception:
                errs_len = 0
            try:
                avisos_len = len(avisos)
            except Exception:
                avisos_len = 0

            if errs_len > 0:
                summary_payload["status"] = "ERROR"
            elif avisos_len > 0:
                summary_payload["status"] = "WARN"
            else:
                summary_payload["status"] = "OK"

            summary_payload["report_json"] = str(found_json)
        except Exception:
            # fallback: preserve previous behavior if JSON is malformed
            try:
                raw = pj.get("validacao", {}).get("conteudo")
                if raw and "OK" in str(raw).upper():
                    summary_payload["status"] = "OK"
                elif raw and ("WARN" in str(raw).upper() or "AVISO" in str(raw).upper()):
                    summary_payload["status"] = "WARN"
                else:
                    summary_payload["status"] = "ERROR"
            except Exception:
                summary_payload["status"] = "ERROR"

    summary_path = corrigido_dir / "summary_final.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary_payload, fh, indent=2, ensure_ascii=False)

    # Atualizar resumo leigo
    resumo = Path("resumo_leigo.txt")
    resumo.write_text(
        "🟢 Revalidação final executada com sucesso.\n"
        f"Linhas removidas: {inconsistent_lines}\n"
        f"Arquivo final: {output_file.name}\n"
        "Verifique summary_final.json na pasta correspondente para status final.",
        encoding="utf-8"
    )

    # Mover artefatos finais para input/arquivo_pronto_para_envio_connect/
    target = Path.cwd() / "input" / "arquivo_pronto_para_envio_connect"
    target.mkdir(parents=True, exist_ok=True)
    try:
        # copy final file
        shutil.copy2(output_file, target / output_file.name)
        # copy summary_final.json
        shutil.copy2(summary_path, target / summary_path.name)
        # copy resumo_leigo.txt
        if resumo.exists():
            shutil.copy2(resumo, target / resumo.name)
        print(f"📁 Arquivos finais copiados para {target}")
        # Deduplicate in target: keep canonical _final.d (not _final_final) or newest
        try:
            candidates = list(target.glob(f"{canonical_stem}*.d"))
            # prefer one that ends with exactly '_final.d' and not '_final_final'
            canon = None
            for c in candidates:
                if c.name.endswith("_final.d") and "_final_final" not in c.name:
                    canon = c
                    break
            if not canon and candidates:
                # fallback: choose newest by mtime
                canon = max(candidates, key=lambda p: p.stat().st_mtime)

            for c in candidates:
                try:
                    if canon and c.resolve() == canon.resolve():
                        continue
                except Exception:
                    pass
                # move non-canonical to reports archive to avoid cluttering send folder
                quarant_dir = archive_dir / "from_ready"
                quarant_dir.mkdir(parents=True, exist_ok=True)
                dest = quarant_dir / c.name
                if dest.exists():
                    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                    dest = quarant_dir / f"{c.stem}_{ts}{c.suffix}"
                print(f"🗄️ Movendo variante não-canonical do ready para archive: {c.name} -> {dest}")
                shutil.move(str(c), str(dest))
        except Exception as exc:
            print(f"Falha ao deduplicar em {target}: {exc}")
    except Exception as exc:
        print(f"Falha ao mover arquivos finais para {target}: {exc}")

    print("📄 resumo_leigo.txt atualizado com resultados.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 1 and len(sys.argv) != 2:
        print("Uso: python3 finalize_pipeline.py <optional_path_para_json>")
        sys.exit(1)
    if len(sys.argv) == 2:
        finalize_and_revalidate(sys.argv[1])
    else:
        print("Passe o caminho do JSON de revalidação do sub-lote para finalizar.")
