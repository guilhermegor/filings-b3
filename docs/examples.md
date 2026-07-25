# **Examples**

Task-oriented, self-contained snippets. Each recipe stands alone — copy it and adjust the
session date.

> **See also:** [Usage](usage.md) for the basics · [API Reference](api/index.md) for every public
> symbol.

---

## Recipe: read a session's securities-lending open positions

Pull the end-of-session BTB open-position snapshot for one trading day and inspect the largest
positions by financial balance.

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()

# BALANCE is an exact Decimal (BRL) — safe to sort and sum without float drift.
top = df.sort_values("BALANCE", ascending=False).head(10)
print(top[["TCKR_SYMB", "ISIN", "STOCK_BALANCE", "BALANCE"]])
```

## Recipe: read the daily cash-equities summary

```python
from datetime import date
from filings_b3 import BdiStocksSummaryReader

df = BdiStocksSummaryReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "NMBR_TRADES_DAY", "VLM_TRADED_DAY"]].head())
```

## Recipe: keep the raw source for a datalake's bronze layer

Pass `path_raw` to retain each untouched JSON page. Combined with the provenance columns on every
frame (`content_hash`, `url`, `updated_at`), a stored row stays fully attributable and a contract
break is replayable against the exact bytes that caused it.

```python
from datetime import date
from pathlib import Path
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()

# Provenance travels with the data — no separate metadata store needed.
print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

## Recipe: compute money totals without float drift

Every monetary column is a `decimal.Decimal`, so aggregations reconcile against B3's own
published totals exactly.

```python
from datetime import date
from decimal import Decimal
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()

total = sum(df["BALANCE"])
assert isinstance(total, Decimal)  # never a lossy float64
print(f"Total open-position balance: R$ {total}")
```
