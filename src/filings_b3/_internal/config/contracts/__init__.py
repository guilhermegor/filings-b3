"""Data contracts for the project's input files (config layer).

A contract is **declarative configuration** of an input's expected shape — which columns a
source must carry, which must hold valid CNPJs — *not* data access, so contracts live in
``config`` beside the other declarative config (``inputs.yaml``, ``connection_db``), imported
by the model loaders and the controller boundary.

Convention: **one file per source** under this package (``bdi_stocks_summary.py``, …), each
defining a single ``FileContract`` instance; this aggregator re-exports them (plus the
machinery from ``utils.tabular_reader``) so callers import from one place:
``from filings_b3._internal.config.contracts import BDI_STOCKS_SUMMARY, find_file_problems``.

A contract names only the columns a consumer **depends on**, not every column the source sends:
B3 adding a column must not break a read, while a removed one must fail loudly. Extra source
columns still flow through to the frame (and must be typed in the reader's ``dict_dtypes``).
"""

from __future__ import annotations

from filings_b3._internal.config.contracts.bdi_stocks_summary import BDI_STOCKS_SUMMARY
from filings_b3._internal.utils.tabular_reader import (
	ContractError,
	FileContract,
	find_file_problems,
)


__all__ = [
	"BDI_STOCKS_SUMMARY",
	"ContractError",
	"FileContract",
	"find_file_problems",
]
