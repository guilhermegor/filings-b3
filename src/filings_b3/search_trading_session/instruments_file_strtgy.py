"""Pesquisa por Pregão instruments file — ``StrtgyInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying ``StrtgyInf``
and maps that block's **complete** field list (23 fields per B3's catalog v2.6, all 23 populated in
the reconciled session): estratégias (operações estruturadas).

**The legs repeat, so they are published per leg.** ``StrtgyLegList`` is ``[1..*]`` — 1,012 of the
1,065 strategy records carry two legs, 53 carry one — so an un-indexed path would silently keep
leg 1 and drop leg 2. Each leg field is therefore mapped twice, through the seam's ``Tag[n]``
sibling-repeat segment, and named with the consolidated reader's ``1``/``2`` suffix. This is the
defect class of #149, where the four leg columns shipped null on 100% of records because
``SdTpCd`` was mapped as a *child* of ``LegId``; B3's catalog v2.6 (``4.8.17.1``–``4.8.17.3``)
independently confirms they are **siblings**.

Each leg's underlying is published **twice**, deliberately: ``UNDRLYG_INSTRM_ID{n}`` is the raw
proprietary id the document declares, and ``UNDRLYG_TCKR_SYMB{n}`` is that id resolved to the
referenced instrument's ticker by in-document self-join — the same pair of columns the
consolidated reader publishes, so the two agree instead of forcing a consumer to re-derive one
from the other.

The lifecycle — download, raw-artifact retention, XML flattening, contract, types, provenance —
is inherited from ``_base_instruments_file_reader._BaseInstrumentsFileReader``, which also
supplies the record-level columns common to every instrument type (report date, identification,
common attributes). Only the projection is declared here.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_STRTGY
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <StrtgyInf> sub-block. Derived from B3's catalog v2.6 (block
# anchor 4.8), cross-checked against the taxonomy sheet and a real IN file.
_DICT_PATHS: dict[str, str] = {
	"ALLCN_RND_LOT": "AllcnRndLot",
	"ASST_STTLM_IND": "AsstSttlmInd/OthrId/Id",
	"ASST_STTLM_IND_TP": "AsstSttlmInd/OthrId/Tp/Prtry",
	"ASST_STTLM_IND_MKT_IDR_CD": "AsstSttlmInd/PlcOfListg/MktIdrCd",
	"CFICD": "CFICd",
	"ISIN": "ISIN",
	"OPNG_FUTR_POS_DAY": "OpngFutrPosDay",
	"PRTL_GV_UP_ALLWNC_IND": "PrtlGvUpAllwncInd",
	"RLVR_BASE_PRIC_NM": "RlvrBasePricCd",
	"SCTY_CTGY_NM": "SctyCtgy",
	"STTLM_IND_MLTPLR": "SttlmIndMltplr",
	"TCKR_SYMB": "TckrSymb",
	"TRADG_CCY": "TradgCcy",
	"TRADG_END_DT": "TradgEndDt",
	"TRADG_START_DT": "TradgStartDt",
	"VAL_TP_NM": "ValTpCd",
	"XPRTN_CD": "XprtnCd",
	"XPRTN_DT": "XprtnDt",
	# The two legs. An indexed segment selects the n-th sibling repeat of the leg container,
	# 1-based. LegId is a SIBLING of these values, never their parent — mapping it as a parent is
	# what made #149's columns null on every row.
	"LEG_ID1": "StrtgyLegList[1]/LegId",
	"SD_TP_CD1": "StrtgyLegList[1]/SdTpCd",
	"UNDRLYG_INSTRM_ID1": "StrtgyLegList[1]/UndrlygInstrmId/OthrId/Id",
	"UNDRLYG_INSTRM_ID_TP1": "StrtgyLegList[1]/UndrlygInstrmId/OthrId/Tp/Prtry",
	"UNDRLYG_INSTRM_ID_MKT_IDR_CD1": "StrtgyLegList[1]/UndrlygInstrmId/PlcOfListg/MktIdrCd",
	"LEG_ID2": "StrtgyLegList[2]/LegId",
	"SD_TP_CD2": "StrtgyLegList[2]/SdTpCd",
	"UNDRLYG_INSTRM_ID2": "StrtgyLegList[2]/UndrlygInstrmId/OthrId/Id",
	"UNDRLYG_INSTRM_ID_TP2": "StrtgyLegList[2]/UndrlygInstrmId/OthrId/Tp/Prtry",
	"UNDRLYG_INSTRM_ID_MKT_IDR_CD2": "StrtgyLegList[2]/UndrlygInstrmId/PlcOfListg/MktIdrCd",
}

# Each leg's underlying ticker is a **self-join**, not a path: the leg references the other
# instrument by an opaque proprietary id (`200001037989`), while its ticker lives on that other
# instrument's own record. Each entry is (foreign key on this record, primary key on any record,
# value to bring back). Unlike dict_own_paths these are record-relative, since the join reaches
# outside this sub-block by design. Mirrors the consolidated reader so the two agree exactly.
_DICT_JOINS: dict[str, tuple[str, str, str]] = {
	"UNDRLYG_TCKR_SYMB1": (
		"InstrmInf/StrtgyInf/StrtgyLegList[1]/UndrlygInstrmId/OthrId/Id",
		"FinInstrmId/OthrId/Id",
		"InstrmInf/*/TckrSymb",
	),
	"UNDRLYG_TCKR_SYMB2": (
		"InstrmInf/StrtgyInf/StrtgyLegList[2]/UndrlygInstrmId/OthrId/Id",
		"FinInstrmId/OthrId/Id",
		"InstrmInf/*/TckrSymb",
	),
}

# Dates -> datetime.date; money/quantity/multiplier -> exact Decimal (never binary float). Every
# other column stays source text for fidelity, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = ("TRADG_END_DT", "TRADG_START_DT", "XPRTN_DT")
_LIST_DECIMAL_COLS: tuple[str, ...] = ()


class InstrumentsFileStrtgyReader(_BaseInstrumentsFileReader):
	"""Reader for the ``StrtgyInf`` records of B3's instruments file.

	Covers estratégias (operações estruturadas). Downloads ``IN{yymmdd}.zip``, keeps the records
	carrying ``StrtgyInf``, flattens this block's fields — both strategy legs, each in its own
	columns — plus the record-level common columns, validates against ``INSTRUMENTS_FILE_STRTGY``,
	applies explicit types, and stamps provenance. No persistence — a distributable library returns
	the frame.

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

	str_source_key = "instruments_file_strtgy"
	cls_contract = INSTRUMENTS_FILE_STRTGY
	str_sub_block = "StrtgyInf"
	dict_own_paths = _DICT_PATHS
	dict_joins = _DICT_JOINS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
