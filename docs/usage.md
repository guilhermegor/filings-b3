# **Uso**

Instalando e usando o `filings-b3` — acesso tipado aos conjuntos de dados públicos da B3 (a bolsa
brasileira).

> **Veja também:** [Referência da API](api/index.md) · [Exemplos](examples.md)

---

## Instalação

```bash
pip install filings-b3
```

Ou com Poetry:

```bash
poetry add filings-b3
```

---

## Uso básico

Cada _reader_ recebe o pregão a ser lido e retorna um `pandas.DataFrame` tipado, com colunas de
proveniência:

```python
from datetime import date
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "STOCK_BALANCE", "BALANCE"]].head())
```

Cada _reader_ vive numa **macro-seção** (`daily_bulletin`, `search_trading_session`, …) e é
importado **de lá, e só de lá**. A raiz do pacote não exporta _readers_.

!!! warning "Mudança na 0.2.0"
    Até a 0.1.x cada _reader_ também era reexportado de forma plana na raiz
    (`from filings_b3 import BdiBtbLendingOpenPositionsReader`). Isso **foi removido**: com seis
    macro-seções e ~105 datasets previstos, a raiz viraria uma lista de mais de cem nomes — o
    oposto do que a organização por seção existe para resolver. Troque o _import_ pela seção
    correspondente.

`date_ref` é **obrigatório** — o endpoint do BDI é endereçado por data, então não existe um padrão
"mais recente". Precisa do dia útil anterior? Calcule-o e passe explicitamente.

## Mantendo o artefato bruto (camada bronze)

Passe `path_raw` para reter cada página bruta da fonte para a camada bronze de um _datalake_ — uma
quebra de contrato fica, assim, reproduzível contra os bytes exatos:

```python
from pathlib import Path

df = BdiBtbLendingOpenPositionsReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()
```

## O que todo _reader_ garante

- As colunas são as da própria fonte, em _UPPER_SNAKE_CASE_ e **tipadas explicitamente** — nunca a
  inferência do pandas.
- Colunas monetárias (`BALANCE`, `AVG_PRIC`, `VLM_TRADED_DAY`, …) são `decimal.Decimal` exato,
  nunca `float` binário.
- Seis colunas de proveniência em todo _frame_: `url`, `updated_at`, `source_key`,
  `package_version`, `ingestion_run_id`, `content_hash`.
- Uma fonte que viola o contrato declarado levanta `ContractError` — uma coluna obrigatória
  ausente falha de forma barulhenta, em vez de silenciosa.

Veja a [Referência da API](api/index.md) para a lista completa de _readers_, organizada por seção.

---

## Executando os testes

```bash
make unit_tests         # apenas testes unitários
make integration_tests  # apenas testes de integração
make test_cov           # testes unitários + relatório de cobertura + badge
```

---

## Lint e formatação

```bash
make lint          # ruff check + ruff format + codespell + pydocstyle
```

---

## Publicando no PyPI

Dois workflows do GitHub Actions cuidam dos releases:

- **`release-test-pypi.yaml`** — publica primeiro no [Test PyPI](https://test.pypi.org).
- **`release-pypi.yaml`** — publica no [PyPI](https://pypi.org) e cria um release no GitHub.

Dispare qualquer um pela aba **Actions** (`workflow_dispatch`) com a versão a publicar. Ambos
exigem que a nova versão seja maior que a última já publicada, constroem com o Poetry e recorrem ao
`twine` caso o `poetry publish` não esteja disponível.
