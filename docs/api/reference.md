# **API Reference**

Public interface for `filings-b3`. Everything below is re-exported from the package root, so a
consumer imports from `filings_b3` directly — never from a section module path, and never from
the package's private `_internal` subpackage (it ships in the wheel but is not API).

> **See also:** [Usage](../usage.md) · [Examples](../examples.md)

---

## Module: `daily_bulletin` — Boletim Diário do Pregão (BDI)

B3's daily trading bulletin, served from `arquivos.b3.com.br/bdi`. Each dataset is a paginated
JSON table; a reader turns one trading session into a typed, contract-validated
`pandas.DataFrame` carrying provenance.

Every reader shares the same shape:

```python
Reader(date_ref: datetime.date, path_raw: pathlib.Path | None = None) -> Reader
Reader.read() -> pandas.DataFrame
```

| Parameter | Type | Meaning |
|-----------|------|---------|
| `date_ref` | `datetime.date` | Trading session to read. **Required, no default** — the endpoint is date-addressed, so a wrong-session guess is worse than a `TypeError`. |
| `path_raw` | `pathlib.Path`, optional | Directory in which to **keep** each downloaded raw JSON page (a datalake's bronze layer). `None` (default) uses a temporary directory removed on exit. |

`read()` returns a DataFrame whose columns are the source's own, upper-snake-cased
(`TckrSymb` → `TCKR_SYMB`), typed explicitly (never pandas' inference). Money columns are exact
`decimal.Decimal`, never binary `float`. Six provenance columns are appended to every frame:
`url`, `updated_at`, `source_key`, `package_version`, `ingestion_run_id`, `content_hash`. A
source that violates its declared contract raises `ContractError`.

### `BdiStocksSummaryReader`

The per-session cash-equities summary (B3 table `DailyAverageStocks`): one row per instrument
with the day's trade count and traded financial volume.

```python
from datetime import date
from filings_b3 import BdiStocksSummaryReader

df = BdiStocksSummaryReader(date(2025, 1, 2)).read()
```

Key columns: `TCKR_SYMB` (ticker), `NMBR_TRADES_DAY` (`Int64`), `VLM_TRADED_DAY` (`Decimal`, BRL).

### `BdiBtbLendingOpenPositionsReader`

The end-of-session securities-lending (*banco de títulos*, "BTB") snapshot (B3 table
`BTBLendingOpenPosition`): one row per instrument still out on loan, with the quantity on loan,
its average lending price, and the position's financial balance.

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
```

Key columns: `DT_REF` (session date), `TCKR_SYMB`, `ISIN`, `STOCK_BALANCE` (`Int64`, qty on
loan), `AVG_PRIC` (`Decimal`), `BALANCE` (`Decimal`, BRL).

---

## `__version__`

```python
import filings_b3

filings_b3.__version__  # the installed distribution version
```

---

## Conventions

| Convention | Rule |
|------------|------|
| Import path | From `filings_b3` only; the `_internal` subpackage is private |
| Return type | Every reader returns a typed, contract-validated `pandas.DataFrame` with provenance |
| Numbers | Money and any value whose fractional part matters are exact `Decimal`, never `float` |
| Type hints | Required on all public functions, including `-> None` |
| Docstrings | NumPy style; explain *why*, not *what* |
