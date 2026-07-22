"""BDI daily average stocks summary — the cash-equities per-session summary reader.

Reads B3's ``DailyAverageStocks`` table from the Boletim Diário do Pregão: one row per
instrument for a given trading session, with the day's trade count and traded volume.

Everything but the four declarations below is inherited from
:class:`~filings_b3.daily_bulletin._base_bdi_reader._BaseBdiReader` — the fetch, the raw-page
retention, the positional-values → named-columns mapping, contract enforcement, dtype coercion
and provenance stamping. That is the point of the section base: a new BDI dataset is a
declaration, not an implementation.

Usage::

    from datetime import date
    from filings_b3 import BdiStocksSummaryReader

    df = BdiStocksSummaryReader(date(2025, 1, 2)).read()

Keep the raw artifact for a datalake's bronze layer by passing ``path_raw``::

    df = BdiStocksSummaryReader(date(2025, 1, 2), path_raw=Path("/data/bronze/b3")).read()
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import BDI_STOCKS_SUMMARY
from filings_b3.daily_bulletin._base_bdi_reader import _BaseBdiReader


class BdiStocksSummaryReader(_BaseBdiReader):
	"""Reader for the BDI daily average stocks summary (``DailyAverageStocks``).

	Single-page: the endpoint returns the session's summary rows in one response, so the
	inherited ``int_max_pages = 1`` default applies and is not overridden here.

	Attributes
	----------
	str_source_key : str
		Provenance source key for this dataset.
	str_endpoint : str
		B3's table name under ``arquivos.b3.com.br/bdi/table``.
	cls_contract : FileContract
		The columns a consumer may rely on.
	dict_dtypes : dict of {str: str}
		Explicit column types — never pandas' inference. Covers **every** column the source
		sends, not merely the contract's required ones: an untyped pass-through column would
		reach the datalake with whatever pandas guessed from the first page's values. Volume is
		``float64`` (a market aggregate, not a monetary amount needing decimal exactness); the
		counts are nullable ``Int64`` so a suppressed value stays NA instead of becoming ``0``.
	"""

	str_source_key = "bdi_stocks_summary"
	str_endpoint = "DailyAverageStocks"
	cls_contract = BDI_STOCKS_SUMMARY
	dict_dtypes = {  # noqa: RUF012 - declarative class-level config, matching the base's contract
		"TCKR_SYMB": "str",
		"NMBR_TRADES_DAY": "Int64",
		"VLM_TRADED_DAY": "float64",
		# Absent from the contract, since no consumer need depend on it, yet still sent by the
		# source and carried through — so it is typed here rather than left to inference.
		"COL_ORDER": "Int64",
	}
