"""Unit tests for exact-decimal typing (``_internal.utils.dtypes.list_decimal_cols``).

Money and any other value whose fractional part carries meaning must survive ingestion
**exactly**. These tests pin that, and pin the deliberate refusal to launder a value whose
precision was already destroyed upstream.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from filings_b3._internal.utils.dtypes import apply_dtypes


def test_text_becomes_an_exact_decimal() -> None:
	"""A numeric string is converted without passing through a binary float.

	``float("1984223115.42")`` is ``1984223115.4200000762939453125``; the assertion below is
	exact equality precisely because that near-miss is the whole failure mode.
	"""
	df_in = pd.DataFrame({"VLM": ["1984223115.42", "0.01"]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["VLM"])

	assert df_out["VLM"].iloc[0] == Decimal("1984223115.42")
	assert df_out["VLM"].iloc[1] == Decimal("0.01")


def test_the_source_scale_is_preserved_not_chosen() -> None:
	"""Trailing zeros survive: the source's own scale is the scale, unrounded and unpadded.

	No precision is *decided* at ingestion. ``1.50`` stays two-decimal and ``1.5000`` stays
	four, because how many decimals a value carries is information the source published —
	quantising it here would discard evidence a warehouse may need.
	"""
	df_in = pd.DataFrame({"PRICE": ["1.50", "1.5000", "2"]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["PRICE"])

	assert str(df_out["PRICE"].iloc[0]) == "1.50"
	assert str(df_out["PRICE"].iloc[1]) == "1.5000"
	assert str(df_out["PRICE"].iloc[2]) == "2"


def test_decimals_sum_exactly() -> None:
	"""Aggregating stays exact — this is what the warehouse does to these columns.

	Summed as floats, ``0.01`` five hundred thousand times drifts off ``5000.00``; the errors
	are individually invisible and collectively a reconciliation failure.
	"""
	df_in = pd.DataFrame({"VLM": ["0.10", "0.20", "0.30"]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["VLM"])

	assert sum(df_out["VLM"]) == Decimal("0.60")
	# Pinned for contrast — the same arithmetic in binary floats misses 0.60 entirely.
	assert 0.10 + 0.20 + 0.30 != 0.60


def test_an_already_decimal_value_passes_through() -> None:
	"""A value parsed with ``parse_float=Decimal`` upstream is kept as-is."""
	df_in = pd.DataFrame({"VLM": [Decimal("1984223115.42")]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["VLM"])

	assert df_out["VLM"].iloc[0] == Decimal("1984223115.42")


def test_integers_convert_exactly() -> None:
	"""An integer source value is exact in both worlds and converts without complaint."""
	df_in = pd.DataFrame({"VLM": [42]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["VLM"])

	assert df_out["VLM"].iloc[0] == Decimal("42")


def test_a_binary_float_is_refused_not_laundered() -> None:
	"""Converting a float would launder a lossy value into a type advertising exactness.

	By the time a ``float`` exists the source's exact value is already gone, so silently
	wrapping it in ``Decimal`` would produce a column that *claims* precision it does not
	have — worse than the float, because nothing downstream would ever question it. The fix
	belongs at the parse boundary, and the error message says so.
	"""
	df_in = pd.DataFrame({"VLM": [1984223115.42]})

	with pytest.raises(ValueError, match="parse_float=Decimal"):
		apply_dtypes(df_in, list_decimal_cols=["VLM"])


@pytest.mark.parametrize("value_missing", [None, "", float("nan")])
def test_missing_values_stay_missing(value_missing: object) -> None:
	"""A blank source field becomes NA, never ``Decimal("0")``.

	``float("nan")`` is in this list deliberately: NaN *is* a float, and pandas uses it as the
	missing marker in any numeric column, so it must be recognised as missing **before** the
	float rejection — otherwise every blank cell in such a column would raise.

	Parameters
	----------
	value_missing : object
		A representation of an absent source value.
	"""
	df_in = pd.DataFrame({"VLM": [value_missing]})

	df_out = apply_dtypes(df_in, list_decimal_cols=["VLM"])

	assert df_out["VLM"].iloc[0] is pd.NA


def test_decimal_column_may_not_also_be_declared_elsewhere() -> None:
	"""A column claimed by two type sets is rejected, as the other sets already are."""
	df_in = pd.DataFrame({"VLM": ["1.50"]})

	with pytest.raises(ValueError, match="more than one target type"):
		apply_dtypes(df_in, {"VLM": "str"}, list_decimal_cols=["VLM"])


def test_a_missing_decimal_column_is_reported() -> None:
	"""Naming a column the frame does not have fails fast, as for the other sets."""
	df_in = pd.DataFrame({"VLM": ["1.50"]})

	with pytest.raises(KeyError, match="ABSENT"):
		apply_dtypes(df_in, list_decimal_cols=["ABSENT"])
