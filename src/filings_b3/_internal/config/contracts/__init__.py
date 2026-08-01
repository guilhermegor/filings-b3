"""Data contracts for the project's input files (config layer).

A contract is **declarative configuration** of an input's expected shape — which columns a
source must carry, which must hold valid CNPJs — *not* data access, so contracts live in
``config`` beside the other declarative config (``inputs.yaml``, ``connection_db``), imported
by the model loaders and the controller boundary.

Convention: contracts are grouped into **section subpackages that mirror
``src/filings_b3/`` one-for-one** (``daily_bulletin/stocks_summary.py`` beside the reader
``daily_bulletin/stocks_summary.py``), each file defining a single ``FileContract`` instance;
the section aggregators re-export upward so callers still import from one place:
``from filings_b3._internal.config.contracts import BDI_STOCKS_SUMMARY, find_file_problems``.

A contract names only the columns a consumer **depends on**, not every column the source sends:
B3 adding a column must not break a read, while a removed one must fail loudly. Extra source
columns still flow through to the frame (and must be typed in the reader's ``dict_dtypes``).
"""

from __future__ import annotations

from filings_b3._internal.config.contracts.daily_bulletin import (
	BDI_BTB_LENDING_OPEN_POSITIONS,
	BDI_STOCKS_SUMMARY,
)
from filings_b3._internal.config.contracts.search_trading_session import (
	INSTRUMENTS_FILE,
	INSTRUMENTS_FILE_ADR,
	INSTRUMENTS_FILE_BTC,
	INSTRUMENTS_FILE_EQTY,
	INSTRUMENTS_FILE_EQTY_FWD,
	INSTRUMENTS_FILE_EXRC_EQTS,
	INSTRUMENTS_FILE_FXD_INCM,
	INSTRUMENTS_FILE_OPTN_ON_EQTS,
	INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES,
	INSTRUMENTS_LAYOUT_META,
)
from filings_b3._internal.utils.tabular_reader import (
	ContractError,
	FileContract,
	find_file_problems,
)


__all__ = [
	"BDI_BTB_LENDING_OPEN_POSITIONS",
	"BDI_STOCKS_SUMMARY",
	"INSTRUMENTS_FILE",
	"INSTRUMENTS_FILE_ADR",
	"INSTRUMENTS_FILE_BTC",
	"INSTRUMENTS_FILE_EQTY",
	"INSTRUMENTS_FILE_EQTY_FWD",
	"INSTRUMENTS_FILE_EXRC_EQTS",
	"INSTRUMENTS_FILE_FXD_INCM",
	"INSTRUMENTS_FILE_OPTN_ON_EQTS",
	"INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES",
	"INSTRUMENTS_LAYOUT_META",
	"ContractError",
	"FileContract",
	"find_file_problems",
]
