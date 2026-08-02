"""Pesquisa por Pregão instruments file — ``NtlBdInf`` projection.

One of the per-type views of B3's daily ``IN{yymmdd}.zip`` (BVBG.028.02). The file registers every
instrument of the trading session; each ``<Instrm>`` record nests its type-specific fields under
exactly one ``<InstrmInf>`` sub-block, so this reader keeps the records carrying ``NtlBdInf``
and maps that block's **complete** field list (12 fields, all 12 populated in the reconciled
session): títulos públicos nacionais.

⚠️ **B3's catalog v2.6 is stale for this block.** Dated 24/10/2017, it declares only 9 fields; a
real ``IN260729.zip`` carries 4 more (``BrzlnFdrlGovntBdTpCd``, ``GovntBdRepoGnlInd``,
``GovntBdRepoSpcfcInd``, ``SctyLndgGovntBdInd``) on 100% of rows. The taxonomy sheet lists all 12.
They are mapped — dropping a field the source sends is silent data loss — but the contract does not
require them, since no current document declares their cardinality.

The lifecycle — download, raw-artifact retention, XML flattening, contract, types, provenance —
is inherited from ``_base_instruments_file_reader._BaseInstrumentsFileReader``, which also
supplies the record-level columns common to every instrument type (report date, identification,
common attributes). Only the projection is declared here.
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE_NTL_BD
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_BaseInstrumentsFileReader,
)


# Column to path, relative to the <NtlBdInf> sub-block. Derived from B3's catalog v2.6 (block
# anchor 4.14) where it declares a field, and from the taxonomy sheet for the four fields the 2017
# catalog predates; all 12 confirmed against a real IN file. A monetary column carries its `Ccy`
# attribute as a companion — ISO-20022 puts the unit in an attribute of the amount, so a text-only
# read would lose the currency of every price.
_DICT_PATHS: dict[str, str] = {
	"BASE_DT": "BaseDt",
	"BASE_DT_PRIC": "BaseDtPric",
	"BASE_DT_PRIC_CCY": "BaseDtPric/@Ccy",
	"BRZLN_FDRL_GOVNT_BD_TP_CD": "BrzlnFdrlGovntBdTpCd",
	"GOVNT_BD_REPO_GNL_IND": "GovntBdRepoGnlInd",
	"GOVNT_BD_REPO_SPCFC_IND": "GovntBdRepoSpcfcInd",
	"ISIN": "ISIN",
	"ISSE_DT": "IsseDt",
	"MTRTY_DT": "MtrtyDt",
	"MTRTY_VAL": "MtrtyVal",
	"MTRTY_VAL_CCY": "MtrtyVal/@Ccy",
	"SCTY_CTGY_NM": "SctyCtgy",
	"SCTY_LNDG_GOVNT_BD_IND": "SctyLndgGovntBdInd",
	"SELIC_CD": "SelicCd",
}

# Dates -> datetime.date; money/quantity/multiplier -> exact Decimal (never binary float). Every
# other column stays source text for fidelity, typed downstream.
_LIST_DATE_COLS: tuple[str, ...] = ("BASE_DT", "ISSE_DT", "MTRTY_DT")
_LIST_DECIMAL_COLS: tuple[str, ...] = ("BASE_DT_PRIC", "MTRTY_VAL")


class InstrumentsFileNtlBdReader(_BaseInstrumentsFileReader):
	"""Reader for the ``NtlBdInf`` records of B3's instruments file.

	Covers títulos públicos nacionais. Downloads ``IN{yymmdd}.zip``, keeps the records carrying
	``NtlBdInf``, flattens this block's fields plus the record-level common columns, validates
	against ``INSTRUMENTS_FILE_NTL_BD``, applies explicit types, and stamps provenance. No
	persistence — a distributable library returns the frame.

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

	str_source_key = "instruments_file_ntl_bd"
	cls_contract = INSTRUMENTS_FILE_NTL_BD
	str_sub_block = "NtlBdInf"
	dict_own_paths = _DICT_PATHS
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS
