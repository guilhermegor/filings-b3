# **Usage**

Installing and using `filings-b3` — typed access to B3 (Brazil's exchange) public datasets.

> **See also:** [API Reference](api/index.md) · [Examples](examples.md)

---

## Installation

```bash
pip install filings-b3
```

Or with Poetry:

```bash
poetry add filings-b3
```

---

## Basic usage

Every reader takes the trading session to read and returns a typed
`pandas.DataFrame` carrying provenance columns:

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "STOCK_BALANCE", "BALANCE"]].head())
```

`date_ref` is **required** — the BDI endpoint is date-addressed, so there is no
"latest" default. Want the previous business day? Compute it and pass it.

## Keeping the raw artifact (bronze layer)

Pass `path_raw` to retain each untouched source page for a datalake's bronze
layer — a contract break is then replayable against the exact bytes:

```python
from pathlib import Path

df = BdiBtbLendingOpenPositionsReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()
```

## What every reader guarantees

- Columns are the source's own, upper-snake-cased and **explicitly typed** — never pandas'
  inference.
- Money columns (`BALANCE`, `AVG_PRIC`, `VLM_TRADED_DAY`, …) are exact `decimal.Decimal`, never
  binary `float`.
- Six provenance columns on every frame: `url`, `updated_at`, `source_key`, `package_version`,
  `ingestion_run_id`, `content_hash`.
- A source that violates its declared contract raises `ContractError` — a missing required
  column fails loudly rather than silently.

See the [API Reference](api/reference.md) for the full reader list.

---

## Running tests

```bash
make unit_tests         # unit tests only
make integration_tests  # integration tests only
make test_cov           # unit tests + coverage report + badge
```

---

## Linting and formatting

```bash
make lint          # ruff check + ruff format + codespell + pydocstyle
```

---

## Publishing to PyPI

Two GitHub Actions workflows handle releases:

- **`release-test-pypi.yaml`** — publish to [Test PyPI](https://test.pypi.org) first.
- **`release-pypi.yaml`** — publish to [PyPI](https://pypi.org) and cut a GitHub release.

Trigger either from the **Actions** tab (`workflow_dispatch`) with the version to release.
Both gate on the new version being greater than the latest already published, build with
Poetry, and fall back to `twine` if `poetry publish` is unavailable.
