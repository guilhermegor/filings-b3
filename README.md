# Filings B3 <img src="assets/b3-brasil-bolsa-balcao.png" align="right" width="200" style="border-radius: 15px;" alt="Filings B3">

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI Version](https://img.shields.io/pypi/v/filings-b3)
[![Snyk Vulnerabilities](https://snyk.io/test/github/guilhermegor/filings-b3/badge.svg)](https://snyk.io/test/github/guilhermegor/filings-b3)
[![Snyk License](https://snyk.io/advisor/python/filings-b3/badge.svg)](https://snyk.io/advisor/python/filings-b3)
![PyPI Downloads](https://static.pepy.tech/badge/filings-b3)
[![Linting](https://img.shields.io/badge/linting-ruff_|_codespell-blue)](https://github.com/astral-sh/ruff)
![Formatting: isort](https://img.shields.io/badge/formatting-isort-%231674b1)
![Test Coverage](./coverage.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Open Issues](https://img.shields.io/github/issues/guilhermegor/filings-b3)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

Simple and efficient Python library to interact with B3 (Brazil's exchange) public datasets.
Each reader turns one trading session into a typed, contract-validated `pandas.DataFrame`
carrying provenance — money as exact `Decimal`, never a lossy `float`.

## ✨ Key Features

### 📊 Daily Bulletin (BDI) readers
- [`BdiStocksSummaryReader`](https://guilhermegor.github.io/filings-b3/api/reference/) — the per-session cash-equities summary (`DailyAverageStocks`).
- [`BdiBtbLendingOpenPositionsReader`](https://guilhermegor.github.io/filings-b3/api/reference/) — the securities-lending (BTB) open-position snapshot (`BTBLendingOpenPosition`).

### 🔒 Fidelity by construction
- **Explicit typing** — every column typed on load, never pandas' inference.
- **Exact decimals** — money and any value whose fractional part matters is `decimal.Decimal`, never a binary `float`.
- **Contracts** — a source that drops a required column fails loudly with `ContractError`, verified against B3's own published layouts.

### 🧾 Provenance & bronze layer
- Six provenance columns on every frame (`url`, `updated_at`, `source_key`, `package_version`, `ingestion_run_id`, `content_hash`).
- Pass `path_raw=` to retain each untouched source page for a datalake's bronze layer.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Poetry (recommended)
- Optional: Makefile

### Installation

**Option 1: Pip (recommended)**
```bash
pip install filings-b3
```

**Option 2: Build from source**
```bash
git clone https://github.com/guilhermegor/filings-b3.git
cd filings-b3
pyenv install 3.12.2
pyenv local 3.12.2
poetry install --no-root
poetry shell
```

### Basic usage
```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "STOCK_BALANCE", "BALANCE"]].head())
```

`date_ref` is **required** — the BDI endpoint is date-addressed, so there is no "latest"
default. See the [documentation](https://guilhermegor.github.io/filings-b3/) for every reader
and more recipes.

### Running Tests
```bash
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
```

## 📂 Project Structure
```
filings-b3/
├── .github/
│   ├── workflows/
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
├── assets/
│   └── b3-brasil-bolsa-balcao.png
├── bin/
├── docs/
├── src/filings_b3/
│   ├── daily_bulletin/          # Boletim Diário do Pregão (BDI) readers
│   ├── search_trading_session/  # Pesquisa por Pregão readers
│   └── _internal/               # private: contracts, utils, ports
├── tests/
│   ├── unit/
│   ├── integration/
│   └── performance/
├── LICENSE
├── Makefile
├── poetry.lock
├── pyproject.toml
├── README.md
└── requirements.txt
```

## 👨‍💻 Authors
- guilhermegor — [GitHub](https://github.com/guilhermegor)

## 📜 License
This project is licensed under the MIT License — see [LICENSE](LICENSE).

## 🔗 Useful Links
- [Documentation](https://guilhermegor.github.io/filings-b3/)
- [GitHub Repository](https://github.com/guilhermegor/filings-b3)
- [Issue Tracker](https://github.com/guilhermegor/filings-b3/issues)
