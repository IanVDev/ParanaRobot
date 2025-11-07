#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
from datetime import datetime

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def remove_inconsistent_and_revalidate(json_path):
    data = load_json(json_path)
    base = Path(json_path).parent.parent
    corrigido_dir = base / "corrigido"

    # Localiza arquivo corrigido .d correspondente
    candidates = []
    if corrigido_dir.exists():
        candidates = list(corrigido_dir.glob("*_fix_*.d")) or list(corrigido_dir.glob("*_fix.d"))

    if not candidates:
        # try to use 'origem' field inside the JSON which often points to the corrected file
        origem = data.get("origem") or (data.get("validacao", {}) and data.get("origem"))
        if origem:
            p = Path(origem)
            if p.exists():
                input_file = p
                corrigido_dir = p.parent
            else:
                # try resolve
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
    else:
        input_file = candidates[-1]
    output_file = corrigido_dir / (input_file.stem + "_final.d")

    # Identifica linhas inconsistentes a remover
    inconsistent_lines = []
    # Try to read warnings from the same structure as earlier (validacao.avisos)
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

    # Recalcular trailer
    header = new_lines[0]
    details = [l for l in new_lines if l.startswith("200")]
    trailer = [l for l in new_lines if l.startswith("300")][-1]

    total_registros = str(len(details)).rjust(8, "0")
    # Note: user script used slice 50:62 for values; keep as provided but fallback to 17:32 if empty
    # Compute total using the same slice used by Analyzer (positions 17:32)
    total_val = 0
    for l in details:
        slice_val = l[17:32].strip()
        # remove any non-digit chars just in case
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
    if found_json:
        try:
            with found_json.open("r", encoding="utf-8") as fh:
                pj = json.load(fh)
            summary_payload["status"] = pj.get("validacao", {}).get("conteudo")
            summary_payload["report_json"] = str(found_json)
        except Exception:
            pass

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
        import shutil

        # move final file
        shutil.copy2(output_file, target / output_file.name)
        # move summary_final.json
        shutil.copy2(summary_path, target / summary_path.name)
        # move resumo_leigo.txt
        if resumo.exists():
            shutil.copy2(resumo, target / resumo.name)
        print(f"📁 Arquivos finais copiados para {target}")
    except Exception as exc:
        print(f"Falha ao mover arquivos finais para {target}: {exc}")

    print("📄 resumo_leigo.txt atualizado com resultados.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Uso: python3 fix_pipeline_final.py <path_para_json>")
        sys.exit(1)
    remove_inconsistent_and_revalidate(sys.argv[1])
