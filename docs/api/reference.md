# **Referência da API**

Interface pública do `filings-b3`. Tudo abaixo é reexportado a partir da raiz do pacote, então o
consumidor importa direto de `filings_b3` — nunca de um caminho de módulo de seção, e nunca do
subpacote privado `_internal` do pacote (ele vai no _wheel_, mas não é API).

> **Veja também:** [Uso](../usage.md) · [Exemplos](../examples.md)

---

## Módulo: `daily_bulletin` — Boletim Diário do Pregão (BDI)

O boletim diário de negociação da B3, servido a partir de `arquivos.b3.com.br/bdi`. Cada conjunto
de dados é uma tabela JSON paginada; um _reader_ transforma um pregão em um `pandas.DataFrame`
tipado, validado por contrato e com proveniência.

Todo _reader_ tem a mesma forma:

```python
Reader(date_ref: datetime.date, path_raw: pathlib.Path | None = None) -> Reader
Reader.read() -> pandas.DataFrame
```

| Parâmetro | Tipo | Significado |
|-----------|------|-------------|
| `date_ref` | `datetime.date` | Pregão a ler. **Obrigatório, sem padrão** — o endpoint é endereçado por data, então um palpite de pregão errado é pior que um `TypeError`. |
| `path_raw` | `pathlib.Path`, opcional | Diretório onde **manter** cada página JSON bruta baixada (a camada bronze de um _datalake_). `None` (padrão) usa um diretório temporário removido ao final. |

`read()` retorna um DataFrame cujas colunas são as da própria fonte, em _UPPER_SNAKE_CASE_
(`TckrSymb` → `TCKR_SYMB`), tipadas explicitamente (nunca a inferência do pandas). Colunas
monetárias são `decimal.Decimal` exato, nunca `float` binário. Seis colunas de proveniência são
anexadas a todo _frame_: `url`, `updated_at`, `source_key`, `package_version`, `ingestion_run_id`,
`content_hash`. Uma fonte que viola o contrato declarado levanta `ContractError`.

### `BdiStocksSummaryReader`

O resumo por pregão do mercado à vista de ações (tabela `DailyAverageStocks` da B3): uma linha por
instrumento com a quantidade de negócios e o volume financeiro negociado do dia.

```python
from datetime import date
from filings_b3 import BdiStocksSummaryReader

df = BdiStocksSummaryReader(date(2025, 1, 2)).read()
```

Colunas principais: `TCKR_SYMB` (ticker), `NMBR_TRADES_DAY` (`Int64`), `VLM_TRADED_DAY`
(`Decimal`, BRL).

### `BdiBtbLendingOpenPositionsReader`

O retrato de fim de pregão do empréstimo de ativos (banco de títulos, "BTB"; tabela
`BTBLendingOpenPosition` da B3): uma linha por instrumento ainda em aberto, com a quantidade
emprestada, o preço médio de empréstimo e o saldo financeiro da posição.

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
```

Colunas principais: `DT_REF` (data do pregão), `TCKR_SYMB`, `ISIN`, `STOCK_BALANCE` (`Int64`, qtd.
emprestada), `AVG_PRIC` (`Decimal`), `BALANCE` (`Decimal`, BRL).

---

## `__version__`

```python
import filings_b3

filings_b3.__version__  # a versão da distribuição instalada
```

---

## Convenções

| Convenção | Regra |
|-----------|-------|
| Caminho de import | Somente a partir de `filings_b3`; o subpacote `_internal` é privado |
| Tipo de retorno | Todo _reader_ retorna um `pandas.DataFrame` tipado, validado por contrato e com proveniência |
| Números | Dinheiro e qualquer valor cuja parte fracionária importa são `Decimal` exato, nunca `float` |
| Type hints | Obrigatórios em todas as funções públicas, incluindo `-> None` |
| Docstrings | Estilo NumPy; explicam o *porquê*, não o *o quê* |
