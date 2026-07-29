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

The column→XML-path map (:data:`_DICT_PATHS` / :data:`_DICT_SCALARS`) is B3's authoritative
``BVBG.028 para UP2DATA`` layout (sheet ``InstrumentsConsolidatedFile``): each flat column resolves
the first present of its type-specific alternative paths under a record.

⚠️ **Pending live reconcile (issue #68).** Two things are not yet confirmed against a real ``IN``
file (the dev clock is future-dated, so B3 serves an empty ZIP for reachable days):

1. :data:`_ROW_TAG` — the local name of the repeating instrument-record element. The UP2DATA layout
   gives per-column paths *relative to a record* but not the record tag itself; this is a
   documented single-point-of-change assumption to verify first.
2. The multi-alternative XML paths for every field (the column **names** are now pinned to the
   library convention — ``pascal_to_upper_snake`` of the UP2DATA tag abbreviation — so only the
   paths and the row tag need confirming against real XML).

Both are isolated to the module-level constants below so reconciling is a localized edit.
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

# Local name of the repeating instrument-record element (see the ⚠ live-reconcile note above).
_ROW_TAG = "InstrmRcrd"

# File-level scalar: resolved once against the root and broadcast to every row.
_DICT_SCALARS: dict[str, str] = {"RPT_DT": "RptParams/RptDtAndTm/Dt"}

# Column → ordered alternative element paths (relative to a record). The first path that resolves
# for a given record supplies the value; a record of a different instrument type leaves it empty.
# Transcribed from the UP2DATA InstrumentsConsolidatedFile layout (BVBG.028.02).
_EQ = "InstrmInf/EqtyInf"
_FUT = "InstrmInf/FutrCtrctsInf"
_OSF = "InstrmInf/OptnOnSpotAndFutrsInf"
_OEQ = "InstrmInf/OptnOnEqtsInf"
_GLD = "InstrmInf/SpotGoldInf"
_STR = "InstrmInf/StrtgyInf"
_FIX = "InstrmInf/FxdIncmNonTrdblInf"
_CMON = "FinInstrmAttrCmon"

_DICT_PATHS: dict[str, tuple[str, ...]] = {
	"TCKR_SYMB": (
		f"{_EQ}/TckrSymb",
		f"{_FUT}/TckrSymb",
		f"{_OSF}/TckrSymb",
		f"{_OEQ}/TckrSymb",
		f"{_GLD}/TckrSymb",
		f"{_STR}/TckrSymb",
		f"{_FIX}/TckrSymb",
	),
	"ASST": (f"{_CMON}/Asst",),
	"ASST_DESC": (f"{_CMON}/AsstDesc",),
	"SGMT_NM": (f"{_CMON}/Sgmt",),
	"MKT_NM": (f"{_CMON}/Mkt",),
	"SCTY_CTGY_NM": (
		f"{_EQ}/SctyCtgy",
		f"{_FUT}/SctyCtgy",
		f"{_OEQ}/SctyCtgy",
		f"{_STR}/SctyCtgy",
	),
	"XPRTN_DT": (f"{_STR}/XprtnDt", f"{_FUT}/XprtnDt", f"{_OSF}/XprtnDt"),
	"XPRTN_CD": (f"{_STR}/XprtnCd", f"{_FUT}/XprtnCd", f"{_OSF}/XprtnCd"),
	"TRADG_START_DT": (
		f"{_EQ}/TradgStartDt",
		f"{_FUT}/TradgStartDt",
		f"{_OSF}/TradgStartDt",
		f"{_OEQ}/TradgStartDt",
		f"{_GLD}/TradgStartDt",
		f"{_STR}/TradgStartDt",
		f"{_FIX}/TradgStartDt",
	),
	"TRADG_END_DT": (
		f"{_EQ}/TradgEndDt",
		f"{_FUT}/TradgEndDt",
		f"{_OSF}/TradgEndDt",
		f"{_OEQ}/TradgEndDt",
		f"{_GLD}/TradgEndDt",
		f"{_STR}/TradgEndDt",
		f"{_FIX}/TradgEndDt",
	),
	"BASE_CD": (f"{_FUT}/BaseCd",),
	"CONVS_CRIT_NM": (f"{_FUT}/ConvsCrit",),
	"MTRTY_DT_TRGT_PT": (f"{_FUT}/MtrtyDtTrgtPt",),
	"REQRD_CONVS_IND": (f"{_FUT}/ReqrdConvsInd",),
	"ISIN": (
		f"{_EQ}/ISIN",
		f"{_FUT}/ISIN",
		f"{_OSF}/ISIN",
		f"{_OEQ}/ISIN",
		f"{_GLD}/ISIN",
		f"{_STR}/ISIN",
		f"{_FIX}/ISIN",
	),
	"CFICD": (
		f"{_EQ}/CFICd",
		f"{_FUT}/CFICd",
		f"{_OSF}/CFICd",
		f"{_OEQ}/CFICd",
		f"{_GLD}/CFICd",
		f"{_STR}/CFICd",
	),
	"DLVRY_NTCE_START_DT": (f"{_FUT}/DlvryNtceStartDt",),
	"DLVRY_NTCE_END_DT": (f"{_FUT}/DlvryNtceEndDt",),
	"OPTN_TP": (f"{_OEQ}/OptnTp", f"{_OSF}/OptnTp"),
	"CTRCT_MLTPLR": (
		f"{_FUT}/CtrctMltplr",
		f"{_OSF}/CtrctMltplr",
		f"{_GLD}/CtrctMltplr",
		f"{_STR}/SttlmIndMltplr",
	),
	"ASST_QTN_QTY": (f"{_FUT}/AsstQtnQty", f"{_OSF}/AsstQtnQty", f"{_GLD}/AsstQtnQty"),
	"ALLCN_RND_LOT": (
		f"{_EQ}/AllcnRndLot",
		f"{_FUT}/AllcnRndLot",
		f"{_OSF}/AllcnRndLot",
		f"{_OEQ}/AllcnRndLot",
		f"{_GLD}/AllcnRndLot",
		f"{_STR}/AllcnRndLot",
	),
	"TRADG_CCY": (
		f"{_EQ}/TradgCcy",
		f"{_FUT}/TradgCcy",
		f"{_OSF}/TradgCcy",
		f"{_OEQ}/TradgCcy",
		f"{_GLD}/TradgCcy",
		f"{_STR}/TradgCcy",
	),
	"DLVRY_TP_NM": (f"{_OEQ}/DlvryTp", f"{_FUT}/DlvryTp"),
	"WDRWL_DAYS": (f"{_OSF}/WdrwlDays", f"{_FUT}/WdrwlDays"),
	"WRKG_DAYS": (f"{_OSF}/WrkgDays", f"{_FUT}/WrkgDays"),
	"CLNR_DAYS": (f"{_OSF}/ClnrDays", f"{_FUT}/ClnrDays"),
	"RLVR_BASE_PRIC_NM": (f"{_STR}/RlvrBasePricCd",),
	"OPNG_FUTR_POS_DAY": (f"{_STR}/OpngFutrPosDay",),
	"SD_TP_CD1": (f"{_STR}/StrtgyLegList/LegId/SdTpCd",),
	"UNDRLYG_TCKR_SYMB1": (f"{_STR}/StrtgyLegList/LegId/UndrlygInstrmId",),
	"SD_TP_CD2": (f"{_STR}/StrtgyLegList/LegId/SdTpCd",),
	"UNDRLYG_TCKR_SYMB2": (f"{_STR}/StrtgyLegList/LegId/UndrlygInstrmId",),
	"PURE_GOLD_WGHT": (f"{_GLD}/PureGoldWght", f"{_OSF}/PureGoldWght", f"{_FUT}/PureGoldWght"),
	"EXRC_PRIC": (f"{_OEQ}/ExrcPric", f"{_OSF}/ExrcPric"),
	"OPTN_STYLE": (f"{_OEQ}/OptnStyle", f"{_OSF}/ExrcStyle"),
	"VAL_TP_NM": (f"{_FUT}/ValTpCd", f"{_STR}/ValTpCd"),
	"PRM_UPFRNT_IND": (f"{_OSF}/PrmUpfrntInd", f"{_OEQ}/PrmUpfrntInd"),
	"OPNG_POS_LMT_DT": (f"{_OSF}/OpngPosLmtDt",),
	"DSTRBTN_ID": (f"{_OEQ}/DstrbtnId", f"{_EQ}/DstrbtnId"),
	"PRIC_FCTR": (f"{_EQ}/PricFctr", f"{_OEQ}/PricFctr"),
	"DAYS_TO_STTLM": (f"{_OEQ}/DaysToSttlm", f"{_EQ}/DaysToSttlm"),
	"SRS_TP_NM": (f"{_OEQ}/SrsTp",),
	"PRTCN_FLG": (f"{_OEQ}/PrtcnFlg",),
	"AUTOMTC_EXRC_IND": (f"{_OEQ}/AutomtcExrcInd",),
	"SPCFCTN_CD": (f"{_EQ}/SpcfctnCd",),
	"CRPN_NM": (f"{_EQ}/CrpnNm",),
	"CORP_ACTN_START_DT": (f"{_EQ}/CorpActnStartDt",),
	"CTDY_TRTMNT_TP_NM": (f"{_EQ}/CtdyTrtmntTp",),
	"MKT_CPTLSTN": (f"{_EQ}/MktCptlstn",),
	"CORP_GOVN_LVL_NM": (f"{_EQ}/GovnInd",),
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
