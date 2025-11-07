# ParanaRobot — Guia Operacional

Este README descreve o fluxo operacional mínimo para validar, diagnosticar e finalizar arquivos FHML (MAC/CON) antes do envio ao Connect.

## Estrutura principal de pastas

- `input/arquivos_para_comparacao/` — pasta observada pelo `upload_manager.py` (entrada para processamento).
- `input/arquivo_pronto_para_envio_connect/` — pasta de saída com arquivos finais prontos para envio ao Connect.
- `reports/<stem>/json/` — relatórios JSON gerados pelo validador para cada arquivo.
- `reports/<stem>/txt/` — relatórios humanos em TXT.
- `reports/<stem>/ret/` — RETs gerados por comparadores (quando aplicável).
- `reports/<stem>/corrigido/` — arquivos corrigidos gerados pelo pipeline de diagnóstico/finalização.
- `reports/<stem>/archive/` — histórico/arquivamento automático de versões antigas (criadas pela finalização).

## Scripts principais

- `main.py <arquivo>` — executa o pipeline de validação principal sobre um arquivo MAC/CON.
- `upload_manager.py` — observa `input/arquivos_para_comparacao/` e dispara o pipeline automaticamente (útil em produção).
- `diagnose_pipeline.py <report.json>` — gera versões corrigidas por sub-lote (`*_fixed_XXX.d`) a partir do JSON de diagnóstico.
- `finalize_pipeline.py <report_final.json>` — gera o arquivo final canônico `<stem>_final.d`, arquiva versões antigas em `reports/<stem>/archive/` e copia os artefatos finais para `input/arquivo_pronto_para_envio_connect/`.

## Como executar (exemplos)

1. Validar um arquivo manualmente:

```bash
python3 main.py input/lote_teste_funcional/HMLMAC12.B254.D0000001.txt
```

2. Rodar diagnóstico (gera `_fixed_XXX.d` por sub-lote):

```bash
python3 diagnose_pipeline.py reports/HMLMAC12.B254.D0000001/json/summary.json
```

3. Finalizar (gera `<stem>_final.d`, arquiva antigas, copia arquivos prontos):

```bash
python3 finalize_pipeline.py reports/HMLMAC12.B254.D0000001/corrigido/summary_final.json
```

## Interpretação de status

- `OK` — sem erros; pronto para envio.
- `WARN` — contém avisos; revisar `resumo_leigo.txt` e o JSON antes de enviar.
- `ERROR` — contém erros bloqueantes; não enviar. Investigar via JSON/TXT e executar `diagnose_pipeline.py`.

## Boas práticas

- Nunca envie arquivos intermediários (`*_fixed_*.d`). Sempre envie o arquivo final `<stem>_final.d` encontrado em `input/arquivo_pronto_para_envio_connect/`.
- Mantenha o repositório limpo: o pipeline arquiva versões antigas automaticamente em `reports/<stem>/archive/`.
- Revise `summary_final.json` e `resumo_leigo.txt` antes do envio para QA.

## Checklist rápido antes do envio

1. Verificar que `input/arquivo_pronto_para_envio_connect/` contém apenas `<stem>_final.d` desejados.
2. Abrir `reports/<stem>/corrigido/summary_final.json` e confirmar `status` é `OK` ou `WARN` (se WARN, revisar avisos).
3. Conferir `resumo_leigo.txt` para orientações rápidas sobre o que foi removido/ajustado.

---
Se precisar, posso incluir um exemplo de workflow automatizado ou adicionar instruções para implantação/serviço systemd/launchd.
# ParanaRobot

ParanaRobot é um robô de validação automática para arquivos de integração FHML utilizados pela Dataprev. Ele automatiza a inspeção de arquivos `.d` de 240 bytes por registro, tratando tanto arquivos compactados (`.zip`) quanto arquivos planos.

## Objetivos

- Validar a estrutura FHML (header 100, detalhes 200, trailer 300).
- Garantir que cada registro tenha exatamente 240 bytes.
- Detectar problemas de codificação, como presença de BOM, bytes nulos e caracteres fora da faixa ASCII.
- Interpretar campos-chave dos arquivos FHML (header, detalhes e trailer) para validar datas, códigos e totais.
- Gerar relatórios em JSON e texto com os problemas encontrados.

## Estrutura do Projeto

```
paranarobot/
│
├── main.py
├── modules/
│   ├── __init__.py
│   ├── analyzer.py
│   ├── reporter.py
│   ├── sanitizer.py
│   ├── unzipper.py
│   ├── utils.py
│   └── validator.py
├── reports/
├── tests/
│   ├── __init__.py
│   ├── test_analyzer.py
│   ├── test_sanitizer.py
│   └── test_validator.py
└── README.md
```

## Execução

```
python3 main.py caminho/para/FHMLRET11.20251029141050.zip
```

Um relatório JSON e outro texto serão salvos em `reports/` após a execução.

## Desenvolvimento

- Python 3.11+
- Pytest para testes unitários (`pip install -r requirements.txt`)
- Organização modular para facilitar extensão futura (por exemplo, suporte a novos layouts FHML).

## Próximos Passos

- Cobertura de todos os layouts FHML conhecidos.
- Integração com pipelines CI/CD.
- Interface web simples para execução via navegador.
