"""Pesquisa por Pregão consolidated instruments file (BVBG.028.02) reader.

Reads B3's daily ``IN{yymmdd}.zip`` from ``www.b3.com.br/pesquisapregao/download``: one ISO-20022
``InstrumentReport`` (BVBG.028.02) XML holding every instrument registered for the session, across
equities, futures, options, gold, strategies and fixed income — one row per instrument.

Unlike the CSV/ZIP datasets served by the section's tabular base (``_base_pregao_reader``), this
source is **nested XML**, so it rides
:class:`~filings_b3.search_trading_session._base_instruments_file_reader._BaseInstrumentsFileReader`
— the section-local base shared by every reader of this one file — which composes the same
``_internal`` seams (download-with-retry, raw-artifact retention, provenance) but flattens
through :func:`~filings_b3._internal.utils.xml_reader.read_xml` instead of
:func:`~filings_b3._internal.utils.tabular_reader.read_table`.

This reader is the **consolidated** projection: it spans every instrument type, so it sets
``dict_full_paths`` (whole record-relative paths, wildcard included) and opts out of the base's
common-block columns — its column set is pinned to B3's published UP2DATA layout by the
contract-drift oracle, which would report any column the layout does not declare. The **per-type**
readers (``instruments_file_adr`` and siblings) take the opposite deal: the base's common columns
plus their own sub-block's complete field list.

The 52 columns come from B3's authoritative ``BVBG.028 para UP2DATA`` layout (sheet
``InstrumentsConsolidatedFile``); their names are ``pascal_to_upper_snake`` of the BVBG.028 tag
abbreviation (matching ``daily_bulletin``). Each column's :data:`_DICT_PATHS` path is resolved
relative to a record ``<Instrm>``; a ``*`` segment (see :func:`read_xml`) matches whichever of
B3's 17 instrument sub-blocks the record carries, so one ``InstrmInf/*/<tag>`` path covers every
type — and any type B3 adds later.

Verified live against a real ``IN260729.zip`` (issue #143, 183,164 records): the row element is
``<Instrm>``; ``RptParams`` (hence the report date) is **per-record**, not file-level; and the file
holds **17** sub-block types, not the 7 the UP2DATA consolidated sheet enumerates (``EqtyInf``,
``FutrCtrctsInf``, ``OptnOnEqtsInf``, ``ExrcEqtsInf``, ``ADRInf``, ``BTCInf``, ``CshInf``, …). The
wildcard covers all of them. Columns that a given instrument type does not carry (a cash or bond
record has no ``TckrSymb``) are legitimately null — the source has no such value.

# ponytail: read_xml loads the whole XML tree in memory — the real IN file is ~660 MB (~4 GB
# resident). Fine on a workstation and for the weekly job; switch read_xml to an iterparse stream
# keyed on the row tag if a memory-constrained consumer needs it (tracked as a follow-up).
"""

from __future__ import annotations

from collections.abc import Mapping

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column -> the element path relative to a record <Instrm>. A `*` segment is a single-level
# wildcard matching whichever instrument sub-block the record carries (BVBG.028 nests each
# instrument's fields under exactly one of 17 <InstrmInf> sub-blocks — EqtyInf, FutrCtrctsInf,
# OptnOnEqtsInf, ExrcEqtsInf, ADRInf, BTCInf, …), so one `InstrmInf/*/<tag>` path covers every
# type and any type B3 adds later. Field tags are B3's BVBG.028 names (confirmed against a live
# IN file); the common block <FinInstrmAttrCmon> and the strategy legs keep their explicit paths.
_DICT_PATHS: dict[str, tuple[str, ...]] = {
	"RPT_DT": ("RptParams/RptDtAndTm/Dt",),
	"TCKR_SYMB": ("InstrmInf/*/TckrSymb",),
	"ASST": ("FinInstrmAttrCmon/Asst",),
	"ASST_DESC": ("FinInstrmAttrCmon/AsstDesc",),
	"SGMT_NM": ("FinInstrmAttrCmon/Sgmt",),
	"MKT_NM": ("FinInstrmAttrCmon/Mkt",),
	"SCTY_CTGY_NM": ("InstrmInf/*/SctyCtgy",),
	"XPRTN_DT": ("InstrmInf/*/XprtnDt",),
	"XPRTN_CD": ("InstrmInf/*/XprtnCd",),
	"TRADG_START_DT": ("InstrmInf/*/TradgStartDt",),
	"TRADG_END_DT": ("InstrmInf/*/TradgEndDt",),
	"BASE_CD": ("InstrmInf/*/BaseCd",),
	"CONVS_CRIT_NM": ("InstrmInf/*/ConvsCrit",),
	"MTRTY_DT_TRGT_PT": ("InstrmInf/*/MtrtyDtTrgtPt",),
	"REQRD_CONVS_IND": ("InstrmInf/*/ReqrdConvsInd",),
	"ISIN": ("InstrmInf/*/ISIN",),
	"CFICD": ("InstrmInf/*/CFICd",),
	"DLVRY_NTCE_START_DT": ("InstrmInf/*/DlvryNtceStartDt",),
	"DLVRY_NTCE_END_DT": ("InstrmInf/*/DlvryNtceEndDt",),
	"OPTN_TP": ("InstrmInf/*/OptnTp",),
	"CTRCT_MLTPLR": ("InstrmInf/*/CtrctMltplr",),
	"ASST_QTN_QTY": ("InstrmInf/*/AsstQtnQty",),
	"ALLCN_RND_LOT": ("InstrmInf/*/AllcnRndLot",),
	"TRADG_CCY": ("InstrmInf/*/TradgCcy",),
	"DLVRY_TP_NM": ("InstrmInf/*/DlvryTp",),
	"WDRWL_DAYS": ("InstrmInf/*/WdrwlDays",),
	"WRKG_DAYS": ("InstrmInf/*/WrkgDays",),
	"CLNR_DAYS": ("InstrmInf/*/ClnrDays",),
	"RLVR_BASE_PRIC_NM": ("InstrmInf/*/RlvrBasePricCd",),
	"OPNG_FUTR_POS_DAY": ("InstrmInf/*/OpngFutrPosDay",),
	# Strategy legs. The matching underlying columns are self-joins, declared in _DICT_JOINS below
	# rather than here. An indexed segment addresses the n-th repeat of the leg container, 1-based.
	"SD_TP_CD1": ("InstrmInf/StrtgyInf/StrtgyLegList[1]/SdTpCd",),
	"SD_TP_CD2": ("InstrmInf/StrtgyInf/StrtgyLegList[2]/SdTpCd",),
	"PURE_GOLD_WGHT": ("InstrmInf/*/PureGoldWght",),
	"EXRC_PRIC": ("InstrmInf/*/ExrcPric",),
	"OPTN_STYLE": ("InstrmInf/*/OptnStyle",),
	"VAL_TP_NM": ("InstrmInf/*/ValTpCd",),
	"PRM_UPFRNT_IND": ("InstrmInf/*/PrmUpfrntInd",),
	"OPNG_POS_LMT_DT": ("InstrmInf/*/OpngPosLmtDt",),
	"DSTRBTN_ID": ("InstrmInf/*/DstrbtnId",),
	"PRIC_FCTR": ("InstrmInf/*/PricFctr",),
	"DAYS_TO_STTLM": ("InstrmInf/*/DaysToSttlm",),
	"SRS_TP_NM": ("InstrmInf/*/SrsTp",),
	"PRTCN_FLG": ("InstrmInf/*/PrtcnFlg",),
	"AUTOMTC_EXRC_IND": ("InstrmInf/*/AutomtcExrcInd",),
	"SPCFCTN_CD": ("InstrmInf/*/SpcfctnCd",),
	"CRPN_NM": ("InstrmInf/*/CrpnNm",),
	"CORP_ACTN_START_DT": ("InstrmInf/*/CorpActnStartDt",),
	"CTDY_TRTMNT_TP_NM": ("InstrmInf/*/CtdyTrtmntTp",),
	"MKT_CPTLSTN": ("InstrmInf/*/MktCptlstn",),
	"CORP_GOVN_LVL_NM": ("InstrmInf/*/GovnInd",),
}

# The two strategy-leg underlyings are **self-joins**, not paths: a leg references the other
# instrument by an opaque proprietary id (`200001037989`), while the ticker the UP2DATA layout
# promises (`UNDRLYG_TCKR_SYMB`) lives on that other instrument's own record. Each entry is
# (foreign key on this record, primary key on any record, value to bring back). Verified against a
# real IN file: all 378 distinct leg ids resolve, so no strategy leg is left dangling.
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

# Dates → datetime.date; money/quantity/multiplier → exact Decimal (never binary float). Every
# other column stays source text (str) for fidelity — the source's exact bytes, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = (
	"RPT_DT",
	"XPRTN_DT",
	"TRADG_START_DT",
	"TRADG_END_DT",
	"DLVRY_NTCE_START_DT",
	"DLVRY_NTCE_END_DT",
	"OPNG_POS_LMT_DT",
	"CORP_ACTN_START_DT",
)
_LIST_DECIMAL_COLS: tuple[str, ...] = (
	"CTRCT_MLTPLR",
	"ASST_QTN_QTY",
	"PURE_GOLD_WGHT",
	"EXRC_PRIC",
	"MKT_CPTLSTN",
)


class InstrumentsFileReader(_BaseInstrumentsFileReader):
	"""Reader for B3's Pesquisa por Pregão consolidated instruments file (BVBG.028.02).

	Downloads ``IN{yymmdd}.zip``, extracts its single XML member, flattens each instrument record
	into a row via :func:`~filings_b3._internal.utils.xml_reader.read_xml`, validates against
	:data:`~filings_b3._internal.config.contracts.INSTRUMENTS_FILE`, applies explicit types, and
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

	str_source_key = "instruments_file"
	cls_contract = INSTRUMENTS_FILE
	# This reader spans every instrument type, so it supplies whole record-relative paths
	# including the wildcard, and takes none of the common-block columns the per-type readers
	# inherit. Its column set is exactly B3's published UP2DATA layout, which the drift oracle
	# checks column for column, so adding a column here would be reported as drift.
	dict_full_paths = _DICT_PATHS
	dict_joins = _DICT_JOINS
	dict_common_paths: Mapping[str, str] = {}  # noqa: RUF012 - by convention, never mutated
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
