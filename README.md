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
