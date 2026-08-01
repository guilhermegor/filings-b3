"""Data contracts for the search_trading_session (Pesquisa por Pregão) section.

Mirrors ``src/filings_b3/search_trading_session/`` one-for-one: a reader
``search_trading_session/<dataset>.py`` has its contract at
``config/contracts/search_trading_session/<dataset>.py``. The section folder already names the
macro-section, so the filename drops any redundant source prefix.

Convention: **one contract per file**, each defining a single ``FileContract`` instance; this
aggregator re-exports them so the parent ``contracts`` package (and callers) import from one place.

The ``instruments_file*`` family all describe the **same** ``IN{yymmdd}.zip`` download read
through different projections: ``INSTRUMENTS_FILE`` spans every instrument type on B3's published
52-column UP2DATA layout, while each ``INSTRUMENTS_FILE_<TYPE>`` covers one ``InstrmInf``
sub-block with that block's complete field list. A few dataset names are long enough that their
fully-qualified module path exceeds the line limit; those imports carry an explicit ``noqa``
rather than shortening a name away from the dataset it migrates.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts.search_trading_session.instruments_file import (
	INSTRUMENTS_FILE,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_adr import (
	INSTRUMENTS_FILE_ADR,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_btc import (
	INSTRUMENTS_FILE_BTC,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_eqty import (
	INSTRUMENTS_FILE_EQTY,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_eqty_fwd import (  # noqa: E501
	INSTRUMENTS_FILE_EQTY_FWD,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_exrc_eqts import (  # noqa: E501
	INSTRUMENTS_FILE_EXRC_EQTS,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_fxd_incm import (  # noqa: E501
	INSTRUMENTS_FILE_FXD_INCM,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_optn_on_eqts import (  # noqa: E501
	INSTRUMENTS_FILE_OPTN_ON_EQTS,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_file_optn_on_spot_and_futures import (  # noqa: E501
	INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES,
)
from filings_b3._internal.config.contracts.search_trading_session.instruments_layout_meta import (
	INSTRUMENTS_LAYOUT_META,
)


__all__ = [
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
]
