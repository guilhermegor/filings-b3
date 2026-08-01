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
