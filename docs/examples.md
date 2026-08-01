# **Exemplos**

Trechos autossuficientes, orientados a tarefas. Cada receita é independente — copie e ajuste a data
do pregão.

> **Veja também:** [Uso](usage.md) para o básico · [Referência da API](api/index.md) para cada
> símbolo público.

Os _readers_ são importados pela sua **macro-seção** (`from filings_b3.daily_bulletin import …`) —
a única forma pública. A raiz do pacote não exporta _readers_ desde a **0.2.0**.

---

## Receita: ler as posições em aberto de empréstimo de ativos de um pregão

Obtenha o retrato de fim de pregão das posições em aberto de BTB para um dia e inspecione as
maiores posições por saldo financeiro.

```python
from datetime import date
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()

# BALANCE é um Decimal exato (em BRL) — seguro para ordenar e somar sem perda de float.
top = df.sort_values("BALANCE", ascending=False).head(10)
print(top[["TCKR_SYMB", "ISIN", "STOCK_BALANCE", "BALANCE"]])
```

## Receita: ler o resumo diário do mercado à vista de ações

```python
from datetime import date
from filings_b3.daily_bulletin import BdiStocksSummaryReader

df = BdiStocksSummaryReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "NMBR_TRADES_DAY", "VLM_TRADED_DAY"]].head())
```

## Receita: manter a fonte bruta para a camada bronze de um _datalake_

Passe `path_raw` para reter cada página JSON intocada. Combinado com as colunas de proveniência de
todo _frame_ (`content_hash`, `url`, `updated_at`), uma linha armazenada permanece totalmente
rastreável e uma quebra de contrato fica reproduzível contra os bytes exatos que a causaram.

```python
from datetime import date
from pathlib import Path
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()

# A proveniência viaja junto com os dados — nenhum repositório de metadados separado é necessário.
print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

## Receita: calcular totais monetários sem perda de float

Toda coluna monetária é um `decimal.Decimal`, então as agregações reconciliam exatamente com os
totais publicados pela própria B3.

```python
from datetime import date
from decimal import Decimal
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()

total = sum(df["BALANCE"])
assert isinstance(total, Decimal)  # nunca um float64 com perda
print(f"Saldo total das posições em aberto: R$ {total}")
```
