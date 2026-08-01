"""Pesquisa por Pregão instruments file — ``OptnOnSpotAndFutrsInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying
``OptnOnSpotAndFutrsInf`` and maps that block's **complete** field list (27 fields per B3's
taxonomy, 26 of them populated in the reconciled session): opções sobre disponível e futuros.

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

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <OptnOnSpotAndFutrsInf> sub-block. Generated from B3's BVBG.028
# taxonomy and confirmed against a real IN file. A name is qualified by its parent only where
# the bare leaf would collide, since a block's own UndrlygInstrmId and TrgtInstrmId references
# repeat the ISO-20022 identification shape of the record itself.
_DICT_PATHS: dict[str, str] = {
	"ALLCN_RND_LOT": "AllcnRndLot",
	"ASST_QTN_QTY": "AsstQtnQty",
	"ASST_STTLM_IND": "AsstSttlmInd/OthrId/Id",
	"ASST_STTLM_IND_MKT_IDR_CD": "AsstSttlmInd/PlcOfListg/MktIdrCd",
	"ASST_STTLM_IND_TP": "AsstSttlmInd/OthrId/Tp/Prtry",
	"CFICD": "CFICd",
	"CLNR_DAYS": "ClnrDays",
	"CTRCT_MLTPLR": "CtrctMltplr",
	"EXRC_PRIC": "ExrcPric",
	"EXRC_PRIC_CCY": "ExrcPric/@Ccy",
	"EXRC_STYLE": "ExrcStyle",
	"ISIN": "ISIN",
	"OPNG_POS_LMT_DT": "OpngPosLmtDt",
	"OPTN_TP": "OptnTp",
	"PMT_TP": "PmtTp",
	"PRM_UPFRNT_IND": "PrmUpfrntInd",
	"PURE_GOLD_WGHT": "PureGoldWght",
	"TCKR_SYMB": "TckrSymb",
	"TRADG_CCY": "TradgCcy",
	"TRADG_END_DT": "TradgEndDt",
	"TRADG_START_DT": "TradgStartDt",
	"UNDRLYG_INSTRM_ID": "UndrlygInstrmId/OthrId/Id",
	"UNDRLYG_INSTRM_ID_MKT_IDR_CD": "UndrlygInstrmId/PlcOfListg/MktIdrCd",
	"UNDRLYG_INSTRM_ID_TP": "UndrlygInstrmId/OthrId/Tp/Prtry",
	"WDRWL_DAYS": "WdrwlDays",
	"WRKG_DAYS": "WrkgDays",
	"XPRTN_CD": "XprtnCd",
	"XPRTN_DT": "XprtnDt",
}

# Dates -> datetime.date; money/quantity/multiplier -> exact Decimal (never binary float). Every
# other column stays source text for fidelity, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = (
	"OPNG_POS_LMT_DT",
	"TRADG_END_DT",
	"TRADG_START_DT",
	"XPRTN_DT",
)
_LIST_DECIMAL_COLS: tuple[str, ...] = (
	"ASST_QTN_QTY",
	"CTRCT_MLTPLR",
	"EXRC_PRIC",
	"PURE_GOLD_WGHT",
)


class InstrumentsFileOptnOnSpotAndFuturesReader(_BaseInstrumentsFileReader):
	"""Reader for the ``OptnOnSpotAndFutrsInf`` records of B3's instruments file.

	Covers opções sobre disponível e futuros. Downloads ``IN{yymmdd}.zip``, keeps the records
	carrying ``OptnOnSpotAndFutrsInf``, flattens this block's fields plus the record-level
	common columns, validates against ``INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES``, applies
	explicit types, and stamps provenance. No persistence — a distributable library returns the
	frame.

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

	str_source_key = "instruments_file_optn_on_spot_and_futures"
	cls_contract = INSTRUMENTS_FILE_OPTN_ON_SPOT_AND_FUTURES
	str_sub_block = "OptnOnSpotAndFutrsInf"
	dict_own_paths = _DICT_PATHS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
