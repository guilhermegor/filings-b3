"""Unit tests for the text-normalisation helpers.

Focus on ``pascal_to_upper_snake``: the case-boundary and acronym edge cases matter now that
it is a shared helper the BDI base (and any future JSON section) maps every column name through.
"""

from __future__ import annotations

import pytest

from filings_b3._internal.utils.text import pascal_to_upper_snake


@pytest.mark.parametrize(
	("str_in", "str_out"),
	[
		("TckrSymb", "TCKR_SYMB"),
		("VlmTradedDay", "VLM_TRADED_DAY"),
		("StockBalance", "STOCK_BALANCE"),
		("AvgPric", "AVG_PRIC"),
		("RptDt", "RPT_DT"),
		("ISIN", "ISIN"),  # all-caps acronym: no internal boundary, stays intact
		("TCKR_SYMB", "TCKR_SYMB"),  # already upper/snake: idempotent
		("Field1Name", "FIELD1_NAME"),  # digit -> upper boundary splits
	],
)
def test_pascal_to_upper_snake(str_in: str, str_out: str) -> None:
	"""PascalCase/camelCase names snake-case correctly, acronyms and digits included."""
	assert pascal_to_upper_snake(str_in) == str_out
