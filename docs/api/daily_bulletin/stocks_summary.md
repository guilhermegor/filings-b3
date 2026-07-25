# **Resumo diário do mercado à vista de ações — BDI**

Leitura do resumo por pregão do **mercado à vista de ações** (tabela `DailyAverageStocks` da B3),
publicado no Boletim Diário do Pregão.

> **Veja também:** [Visão geral da seção BDI](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Uso](../../usage.md) para instalação e o conceito geral.

---

## Descrição

`BdiStocksSummaryReader` baixa a tabela paginada do pregão, valida o **contrato** de colunas, aplica
os **tipos declarados** — nunca a inferência do pandas — e devolve um `DataFrame` com uma linha por
instrumento, carregando a quantidade de negócios e o volume financeiro negociado do dia.

O contrato lista deliberadamente **apenas as três colunas** de que um consumidor depende, então a B3
acrescentar uma coluna **não** é uma quebra — enquanto uma coluna obrigatória **removida** ainda
falha de forma barulhenta (`ContractError`). Colunas extras da fonte (como `COL_ORDER`, o campo de
ordenação de exibição) continuam fluindo para o _frame_, tipadas pelo _reader_.

| Coluna | Tipo | Observação |
|--------|------|-----------|
| `TCKR_SYMB` | `str` | _Ticker_ do instrumento. |
| `NMBR_TRADES_DAY` | `Int64` | Quantidade de negócios do dia. |
| `VLM_TRADED_DAY` | `Decimal` | Volume financeiro negociado no dia, exato (BRL). |

---

## Exemplos

### Ler um pregão

```python
from datetime import date
from filings_b3.daily_bulletin import BdiStocksSummaryReader

df = BdiStocksSummaryReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "NMBR_TRADES_DAY", "VLM_TRADED_DAY"]].head())
```

`date_ref` é **obrigatório** — o endpoint do BDI é endereçado por data, então não existe um padrão
"mais recente". Precisa do dia útil anterior? Calcule-o e passe explicitamente.

### Volume total negociado sem perda de _float_

`VLM_TRADED_DAY` é um `Decimal` exato (em BRL), então a agregação reconcilia exatamente:

```python
from decimal import Decimal

total = sum(df["VLM_TRADED_DAY"])
assert isinstance(total, Decimal)  # nunca um float64 com perda
print(f"Volume total do pregão: R$ {total}")
```

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = BdiStocksSummaryReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```
