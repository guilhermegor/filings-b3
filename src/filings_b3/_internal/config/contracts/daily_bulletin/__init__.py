"""Data contracts for the daily_bulletin (BDI) section.

Mirrors ``src/filings_b3/daily_bulletin/`` one-for-one: a reader
``daily_bulletin/<dataset>.py`` has its contract at
``config/contracts/daily_bulletin/<dataset>.py``. The section folder already names the
macro-section, so the filename drops the redundant ``bdi_`` prefix (``stocks_summary.py``,
not ``bdi_stocks_summary.py``).

Convention: **one contract per file**, each defining a single ``FileContract`` instance; this
aggregator re-exports them so the parent ``contracts`` package (and callers) import from one
place.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts.daily_bulletin.btb_lending_open_positions import (
	BDI_BTB_LENDING_OPEN_POSITIONS,
)
from filings_b3._internal.config.contracts.daily_bulletin.stocks_summary import (
	BDI_STOCKS_SUMMARY,
)


__all__ = [
	"BDI_BTB_LENDING_OPEN_POSITIONS",
	"BDI_STOCKS_SUMMARY",
]
