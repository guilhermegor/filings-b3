"""Tests for the pure drift oracle of ``bin/check_contract_drift.py``.

Only the offline oracle is unit-tested — the network fetch and GitHub issue upsert are exercised in
the weekly job. The oracle compares the columns the instruments reader **maps** against the columns
B3's UP2DATA layout **declares**, in both directions, so a field B3 adds (unmapped) or removes
(silently null) is caught.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
	"check_contract_drift",
	Path(__file__).resolve().parents[2] / "bin" / "check_contract_drift.py",
)
assert _SPEC is not None and _SPEC.loader is not None
drift = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(drift)


def test_no_drift_when_mapped_equals_layout() -> None:
	"""Identical mapped and layout column sets produce no drift messages."""
	set_cols = frozenset({"TCKR_SYMB", "ISIN", "ASST"})

	assert drift.layout_drift("Instruments", set_cols, set_cols) == []


def test_reports_a_mapped_column_missing_from_the_layout() -> None:
	"""A column the reader maps but B3's layout no longer declares is drift (silent null risk)."""
	set_mapped = frozenset({"TCKR_SYMB", "ISIN"})
	set_layout = frozenset({"TCKR_SYMB"})  # ISIN gone from B3

	list_problems = drift.layout_drift("Instruments", set_mapped, set_layout)

	assert len(list_problems) == 1
	assert "ISIN" in list_problems[0]


def test_reports_a_layout_column_the_reader_does_not_map() -> None:
	"""A field B3 added to the layout that the reader does not map is drift (a missing mapping)."""
	set_mapped = frozenset({"TCKR_SYMB"})
	set_layout = frozenset({"TCKR_SYMB", "NEW_FIELD"})  # B3 added a field

	list_problems = drift.layout_drift("Instruments", set_mapped, set_layout)

	assert len(list_problems) == 1
	assert "NEW_FIELD" in list_problems[0]


def test_reports_both_directions_at_once() -> None:
	"""A simultaneous removal and addition yields one message each."""
	list_problems = drift.layout_drift("Instruments", frozenset({"A", "B"}), frozenset({"A", "C"}))

	assert len(list_problems) == 2


def test_mapped_columns_are_the_reader_paths_and_scalars() -> None:
	"""The mapped set is exactly the instruments reader's scalar + path column keys."""
	from filings_b3.search_trading_session import instruments_file as inst

	set_expected = frozenset(inst._DICT_SCALARS) | frozenset(inst._DICT_PATHS)

	assert drift.mapped_columns() == set_expected
