"""BDI securities-lending open positions — the end-of-session *banco de títulos* (BTB) snapshot.

Reads B3's ``BTBLendingOpenPosition`` table from the Boletim Diário do Pregão: one row per
instrument still out on loan for a given trading session, with the quantity of shares on loan,
their average lending price, and the financial balance of the open positions.

Everything but the four declarations below is inherited from
:class:`~filings_b3.daily_bulletin._base_bdi_reader._BaseBdiReader` — the fetch, the raw-page
retention, the positional-values → named-columns mapping, contract enforcement, dtype coercion
and provenance stamping. That is the point of the section base: a new BDI dataset is a
declaration, not an implementation.

Usage::

    from datetime import date
    from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

    df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()

Keep the raw artifact for a datalake's bronze layer by passing ``path_raw``::

    df = BdiBtbLendingOpenPositionsReader(
        date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
    ).read()
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import BDI_BTB_LENDING_OPEN_POSITIONS
from filings_b3.daily_bulletin._base_bdi_reader import _BaseBdiReader


class BdiBtbLendingOpenPositionsReader(_BaseBdiReader):
	"""Reader for the BDI securities-lending open positions (``BTBLendingOpenPosition``).

	Single-page: the endpoint returns the session's open-position rows in one response, so the
	inherited ``int_max_pages = 1`` default applies and is not overridden here.

	The ten columns are taken from a **live** ``BTBLendingOpenPosition`` response, reconciled
	against B3's official *Posição em Aberto* glossary — not inferred from stpstone, which
	dropped the two leading date columns. ``RPT_DT`` is the source's hidden report-generation
	date (``hideColumn: true``); ``DT_REF`` is the visible trading session (the glossary's
	"Data"). Both are carried through and typed rather than discarded.

	Attributes
	----------
	str_source_key : str
		Provenance source key for this dataset.
	str_endpoint : str
		B3's table name under ``arquivos.b3.com.br/bdi/table``.
	cls_contract : FileContract
		The columns a consumer may rely on.
	list_date_cols : tuple of str
		``RPT_DT`` (report-generation date) and ``DT_REF`` (trading session) arrive as ISO
		timestamps and are coerced to pure :class:`datetime.date`.
	dict_dtypes : dict of {str: str}
		Explicit column types — never pandas' inference. Covers **every** non-date, non-decimal
		column the source sends, not merely the contract's required ones: an untyped pass-through
		column would reach the datalake with whatever pandas guessed from the first page's
		values. ``STOCK_BALANCE`` is a nullable ``Int64`` so a suppressed value stays NA rather
		than becoming ``0``.
	list_decimal_cols : tuple of str
		``AVG_PRIC`` (average lending price) and ``BALANCE`` (the position's financial value in
		BRL) are money, aggregated downstream across instruments and sessions. They are kept as
		exact :class:`decimal.Decimal`; ``float64`` would store the source's decimal as a
		slightly different binary value, and that error compounds through every aggregation until
		a reconciliation against B3's own totals misses by a hair, with nothing to point at. The
		source's own scale is preserved — no precision is chosen here.
	"""

	str_source_key = "bdi_btb_lending_open_positions"
	str_endpoint = "BTBLendingOpenPosition"
	cls_contract = BDI_BTB_LENDING_OPEN_POSITIONS
	list_date_cols = ("RPT_DT", "DT_REF")
	dict_dtypes = {  # noqa: RUF012 - declarative class-level config, matching the base's contract
		"TCKR_SYMB": "str",
		"ISIN": "str",
		"COMPANY": "str",
		"TYPE": "str",
		"MARKET": "str",
		"STOCK_BALANCE": "Int64",
	}
	list_decimal_cols = ("AVG_PRIC", "BALANCE")
