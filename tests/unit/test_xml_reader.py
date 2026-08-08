"""Tests for the XML ingestion seam — namespaced, nested XML into a typed DataFrame.

The seam turns a BVBG-style ISO-20022 XML (namespaced, one repeating record element per row,
type-specific sub-blocks) into a typed, contract-validated frame — the XML counterpart of
``tabular_reader.read_table``. These tests drive it with a **synthetic** minimal document (two
instrument records of different sub-block types) so the behaviour is pinned without a live file.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from filings_b3._internal.utils.tabular_reader import ContractError, FileContract
from filings_b3._internal.utils.xml_reader import read_xml


_NS = "urn:bvmf.100.02.xsd"

# A minimal namespaced BVBG-shaped document: a file-level report date, then two instrument
# records whose ticker/lot live under DIFFERENT sub-blocks (EqtyInf vs FutrCtrctsInf) — the
# "ou" alternative-path case the consolidated instruments file is built on.
_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{_NS}">
  <BizGrp>
    <RptParams><RptDtAndTm><Dt>2025-01-02</Dt></RptDtAndTm></RptParams>
    <InstrmRcrd>
      <FinInstrmAttrCmon><Asst>PETR</Asst></FinInstrmAttrCmon>
      <InstrmInf><EqtyInf><TckrSymb>PETR4</TckrSymb><AllcnRndLot>100</AllcnRndLot></EqtyInf></InstrmInf>
    </InstrmRcrd>
    <InstrmRcrd>
      <FinInstrmAttrCmon><Asst>DOL</Asst></FinInstrmAttrCmon>
      <InstrmInf><FutrCtrctsInf><TckrSymb>DOLF25</TckrSymb><AllcnRndLot>5</AllcnRndLot>
        <CtrctMltplr>50.00025</CtrctMltplr></FutrCtrctsInf></InstrmInf>
    </InstrmRcrd>
  </BizGrp>
</Document>
"""

_DICT_PATHS = {
	"TICKER_SYMBOL": ("InstrmInf/EqtyInf/TckrSymb", "InstrmInf/FutrCtrctsInf/TckrSymb"),
	"ASSET": ("FinInstrmAttrCmon/Asst",),
	"ALLOCATION_ROUND_LOT": (
		"InstrmInf/EqtyInf/AllcnRndLot",
		"InstrmInf/FutrCtrctsInf/AllcnRndLot",
	),
}
_DICT_SCALARS = {"REPORT_DATE": "RptParams/RptDtAndTm/Dt"}


def _write(path_dir: Path) -> Path:
	path_xml = path_dir / "instruments.xml"
	path_xml.write_text(_XML, encoding="utf-8")
	return path_xml


def test_read_xml_extracts_rows_resolving_alternative_paths_and_scalar(tmp_path: Path) -> None:
	"""Each record is a row; a column takes its first present alternative; scalar broadcasts."""
	cls_contract = FileContract(
		"Test Instruments",
		"test_instruments",
		("REPORT_DATE", "TICKER_SYMBOL", "ASSET", "ALLOCATION_ROUND_LOT"),
		(),
	)

	df_out = read_xml(
		_write(tmp_path),
		"InstrmRcrd",
		_DICT_PATHS,
		{"TICKER_SYMBOL": "str", "ASSET": "str", "ALLOCATION_ROUND_LOT": "int64"},
		cls_contract,
		dict_scalars=_DICT_SCALARS,
		list_date_cols=("REPORT_DATE",),
	)

	assert list(df_out["TICKER_SYMBOL"]) == ["PETR4", "DOLF25"]
	assert list(df_out["ASSET"]) == ["PETR", "DOL"]
	assert list(df_out["ALLOCATION_ROUND_LOT"]) == [100, 5]
	assert list(df_out["REPORT_DATE"]) == [date(2025, 1, 2), date(2025, 1, 2)]


def test_read_xml_raises_contract_error_when_a_required_column_never_resolves(
	tmp_path: Path,
) -> None:
	"""A required column that no record can supply is a ContractError, not a silent NaN column."""
	cls_contract = FileContract(
		"Test Instruments",
		"test_instruments",
		("TICKER_SYMBOL", "ISIN"),  # ISIN has no path here → must fail loudly
		(),
	)

	with pytest.raises(ContractError):
		read_xml(
			_write(tmp_path),
			"InstrmRcrd",
			{"TICKER_SYMBOL": _DICT_PATHS["TICKER_SYMBOL"]},
			{"TICKER_SYMBOL": "str"},
			cls_contract,
		)


def test_read_xml_keeps_decimal_columns_exact(tmp_path: Path) -> None:
	"""A decimal column preserves the source's exact scale — never a lossy binary float."""
	cls_contract = FileContract(
		"Test Instruments",
		"test_instruments",
		("TICKER_SYMBOL", "CONTRACT_MULTIPLIER"),
		(),
	)

	df_out = read_xml(
		_write(tmp_path),
		"InstrmRcrd",
		{
			"TICKER_SYMBOL": _DICT_PATHS["TICKER_SYMBOL"],
			"CONTRACT_MULTIPLIER": ("InstrmInf/FutrCtrctsInf/CtrctMltplr",),
		},
		{"TICKER_SYMBOL": "str"},
		cls_contract,
		list_decimal_cols=("CONTRACT_MULTIPLIER",),
	)

	# The future contract in the second record carries the multiplier; the equity has none.
	assert df_out.loc[1, "CONTRACT_MULTIPLIER"] == Decimal("50.00025")
	# The string form proves the exact scale survived, which a lossy binary float would not.
	assert str(df_out.loc[1, "CONTRACT_MULTIPLIER"]) == "50.00025"


def test_read_xml_star_wildcard_matches_any_sub_block(tmp_path: Path) -> None:
	"""A ``*`` path segment matches any single child — one path covers every sub-block type.

	The two records place ``TckrSymb`` under different sub-blocks (``EqtyInf`` vs
	``FutrCtrctsInf``); ``InstrmInf/*/TckrSymb`` resolves both without enumerating either, which is
	how the instruments reader covers all 17 BVBG sub-block types with one path.
	"""
	cls_contract = FileContract("Test", "test", ("TICKER_SYMBOL",), ())

	df_out = read_xml(
		_write(tmp_path),
		"InstrmRcrd",
		{"TICKER_SYMBOL": ("InstrmInf/*/TckrSymb",)},
		{"TICKER_SYMBOL": "str"},
		cls_contract,
	)

	assert list(df_out["TICKER_SYMBOL"]) == ["PETR4", "DOLF25"]


# A document whose records carry an ISO-20022 amount with its currency as an ATTRIBUTE, plus two
# different sub-block types — the shape the per-type instruments readers project.
_XML_ATTR = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{_NS}">
  <BizGrp>
    <Instrm>
      <RptParams><RptDtAndTm><Dt>2025-01-02</Dt></RptDtAndTm></RptParams>
      <FinInstrmAttrCmon><Asst>PETR</Asst></FinInstrmAttrCmon>
      <InstrmInf><EqtyInf><TckrSymb>PETR4</TckrSymb>
        <MktCptlstn Ccy="BRL">123.45</MktCptlstn></EqtyInf></InstrmInf>
    </Instrm>
    <Instrm>
      <RptParams><RptDtAndTm><Dt>2025-01-02</Dt></RptDtAndTm></RptParams>
      <FinInstrmAttrCmon><Asst>AAPL</Asst></FinInstrmAttrCmon>
      <InstrmInf><ADRInf><TckrSymb>AAPL34</TckrSymb>
        <Ppsn Ccy="USD">2.5</Ppsn></ADRInf></InstrmInf>
    </Instrm>
  </BizGrp>
</Document>
"""


def _write_attr(path_dir: Path) -> Path:
	path_xml = path_dir / "instruments_attr.xml"
	path_xml.write_text(_XML_ATTR, encoding="utf-8")
	return path_xml


def test_read_xml_row_filter_keeps_only_records_carrying_the_block(tmp_path: Path) -> None:
	"""``str_row_filter`` projects one instrument type out of a heterogeneous file.

	The row anchor stays on the full ``<Instrm>`` record, so the per-record report date and
	common attributes — which live *outside* the sub-block — still resolve for the kept rows.
	"""
	cls_contract = FileContract("Test", "test", ("TICKER_SYMBOL", "ASSET"), ())

	df_out = read_xml(
		_write_attr(tmp_path),
		"Instrm",
		{
			"TICKER_SYMBOL": ("InstrmInf/ADRInf/TckrSymb",),
			"ASSET": ("FinInstrmAttrCmon/Asst",),
			"REPORT_DATE": ("RptParams/RptDtAndTm/Dt",),
		},
		{"TICKER_SYMBOL": "str", "ASSET": "str"},
		cls_contract,
		list_date_cols=("REPORT_DATE",),
		str_row_filter="InstrmInf/ADRInf",
	)

	assert list(df_out["TICKER_SYMBOL"]) == ["AAPL34"]
	assert list(df_out["ASSET"]) == ["AAPL"]
	# Reached from the record, not the sub-block — the filter did not narrow the row anchor.
	assert list(df_out["REPORT_DATE"]) == [date(2025, 1, 2)]


def test_read_xml_row_filter_applies_before_contract_validation(tmp_path: Path) -> None:
	"""Filtering precedes validation, keeping other types out of this dataset's frame.

	Without the filter the equity record would leave ``PROPORTION`` null and a contract
	requiring it would still pass (presence, not nullity) — but the frame would carry a row
	that does not belong to this dataset at all.
	"""
	cls_contract = FileContract("Test", "test", ("PROPORTION",), ())

	df_out = read_xml(
		_write_attr(tmp_path),
		"Instrm",
		{"PROPORTION": ("InstrmInf/ADRInf/Ppsn",)},
		{},
		cls_contract,
		list_decimal_cols=("PROPORTION",),
		str_row_filter="InstrmInf/ADRInf",
	)

	assert len(df_out) == 1
	assert df_out.loc[0, "PROPORTION"] == Decimal("2.5")
	assert not df_out["PROPORTION"].isna().any()


def test_read_xml_reads_an_attribute_with_an_at_segment(tmp_path: Path) -> None:
	"""A trailing ``@name`` segment reads an attribute — ISO-20022 puts an amount's currency there.

	Without this the currency of every monetary column would be unrecoverable from the frame.
	"""
	cls_contract = FileContract("Test", "test", ("PROPORTION", "PROPORTION_CCY"), ())

	df_out = read_xml(
		_write_attr(tmp_path),
		"Instrm",
		{
			"PROPORTION": ("InstrmInf/ADRInf/Ppsn",),
			"PROPORTION_CCY": ("InstrmInf/ADRInf/Ppsn/@Ccy",),
		},
		{"PROPORTION_CCY": "str"},
		cls_contract,
		list_decimal_cols=("PROPORTION",),
		str_row_filter="InstrmInf/ADRInf",
	)

	assert df_out.loc[0, "PROPORTION"] == Decimal("2.5")
	assert df_out.loc[0, "PROPORTION_CCY"] == "USD"


def test_read_xml_attribute_is_none_when_absent(tmp_path: Path) -> None:
	"""An ``@name`` segment naming an attribute the element does not carry yields ``None``."""
	cls_contract = FileContract("Test", "test", (), ())

	df_out = read_xml(
		_write_attr(tmp_path),
		"Instrm",
		{"MISSING": ("InstrmInf/ADRInf/Ppsn/@Nope",)},
		{"MISSING": "str"},
		cls_contract,
		str_row_filter="InstrmInf/ADRInf",
	)

	assert df_out["MISSING"].isna().all()


# Two records: a strategy carrying TWO legs with DIFFERENT values (the case a first-match-wins
# reader silently collapses), and the instrument one of those legs references by id.
_XML_LEGS = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{_NS}">
  <BizGrp>
    <Instrm>
      <FinInstrmId><OthrId><Id>200000363903</Id></OthrId></FinInstrmId>
      <InstrmInf><FutrCtrctsInf><TckrSymb>DDIF38</TckrSymb></FutrCtrctsInf></InstrmInf>
    </Instrm>
    <Instrm>
      <FinInstrmId><OthrId><Id>999</Id></OthrId></FinInstrmId>
      <InstrmInf><StrtgyInf><TckrSymb>DIFF30F35</TckrSymb>
        <StrtgyLegList><LegId>1</LegId><SdTpCd>BUYI</SdTpCd>
          <UndrlygInstrmId><OthrId><Id>200000363903</Id></OthrId></UndrlygInstrmId>
        </StrtgyLegList>
        <StrtgyLegList><LegId>2</LegId><SdTpCd>SELL</SdTpCd>
          <UndrlygInstrmId><OthrId><Id>320100</Id></OthrId></UndrlygInstrmId>
        </StrtgyLegList>
      </StrtgyInf></InstrmInf>
    </Instrm>
  </BizGrp>
</Document>
"""


def _write_legs(path_dir: Path) -> Path:
	path_xml = path_dir / "legs.xml"
	path_xml.write_text(_XML_LEGS, encoding="utf-8")
	return path_xml


def test_read_xml_indexed_segment_addresses_the_nth_repeat(tmp_path: Path) -> None:
	"""``Tag[n]`` reaches the n-th sibling repeat — legs 1 and 2 must not collapse into one.

	Regression for the released bug where both legs mapped to the same path: first-match-wins gave
	leg 1's value to both columns, so a two-legged strategy read as if both sides were identical.
	"""
	cls_contract = FileContract("Test", "test", ("SD_TP_CD1", "SD_TP_CD2"), ())

	df_out = read_xml(
		_write_legs(tmp_path),
		"Instrm",
		{
			"SD_TP_CD1": ("InstrmInf/StrtgyInf/StrtgyLegList[1]/SdTpCd",),
			"SD_TP_CD2": ("InstrmInf/StrtgyInf/StrtgyLegList[2]/SdTpCd",),
		},
		{"SD_TP_CD1": "str", "SD_TP_CD2": "str"},
		cls_contract,
		str_row_filter="InstrmInf/StrtgyInf",
	)

	assert df_out.loc[0, "SD_TP_CD1"] == "BUYI"
	assert df_out.loc[0, "SD_TP_CD2"] == "SELL"
	assert df_out.loc[0, "SD_TP_CD1"] != df_out.loc[0, "SD_TP_CD2"]


def test_read_xml_indexed_segment_is_none_past_the_last_repeat(tmp_path: Path) -> None:
	"""Asking for a repeat that does not exist yields ``None``, never the last one available."""
	cls_contract = FileContract("Test", "test", (), ())

	df_out = read_xml(
		_write_legs(tmp_path),
		"Instrm",
		{"LEG3": ("InstrmInf/StrtgyInf/StrtgyLegList[3]/SdTpCd",)},
		{"LEG3": "str"},
		cls_contract,
		str_row_filter="InstrmInf/StrtgyInf",
	)

	assert df_out["LEG3"].isna().all()


def test_read_xml_self_join_resolves_a_reference_to_another_record(tmp_path: Path) -> None:
	"""``dict_joins`` translates an opaque id into a value carried by the referenced record.

	A strategy leg names its underlying only by a proprietary id; the ticker lives on that other
	instrument's record. Without the join the column can only hold the meaningless id.
	"""
	cls_contract = FileContract("Test", "test", ("UNDRLYG_TCKR_SYMB1",), ())

	df_out = read_xml(
		_write_legs(tmp_path),
		"Instrm",
		{"TCKR_SYMB": ("InstrmInf/*/TckrSymb",)},
		{"TCKR_SYMB": "str", "UNDRLYG_TCKR_SYMB1": "str", "UNDRLYG_TCKR_SYMB2": "str"},
		cls_contract,
		str_row_filter="InstrmInf/StrtgyInf",
		dict_joins={
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
		},
	)

	# Leg 1 points at a record present in the file, so the id becomes that record's ticker. The
	# lookup spans every record, including the one the row filter excluded from the output.
	assert df_out.loc[0, "UNDRLYG_TCKR_SYMB1"] == "DDIF38"
	# Leg 2 points at an instrument absent from this file — unresolved, never a stale carry-over.
	assert pd.isna(df_out.loc[0, "UNDRLYG_TCKR_SYMB2"])


# The same document plus the header block a regulatory envelope uses to declare how many records
# it carries. `{count}` is substituted so a test can make the declaration lie.
_XML_COUNTED = _XML.replace(
	"<BizGrp>",
	"<BizFileHdr><BizGrpDtls><TtlNbOfMsg>{count}</TtlNbOfMsg></BizGrpDtls></BizFileHdr><BizGrp>",
)
_COUNT_PATH = "BizGrpDtls/TtlNbOfMsg"


def _write_counted(path_dir: Path, str_declared: str) -> Path:
	path_xml = path_dir / "counted.xml"
	path_xml.write_text(_XML_COUNTED.format(count=str_declared), encoding="utf-8")
	return path_xml


def _read_counted(path_xml: Path, **kwargs: object) -> pd.DataFrame:
	"""Read the counted document with the seam's count check on."""
	return read_xml(
		path_xml,
		"InstrmRcrd",
		_DICT_PATHS,
		{"TICKER_SYMBOL": "str", "ASSET": "str", "ALLOCATION_ROUND_LOT": "int64"},
		FileContract("Test Instruments", "test_instruments", ("TICKER_SYMBOL",), ()),
		str_declared_count_path=_COUNT_PATH,
		**kwargs,
	)


def test_read_xml_accepts_a_file_whose_declared_count_matches(tmp_path: Path) -> None:
	"""A file that declares exactly what it carries reads normally."""
	df_out = _read_counted(_write_counted(tmp_path, "2"))

	assert list(df_out["TICKER_SYMBOL"]) == ["PETR4", "DOLF25"]


def test_read_xml_raises_when_the_file_carries_fewer_records_than_it_declares(
	tmp_path: Path,
) -> None:
	"""A truncated download is caught by the count the file declares about itself.

	This is the failure mode the check exists for and the only one nothing else sees: every row
	that arrived is individually valid, the XML is well-formed up to the cut, and the contract
	and dtype gates both pass on a frame that is simply missing its tail.
	"""
	with pytest.raises(ValueError, match="declares 3 records but holds 2"):
		_read_counted(_write_counted(tmp_path, "3"))


def test_read_xml_counts_records_before_the_row_filter(tmp_path: Path) -> None:
	"""The count is compared against every record present, not the ones the projection keeps.

	Without this, the check would be usable only by a reader that keeps the whole file: each of
	the seventeen per-sub-block readers of one heterogeneous source would fail by construction,
	its handful of rows never matching the file's own total.
	"""
	df_out = _read_counted(_write_counted(tmp_path, "2"), str_row_filter="InstrmInf/EqtyInf")

	assert list(df_out["TICKER_SYMBOL"]) == ["PETR4"]


def test_read_xml_raises_when_the_declared_count_path_resolves_to_nothing(
	tmp_path: Path,
) -> None:
	"""Asking for a count the file does not declare fails loudly rather than skipping the check."""
	with pytest.raises(ValueError, match="no record count"):
		_read_counted(_write(tmp_path))


def test_read_xml_verifies_no_count_when_no_path_is_given(tmp_path: Path) -> None:
	"""The check is opt-in: a caller that passes no path gets no verification, wrong count or not.

	The seam presumes such a declaration *may* exist, never that it does — which is what keeps it
	usable by a format that declares nothing, without a branch per source.
	"""
	df_out = read_xml(
		_write_counted(tmp_path, "999"),
		"InstrmRcrd",
		_DICT_PATHS,
		{"TICKER_SYMBOL": "str", "ASSET": "str", "ALLOCATION_ROUND_LOT": "int64"},
		FileContract("Test Instruments", "test_instruments", ("TICKER_SYMBOL",), ()),
	)

	assert len(df_out) == 2
