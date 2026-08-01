"""Pesquisa por Pregão instruments file — ``ExrcEqtsInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying ``ExrcEqtsInf``
and maps that block's **complete** field list (10 fields per B3's taxonomy, 10 of them populated in
the reconciled session): exercícios de opções sobre ações.

The lifecycle — download, raw-artifact retention, XML flattening, contract, types, provenance —
is inherited from ``_base_instruments_file_reader._BaseInstrumentsFileReader``, which also
supplies the record-level columns common to every instrument type (report date, identification,
common attributes). Only the projection is declared here.

Prefer this reader over the consolidated
:class:`~filings_b3.search_trading_session.instruments_file.InstrumentsFileReader` when you want
one instrument type with all of its own fields; prefer the consolidated one when you want every
type sharing B3's published 52-column layout.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_EXRC_EQTS
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <ExrcEqtsInf> sub-block. Generated from B3's BVBG.028
# taxonomy and confirmed against a real IN file. A name is qualified by its parent only where
# the bare leaf would collide, since a block's own UndrlygInstrmId and TrgtInstrmId references
# repeat the ISO-20022 identification shape of the record itself.
_DICT_PATHS: dict[str, str] = {
	"DLVRY_TP_NM": "DlvryTp",
	"ISIN": "ISIN",
	"OPTN_EXRC_INSTRM_ID": "OptnExrcInstrmId/OthrId/Id",
	"OPTN_EXRC_INSTRM_ID_MKT_IDR_CD": "OptnExrcInstrmId/PlcOfListg/MktIdrCd",
	"SCTY_CTGY_NM": "SctyCtgy",
	"TCKR_SYMB": "TckrSymb",
	"TP": "OptnExrcInstrmId/OthrId/Tp/Prtry",
	"TRADG_CCY": "TradgCcy",
	"TRADG_END_DT": "TradgEndDt",
	"TRADG_START_DT": "TradgStartDt",
}

# Dates -> datetime.date; money/quantity/multiplier -> exact Decimal (never binary float). Every
# other column stays source text for fidelity, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = (
	"TRADG_END_DT",
	"TRADG_START_DT",
)
_LIST_DECIMAL_COLS: tuple[str, ...] = ()


class InstrumentsFileExrcEqtsReader(_BaseInstrumentsFileReader):
	"""Reader for the ``ExrcEqtsInf`` records of B3's instruments file.

	Covers exercícios de opções sobre ações. Downloads ``IN{yymmdd}.zip``, keeps the records
	carrying ``ExrcEqtsInf``, flattens this block's fields plus the record-level common
	columns, validates against ``INSTRUMENTS_FILE_EXRC_EQTS``, applies explicit types, and
	stamps provenance. No persistence — a distributable library returns the frame.

	Parameters
	----------
	date_ref : datetime.date
		Trading session to read; the URL is built for this date.
	path_raw : pathlib.Path, optional
		Directory in which to **keep** the downloaded raw ``.zip`` (the datalake's bronze layer).
		``None`` (default) uses a temporary directory removed on exit.
	cls_logger : LogEmitter, optional
		Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
	cls_retry_policy : RetryPolicy, optional
		Injected retry/backoff schedule for the download; ``None`` uses the seam's own default.
	"""

	str_source_key = "instruments_file_exrc_eqts"
	cls_contract = INSTRUMENTS_FILE_EXRC_EQTS
	str_sub_block = "ExrcEqtsInf"
	dict_own_paths = _DICT_PATHS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
