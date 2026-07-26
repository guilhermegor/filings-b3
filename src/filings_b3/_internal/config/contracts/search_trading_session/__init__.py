"""Data contracts for the search_trading_session (Pesquisa por Pregão) section.

Mirrors ``src/filings_b3/search_trading_session/`` one-for-one: a reader
``search_trading_session/<dataset>.py`` has its contract at
``config/contracts/search_trading_session/<dataset>.py``. The section folder already names the
macro-section, so the filename drops any redundant source prefix.

Convention: **one contract per file**, each defining a single ``FileContract`` instance; this
aggregator re-exports them so the parent ``contracts`` package (and callers) import from one place.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts.search_trading_session.instruments_file import (
	INSTRUMENTS_FILE,
)


__all__ = ["INSTRUMENTS_FILE"]
