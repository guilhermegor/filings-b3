"""Pesquisa por Pregão consolidated instruments file (BVBG.028.02) reader.

Reads B3's daily ``IN{yymmdd}.zip`` from ``www.b3.com.br/pesquisapregao/download``: one ISO-20022
``InstrumentReport`` (BVBG.028.02) XML holding every instrument registered for the session, across
equities, futures, options, gold, strategies and fixed income — one row per instrument.

Unlike the CSV/ZIP datasets served by the section's tabular base (``_base_pregao_reader``), this
source is **nested XML**, so the reader implements the
:class:`~filings_b3._internal.config.ports.ingestion_reader.IngestionReader` port directly (as the
port's docstring prescribes for a source that fits no tabular family), composing the same
``_internal`` seams the base uses — download-with-retry, raw-artifact retention, provenance — but
flattening the XML through :func:`~filings_b3._internal.utils.xml_reader.read_xml` instead of
:func:`~filings_b3._internal.utils.tabular_reader.read_table`.

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

from datetime import date
from pathlib import Path

import pandas as pd

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
from filings_b3._internal.config.ports.ingestion_reader import IngestionReader
from filings_b3._internal.utils.provenance import (
	hash_artifact,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.raw_workspace import raw_workspace
from filings_b3._internal.utils.retry import LogEmitter, RetryPolicy
from filings_b3._internal.utils.xml_reader import read_xml
from filings_b3._internal.utils.zip_extractor import extract_all
from filings_b3.search_trading_session._base_pregao_reader import PREGAO_DOWNLOAD_BASE


_DISTRIBUTION_NAME = "filings-b3"

# Local name of the repeating instrument-record element, confirmed against a live IN file:
# BVBG.028 wraps each instrument in <Instrm> (not the guessed <InstrmRcrd>).
_ROW_TAG = "Instrm"

# No file-level scalars: RPT_DT is per-record (each <Instrm> carries its own <RptParams>), so it
# lives in _DICT_PATHS below, not here.
_DICT_SCALARS: dict[str, str] = {}

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
	"SD_TP_CD1": ("InstrmInf/StrtgyInf/StrtgyLegList/LegId/SdTpCd",),
	"UNDRLYG_TCKR_SYMB1": ("InstrmInf/StrtgyInf/StrtgyLegList/LegId/UndrlygInstrmId",),
	"SD_TP_CD2": ("InstrmInf/StrtgyInf/StrtgyLegList/LegId/SdTpCd",),
	"UNDRLYG_TCKR_SYMB2": ("InstrmInf/StrtgyInf/StrtgyLegList/LegId/UndrlygInstrmId",),
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
# Text for every non-date, non-decimal column (fidelity: keep the source's exact string).
_DICT_DTYPES: dict[str, str] = {
	str_col: "str"
	for str_col in (*_DICT_SCALARS, *_DICT_PATHS)
	if str_col not in _LIST_DATE_COLS and str_col not in _LIST_DECIMAL_COLS
}


class InstrumentsFileReader(IngestionReader):
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

	def __init__(
		self,
		date_ref: date,
		path_raw: Path | None = None,
		cls_logger: LogEmitter | None = None,
		cls_retry_policy: RetryPolicy | None = None,
	) -> None:
		self.date_ref = date_ref
		self.path_raw = path_raw
		self._cls_logger = cls_logger if cls_logger is not None else LogEmitter()
		self._cls_retry_policy = cls_retry_policy

	def build_url(self) -> str:
		"""Return the ``IN{yymmdd}.zip`` download URL for :attr:`date_ref`.

		Returns
		-------
		str
			The Pesquisa por Pregão download URL for the session's instruments file.
		"""
		return f"{PREGAO_DOWNLOAD_BASE}?filelist=IN{self.date_ref:%y%m%d}.zip"

	def _locate_xml(self, path_download: Path, path_dir: Path) -> Path:
		"""Extract the ZIP and return its single XML member.

		Parameters
		----------
		path_download : pathlib.Path
			The downloaded ``IN{yymmdd}.zip``.
		path_dir : pathlib.Path
			The workspace directory to extract into.

		Returns
		-------
		pathlib.Path
			The extracted XML file.

		Raises
		------
		ValueError
			If the archive does not contain exactly one ``.xml`` member (fail loudly rather than
			guess which member to parse).
		"""
		list_xml = [
			path_member
			for path_member in extract_all(path_download, path_dir)
			if path_member.suffix.lower() == ".xml"
		]
		if len(list_xml) != 1:
			raise ValueError(
				f"expected exactly one .xml member in {path_download.name}, "
				f"found {[p.name for p in list_xml]}"
			)
		return list_xml[0]

	def read(self) -> pd.DataFrame:
		"""Fetch, flatten, and provenance-stamp the instruments file into a typed DataFrame.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped instrument rows.

		Raises
		------
		ContractError
			When the flattened frame violates :data:`INSTRUMENTS_FILE`.
		ValueError
			When the archive does not hold exactly one XML member.
		"""
		from filings_b3._internal.utils.http_downloader import download_file, url_filename

		str_url = self.build_url()
		with raw_workspace(self.path_raw) as path_dir:
			path_download = download_file(str_url, path_dir / url_filename(str_url))
			self._cls_logger.log_message(f"downloaded instruments_file from {str_url}", "info")
			path_xml = self._locate_xml(path_download, path_dir)
			df_typed = read_xml(
				path_xml,
				_ROW_TAG,
				_DICT_PATHS,
				_DICT_DTYPES,
				INSTRUMENTS_FILE,
				dict_scalars=_DICT_SCALARS,
				list_date_cols=_LIST_DATE_COLS,
				list_decimal_cols=_LIST_DECIMAL_COLS,
			)
			return stamp_provenance(
				df_typed,
				str_url,
				INSTRUMENTS_FILE,
				hash_artifact(path_download),
				resolve_package_version(_DISTRIBUTION_NAME),
			)
