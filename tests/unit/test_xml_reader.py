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
