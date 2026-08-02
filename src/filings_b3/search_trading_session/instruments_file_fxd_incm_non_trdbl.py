"""Pesquisa por Pregão instruments file — ``FxdIncmNonTrdblInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying
``FxdIncmNonTrdblInf`` and maps that block's **complete** field list (46 fields per B3's catalog
v2.6, 39 of them populated in the reconciled session): renda fixa não negociável. This is the
widest of the 20 sub-blocks.

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

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_FXD_INCM_NON_TRDBL
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <FxdIncmNonTrdblInf> sub-block. Derived from B3's catalog v2.6
# (block anchor 4.20), cross-checked against the taxonomy sheet and a real IN file. A monetary
# column carries its `Ccy` attribute as a companion — ISO-20022 puts the unit in an attribute of
# the amount, so a text-only read would lose the currency of every value.
#
# Seven declared fields were absent from the reconciled session (EARLY_RED_DT,
# PERPTL_DBNR_INITL_PMT, PMT_PRDCTY_TP, SPCFCTN_NM and the three TRGT_INSTRM_ID leaves). All are
# [0..1], or sit under the [0..*] TrgtInstrmId container, so the absence is legitimate
# non-population — they are mapped so a session that does carry them reads.
_DICT_PATHS: dict[str, str] = {
	"ASST_ADDTL_COLL_TP": "AsstAddtlCollTp",
	"ASST_COLL_TP": "AsstCollTp",
	"ASST_IND": "AsstInd/OthrId/Id",
	"ASST_IND_TP": "AsstInd/OthrId/Tp/Prtry",
	"ASST_IND_MKT_IDR_CD": "AsstInd/PlcOfListg/MktIdrCd",
	"ASST_REGN_DT": "AsstRegnDt",
	"ASST_SUBRDNTD_TP": "AsstSubrdntdTp",
	"BASE_DT": "BaseDt",
	"CFICD": "CFICd",
	"CRPN_NM": "CrpnNm",
	"CTDY_TRTMNT_TP_NM": "CtdyTrtmntTp",
	"DBNR_CONVTBLT_TP": "DbnrConvtbltTp",
	"DBNR_TAX_BNFT_ARTL1_IND": "DbnrTaxBnft/Artl1Ind",
	"DBNR_TAX_BNFT_ARTL2_IND": "DbnrTaxBnft/Artl2Ind",
	"DSTRBTN_ID": "DstrbtnId",
	"EARLY_RED_DT": "EarlyRedDt",
	"EARLY_RED_IND": "EarlyRedInd",
	"EXDSTRBTN_NB": "EXDstrbtnNb",
	"FRST_PRIC": "FrstPric",
	"FRST_PRIC_CCY": "FrstPric/@Ccy",
	"INDX_PCTG": "IndxPctg",
	"INTRST_RATE": "IntrstRate",
	# Present in the live file but newer than the 2017 catalog, whose neighbouring row is the
	# clipped IntrstRateCrrctnT. The taxonomy sheet does list it.
	"INTRST_RATE_CRRCTN_TM_BASE": "IntrstRateCrrctnTmBase",
	"INTRST_RATE_CRRCTN_TP": "IntrstRateCrrctnTp",
	"ISIN": "ISIN",
	"ISSE_CD": "IsseCd",
	"ISSE_DT": "IsseDt",
	"LAST_PRIC": "LastPric",
	"LAST_PRIC_CCY": "LastPric/@Ccy",
	"MKT_CPTLSTN": "MktCptlstn",
	"MKT_CPTLSTN_CCY": "MktCptlstn/@Ccy",
	"PERPTL_DBNR_IND": "PerptlDbnrInd",
	"PERPTL_DBNR_INITL_PMT": "PerptlDbnrInitlPmt",
	"PMT_PRDCTY_TP": "PmtPrdctyTp",
	"RSK_RATG": "RskRatg",
	"SCTY_CTGY_NM": "SctyCtgy",
	"SPCFCTN_CD": "SpcfctnCd",
	"SPCFCTN_NM": "SpcfctnNm",
	"SRS_NB": "SrsNb",
	"TCKR_SYMB": "TckrSymb",
	"TRADG_CCY": "TradgCcy",
	"TRADG_END_DT": "TradgEndDt",
	"TRADG_START_DT": "TradgStartDt",
	"TRGT_INSTRM_ID": "TrgtInstrmId/OthrId/Id",
	"TRGT_INSTRM_ID_TP": "TrgtInstrmId/OthrId/Tp/Prtry",
	"TRGT_INSTRM_ID_MKT_IDR_CD": "TrgtInstrmId/PlcOfListg/MktIdrCd",
	"TTL_SRS_ISSE_VAL": "TtlSrsIsseVal",
	"UNIT_VAL": "UnitVal",
	"XPRTN_DT": "XprtnDt",
}

# Dates -> datetime.date; money/quantity/rate -> exact Decimal (never binary float). Every other
# column stays source text for fidelity, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = (
	"ASST_REGN_DT",
	"BASE_DT",
	"EARLY_RED_DT",
	"ISSE_DT",
	"PERPTL_DBNR_INITL_PMT",
	"TRADG_END_DT",
	"TRADG_START_DT",
	"XPRTN_DT",
)
_LIST_DECIMAL_COLS: tuple[str, ...] = (
	"FRST_PRIC",
	"INDX_PCTG",
	"INTRST_RATE",
	"LAST_PRIC",
	"MKT_CPTLSTN",
	"TTL_SRS_ISSE_VAL",
	"UNIT_VAL",
)


class InstrumentsFileFxdIncmNonTrdblReader(_BaseInstrumentsFileReader):
	"""Reader for the ``FxdIncmNonTrdblInf`` records of B3's instruments file.

	Covers renda fixa não negociável. Downloads ``IN{yymmdd}.zip``, keeps the records carrying
	``FxdIncmNonTrdblInf``, flattens this block's fields plus the record-level common columns,
	validates against ``INSTRUMENTS_FILE_FXD_INCM_NON_TRDBL``, applies explicit types, and stamps
	provenance. No persistence — a distributable library returns the frame.

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

	str_source_key = "instruments_file_fxd_incm_non_trdbl"
	cls_contract = INSTRUMENTS_FILE_FXD_INCM_NON_TRDBL
	str_sub_block = "FxdIncmNonTrdblInf"
	dict_own_paths = _DICT_PATHS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
