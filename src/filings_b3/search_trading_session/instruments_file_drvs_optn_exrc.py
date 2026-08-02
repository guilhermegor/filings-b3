"""Pesquisa por Pregão instruments file — ``DrvsOptnExrcInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying
``DrvsOptnExrcInf`` and maps that block's **complete** field list (14 fields per B3's catalog v2.6,
all 14 populated in the reconciled session): exercício de opções sobre derivativos.

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

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_DRVS_OPTN_EXRC
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <DrvsOptnExrcInf> sub-block. Derived from B3's catalog v2.6
# (block anchor 4.7), cross-checked against the taxonomy sheet and a real IN file. The catalog
# renders the reference tag clipped to `DerivOptnExrcInst` — its PDF columns cut long tags; the
# real file spells it `DerivOptnExrcInstrmId`, which is what resolves.
_DICT_PATHS: dict[str, str] = {
	"ASST_STTLM_IND": "AsstSttlmInd/OthrId/Id",
	"ASST_STTLM_IND_TP": "AsstSttlmInd/OthrId/Tp/Prtry",
	"ASST_STTLM_IND_MKT_IDR_CD": "AsstSttlmInd/PlcOfListg/MktIdrCd",
	"CLNR_DAYS": "ClnrDays",
	"DERIV_OPTN_EXRC_INSTRM_ID": "DerivOptnExrcInstrmId/OthrId/Id",
	"DERIV_OPTN_EXRC_INSTRM_ID_TP": "DerivOptnExrcInstrmId/OthrId/Tp/Prtry",
	"DERIV_OPTN_EXRC_INSTRM_ID_MKT_IDR_CD": "DerivOptnExrcInstrmId/PlcOfListg/MktIdrCd",
	"ISIN": "ISIN",
	"OPTN_DLVRY_TP_NM": "OptnDlvryTp",
	"SCTY_CTGY_NM": "SctyCtgy",
	"STTLM_IND_MLTPLR": "SttlmIndMltplr",
	"TCKR_SYMB": "TckrSymb",
	"WDRWL_DAYS": "WdrwlDays",
	"WRKG_DAYS": "WrkgDays",
}

# Dates -> datetime.date; money/quantity/multiplier -> exact Decimal (never binary float). Every
# other column stays source text for fidelity, typed downstream. This block declares neither:
# SttlmIndMltplr is an integer count of settlement units, not a decimal multiplier.
_LIST_DATE_COLS: tuple[str, ...] = ()
_LIST_DECIMAL_COLS: tuple[str, ...] = ()


class InstrumentsFileDrvsOptnExrcReader(_BaseInstrumentsFileReader):
	"""Reader for the ``DrvsOptnExrcInf`` records of B3's instruments file.

	Covers exercício de opções sobre derivativos. Downloads ``IN{yymmdd}.zip``, keeps the records
	carrying ``DrvsOptnExrcInf``, flattens this block's fields plus the record-level common
	columns, validates against ``INSTRUMENTS_FILE_DRVS_OPTN_EXRC``, applies explicit types, and
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

	str_source_key = "instruments_file_drvs_optn_exrc"
	cls_contract = INSTRUMENTS_FILE_DRVS_OPTN_EXRC
	str_sub_block = "DrvsOptnExrcInf"
	dict_own_paths = _DICT_PATHS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
