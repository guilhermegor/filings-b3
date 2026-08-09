"""Tests for ``bin/check_contract_drift.py`` — the pure oracle and the reporting decisions.

The oracle compares the columns the instruments reader **maps** against the columns B3's UP2DATA
layout **declares**, in both directions, so a field B3 adds (unmapped) or removes (silently null)
is caught.

The reporting half is covered here too, offline. It was **not** covered before, and three defects
lived in it undetected until a review of the sibling BDI-catalog checker (#222) named them: an
outage printed "no layout drift detected", a closed tracker was duplicated every week instead of
reopened, and a GitHub failure reddened a job whose whole contract is to report by opening an
issue. "Exercised in the weekly job" is not coverage — nobody reads a green scheduled run.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


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


def test_mapped_columns_are_the_consolidated_reader_paths_and_joins() -> None:
	"""The mapped set is the consolidated reader's path columns **plus** its self-joined ones.

	A column filled by resolving a reference to another record (a strategy leg's underlying) is
	just as mapped as one resolved by a direct path — and B3's layout declares both the same way,
	so omitting the joins would report them as drift against a layout that does list them.
	"""
	from filings_b3.search_trading_session import instruments_file as inst

	frozenset_attr = frozenset(
		str_col
		for str_col, tuple_paths in inst._DICT_PATHS.items()
		if any("/@" in str_path for str_path in tuple_paths)
	)
	assert (
		drift.mapped_columns()
		== (frozenset(inst._DICT_PATHS) | frozenset(inst._DICT_JOINS)) - frozenset_attr
	)
	assert frozenset(inst._DICT_JOINS) <= drift.mapped_columns()


def test_mapped_columns_exclude_attribute_derived_columns() -> None:
	"""An XML-attribute column is read but never compared against B3's flat layout (#147).

	``EXRC_PRIC_CCY`` comes from ``ExrcPric/@Ccy`` — an *attribute* of a value the UP2DATA layout
	already declares as a field. The layout enumerates flat fields, so it can never list it;
	counting it would report drift the instant the reader starts reading more of the source than
	the flat layout can express. The rule keys off the ``/@`` in the path, so a future attribute
	column is excluded automatically rather than by name.
	"""
	from filings_b3.search_trading_session import instruments_file as inst

	assert "EXRC_PRIC_CCY" in inst._DICT_PATHS, "fixture drifted — the attribute column is gone"
	assert not (drift.mapped_columns() & frozenset({"EXRC_PRIC_CCY", "MKT_CPTLSTN_CCY"}))
	# The value columns themselves stay in the comparison — only the attributes are excluded.
	assert frozenset({"EXRC_PRIC", "MKT_CPTLSTN"}) <= drift.mapped_columns()


def test_mapped_columns_exclude_the_per_type_readers() -> None:
	"""A per-type reader's own columns never leak into the UP2DATA-pinned drift comparison.

	The oracle compares against B3's consolidated UP2DATA layout, which does not describe the
	``InstrmInf`` sub-blocks — so a sub-block column appearing here would be reported as drift
	against a layout that was never meant to declare it.
	"""
	from filings_b3.search_trading_session import instruments_file_adr as adr

	set_adr_only = frozenset(adr._DICT_PATHS) - frozenset({"TCKR_SYMB", "ISIN", "CFICD"})

	assert not (drift.mapped_columns() & frozenset({"CUSIP", "PRGM_LVL", "PPSN_CCY"}))
	assert "PPSN_CCY" in set_adr_only


def test_an_unreadable_layout_is_a_skip_not_an_absence_of_drift(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	"""A B3 outage reports SKIPPED, never "no layout drift detected".

	``None`` and ``[]`` say different things — "I never compared" and "I compared and found
	nothing". Collapsing them printed a green line asserting a comparison that never happened,
	which is precisely the blindness this job exists to remove.
	"""
	monkeypatch.setattr(drift, "fetch_layout_columns", lambda _timeout=60: None)

	assert drift.collect_drift() is None

	monkeypatch.setattr(drift, "collect_drift", lambda: None)
	assert drift.main() == 0
	assert "SKIPPED" in capsys.readouterr().out


def test_a_closed_tracker_is_found_so_it_can_be_reopened() -> None:
	"""A closed marked issue is still THE tracker — otherwise each run opens a weekly duplicate.

	The issue body this job writes promises "O job a reabre se a deriva persistir". Searching open
	issues only made that promise false: closing the tracker while the drift persisted turned the
	next run into a brand-new issue.
	"""
	dict_found = drift.find_drift_issue(
		[{"number": 7, "state": "closed", "body": "<!-- contract-drift-bot -->\nold"}]
	)

	assert dict_found is not None
	assert dict_found["number"] == 7


def test_the_drift_issue_is_told_apart_from_the_catalog_issue() -> None:
	"""The marker, not the shared label, identifies this job's issue.

	Both weekly jobs carry the ``contract-drift`` label, so matching on the label alone would make
	each one hijack and overwrite the other's tracker.
	"""
	list_issues = [
		{"number": 1, "state": "open", "body": "<!-- bdi-catalog-bot -->\ncatalog"},
		{"number": 2, "state": "open", "body": "<!-- contract-drift-bot -->\nlayout"},
	]

	assert drift.find_drift_issue(list_issues)["number"] == 2
	assert drift.find_drift_issue([list_issues[0]]) is None


def test_a_github_failure_does_not_redden_the_job(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	"""Drift still exits 0 when GitHub cannot be reached — it is already on stdout.

	The job reports by opening an issue rather than by failing, so a hiccup talking to GitHub must
	not turn a scheduled run red.
	"""

	def _boom(str_api: str, list_problems: list[str]) -> None:  # noqa: ARG001
		raise OSError("GitHub is down")

	monkeypatch.setattr(drift, "collect_drift", lambda: ["derivou"])
	monkeypatch.setattr(drift, "upsert_issue", _boom)
	monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
	monkeypatch.setenv("GITHUB_TOKEN", "x")

	assert drift.main() == 0
	assert "could not report to GitHub" in capsys.readouterr().err


def test_a_missing_token_reports_to_stdout_instead_of_crashing(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	"""Without a token the run reports locally rather than raising ``KeyError`` from ``_api``.

	The guard used to check only ``GITHUB_REPOSITORY`` while ``_api`` reads ``GITHUB_TOKEN``
	directly, so a repo variable without a token crashed the job on an unhandled ``KeyError``.
	"""
	monkeypatch.setattr(drift, "collect_drift", lambda: ["derivou"])
	monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
	monkeypatch.delenv("GITHUB_TOKEN", raising=False)

	assert drift.main() == 0
	assert "reporting to stdout only" in capsys.readouterr().err
