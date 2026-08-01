"""Tests for the per-sub-block instruments readers and the base they share.

B3's ``IN{yymmdd}.zip`` is one download read nine ways: the consolidated reader spans every
instrument type on B3's published 52-column UP2DATA layout, and eight per-type readers each
project one ``InstrmInf`` sub-block with that block's complete field list. These tests pin the
family's invariants — every reader is a distinct projection of the same file, every mapped column
is explicitly typed, and the consolidated reader's drift-gated column set stays exactly as
published — without touching the network.

The readers' actual column mappings are reconciled against a **real** IN file (issue #143's
fixture); that reconciliation is recorded in the branch ledger, not repeated here, because a
660 MB fixture cannot live in the test suite.
"""

from __future__ import annotations

from datetime import date

import pytest

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
from filings_b3.search_trading_session import (
	InstrumentsFileAdrReader,
	InstrumentsFileBtcReader,
	InstrumentsFileEqtyFwdReader,
	InstrumentsFileEqtyReader,
	InstrumentsFileExrcEqtsReader,
	InstrumentsFileFxdIncmReader,
	InstrumentsFileOptnOnEqtsReader,
	InstrumentsFileOptnOnSpotAndFuturesReader,
	InstrumentsFileReader,
)
from filings_b3.search_trading_session._base_instruments_file_reader import (
	_COMMON_PATHS,
	_BaseInstrumentsFileReader,
)


_DATE_REF = date(2026, 7, 29)

# The eight per-type readers and the sub-block each projects. The sub-block names are BVBG.028
# tags confirmed present in a real IN file.
_SUB_BLOCK_READERS: tuple[tuple[type[_BaseInstrumentsFileReader], str, str], ...] = (
	(InstrumentsFileAdrReader, "ADRInf", "instruments_file_adr"),
	(InstrumentsFileBtcReader, "BTCInf", "instruments_file_btc"),
	(InstrumentsFileEqtyReader, "EqtyInf", "instruments_file_eqty"),
	(InstrumentsFileEqtyFwdReader, "EqtyFwdInf", "instruments_file_eqty_fwd"),
	(InstrumentsFileExrcEqtsReader, "ExrcEqtsInf", "instruments_file_exrc_eqts"),
	(InstrumentsFileFxdIncmReader, "FxdIncmInf", "instruments_file_fxd_incm"),
	(InstrumentsFileOptnOnEqtsReader, "OptnOnEqtsInf", "instruments_file_optn_on_eqts"),
	(
		InstrumentsFileOptnOnSpotAndFuturesReader,
		"OptnOnSpotAndFutrsInf",
		"instruments_file_optn_on_spot_and_futures",
	),
)

_IDS = [cls_reader.__name__ for cls_reader, _, _ in _SUB_BLOCK_READERS]


@pytest.mark.parametrize(("cls_reader", "str_block", "str_key"), _SUB_BLOCK_READERS, ids=_IDS)
def test_every_reader_declares_its_own_sub_block_and_source_key(
	cls_reader: type[_BaseInstrumentsFileReader], str_block: str, str_key: str
) -> None:
	"""Each per-type reader names the sub-block it projects and its own provenance source key."""
	cls_r = cls_reader(_DATE_REF)

	assert cls_r.str_sub_block == str_block
	assert cls_r.str_source_key == str_key
	assert cls_r.cls_contract.str_source_key == str_key


@pytest.mark.parametrize(("cls_reader", "str_block", "str_key"), _SUB_BLOCK_READERS, ids=_IDS)
def test_every_reader_shares_the_one_instruments_file_url(
	cls_reader: type[_BaseInstrumentsFileReader], str_block: str, str_key: str
) -> None:
	"""The whole family reads one download — the same ``IN{yymmdd}.zip`` for the session."""
	assert cls_reader(_DATE_REF).build_url() == InstrumentsFileReader(_DATE_REF).build_url()
	assert "IN260729.zip" in cls_reader(_DATE_REF).build_url()


@pytest.mark.parametrize(("cls_reader", "str_block", "str_key"), _SUB_BLOCK_READERS, ids=_IDS)
def test_sub_block_paths_are_prefixed_and_common_columns_inherited(
	cls_reader: type[_BaseInstrumentsFileReader], str_block: str, str_key: str
) -> None:
	"""Own fields resolve beneath the sub-block; the record-level common columns come free.

	The common block is what makes a per-type frame joinable: the report date and instrument
	identification live *outside* ``InstrmInf``, so a reader anchored on the sub-block alone
	could never reach them.
	"""
	cls_r = cls_reader(_DATE_REF)
	dict_paths = cls_r.dict_paths

	for str_col in _COMMON_PATHS:
		assert str_col in dict_paths, f"{str_col} missing from {cls_reader.__name__}"

	for str_col in cls_r.dict_own_paths:
		(str_path,) = dict_paths[str_col]
		assert str_path.startswith(f"InstrmInf/{str_block}/")


@pytest.mark.parametrize(("cls_reader", "str_block", "str_key"), _SUB_BLOCK_READERS, ids=_IDS)
def test_every_mapped_column_is_explicitly_typed(
	cls_reader: type[_BaseInstrumentsFileReader], str_block: str, str_key: str
) -> None:
	"""No column reaches a datalake on pandas' inference — dates, decimals, then text.

	The three sets must partition the mapped columns exactly: a column missing from all of them
	would be inferred, and one in two of them would be coerced twice.
	"""
	cls_r = cls_reader(_DATE_REF)
	set_cols = set(cls_r.dict_paths)
	set_dates = set(cls_r.list_all_date_cols)
	set_decimals = set(cls_r.list_decimal_cols)
	set_text = set(cls_r.dict_dtypes)

	assert set_dates <= set_cols
	assert set_decimals <= set_cols
	assert not (set_dates & set_decimals)
	assert not (set_text & (set_dates | set_decimals))
	assert set_text | set_dates | set_decimals == set_cols


@pytest.mark.parametrize(("cls_reader", "str_block", "str_key"), _SUB_BLOCK_READERS, ids=_IDS)
def test_contract_required_columns_are_all_mapped(
	cls_reader: type[_BaseInstrumentsFileReader], str_block: str, str_key: str
) -> None:
	"""A contract cannot require a column the reader never maps — that would fail every read."""
	cls_r = cls_reader(_DATE_REF)

	set_unmapped = set(cls_r.cls_contract.tuple_required) - set(cls_r.dict_paths)

	assert not set_unmapped, f"{cls_reader.__name__} requires unmapped {sorted(set_unmapped)}"


def test_each_reader_projects_a_distinct_sub_block() -> None:
	"""Two readers claiming one sub-block would be the same dataset published twice."""
	list_blocks = [str_block for _, str_block, _ in _SUB_BLOCK_READERS]

	assert len(set(list_blocks)) == len(list_blocks)


def test_currency_attribute_columns_accompany_their_amount() -> None:
	"""A monetary column mapped from an ISO-20022 amount carries its ``Ccy`` attribute.

	B3 puts the currency in an attribute of the amount element, so without the companion column
	the unit of every price is lost — the frame would say ``2.5`` with no way back to ``USD``.
	"""
	cls_r = InstrumentsFileAdrReader(_DATE_REF)

	assert cls_r.dict_own_paths["PPSN_CCY"] == "Ppsn/@Ccy"
	assert "PPSN" in cls_r.list_decimal_cols
	assert cls_r.dict_dtypes["PPSN_CCY"] == "str"


def test_consolidated_reader_keeps_its_drift_gated_layout() -> None:
	"""The consolidated reader stays pinned to B3's published 52-column UP2DATA layout.

	It takes none of the base's common-block columns: the contract-drift oracle compares this
	reader's mapped set against B3's declared layout, so an extra column would read as drift.
	"""
	cls_r = InstrumentsFileReader(_DATE_REF)

	cls_r = InstrumentsFileReader(_DATE_REF)

	assert cls_r.str_sub_block is None
	assert cls_r.dict_common_paths == {}
	# 52 source columns total, however each one is resolved — two of them are self-joins.
	assert len(cls_r.dict_paths) + len(cls_r.dict_joins) == 52
	assert cls_r.cls_contract is INSTRUMENTS_FILE
	assert "INSTRM_DESC" not in cls_r.dict_paths


def test_consolidated_reader_resolves_both_strategy_legs_distinctly() -> None:
	"""The two strategy legs must resolve independently, each to its own leg.

	Regression for the released bug (#149): both legs shared one path, which never resolved at all
	(``SdTpCd`` is a *sibling* of ``LegId``, not a child) — so all four leg columns were null on
	100% of strategy records. Even corrected, a shared path would have duplicated leg 1.
	"""
	cls_r = InstrumentsFileReader(_DATE_REF)

	(str_leg1,) = cls_r.dict_paths["SD_TP_CD1"]
	(str_leg2,) = cls_r.dict_paths["SD_TP_CD2"]
	assert str_leg1 != str_leg2, "both legs share a path — leg 2 would duplicate leg 1"
	assert "StrtgyLegList[1]" in str_leg1
	assert "StrtgyLegList[2]" in str_leg2
	# LegId is a sibling of the value, never its parent — the shape that caused the null columns.
	assert "LegId/" not in str_leg1

	str_fk1, str_pk, str_value = cls_r.dict_joins["UNDRLYG_TCKR_SYMB1"]
	str_fk2, _, _ = cls_r.dict_joins["UNDRLYG_TCKR_SYMB2"]
	assert str_fk1 != str_fk2
	# The join brings back a ticker, not the opaque id the leg actually references.
	assert str_value.endswith("TckrSymb")
	assert str_pk == "FinInstrmId/OthrId/Id"


def test_base_rejects_a_reader_missing_a_required_attribute() -> None:
	"""A reader that forgets its contract fails at import, not deep inside a network read."""
	with pytest.raises(NotImplementedError, match="cls_contract"):

		class _Incomplete(_BaseInstrumentsFileReader):
			str_source_key = "oops"
