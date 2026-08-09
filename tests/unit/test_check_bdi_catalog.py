"""Unit tests for the BDI catalog check's pure oracle (``bin/check_bdi_catalog.py``).

Only the **offline** half is exercised here: the diff between B3's published table index and
``bin/bdi_catalog.py``, plus the payload extraction. The network half runs weekly in CI and is
deliberately unreachable from the suite (``tests/conftest.py`` blocks the network).

The should-fail cases are the point. A coverage gate that only ever sees agreement prints green
exactly like one that has stopped comparing — which is the failure mode this whole check exists
to prevent, since the audit in issue #186 found 32 tables missing precisely because nothing was
looking.
"""

from __future__ import annotations

import pathlib
import sys

import pytest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "bin"))

from bdi_catalog import BDI_TABLES, STATE_IMPLEMENTED, STATE_ISSUE  # noqa: E402
from check_bdi_catalog import (  # noqa: E402
	build_issue_body,
	catalog_divergence,
	find_open_catalog_issue,
	published_tables,
)


def test_no_divergence_when_both_sides_agree() -> None:
	"""Identical sets produce no message — the quiet, expected weekly outcome."""
	assert catalog_divergence(frozenset({"A", "B"}), frozenset({"A", "B"})) == []


def test_a_table_b3_publishes_and_the_catalog_omits_is_reported() -> None:
	"""A newly published table is flagged — this is the gap the audit found 32 of.

	Nothing else in the repository can see it: no reader breaks, no test fails, the backlog just
	quietly does not mention the dataset.
	"""
	list_out = catalog_divergence(frozenset({"A", "NovaTabela"}), frozenset({"A"}))

	assert len(list_out) == 1
	assert "NovaTabela" in list_out[0]
	assert "ausente" in list_out[0]


def test_a_catalogued_table_b3_dropped_is_reported() -> None:
	"""The reverse direction is a real signal too: a retired table, or a reader now reading air."""
	list_out = catalog_divergence(frozenset({"A"}), frozenset({"A", "Aposentada"}))

	assert len(list_out) == 1
	assert "Aposentada" in list_out[0]


def test_both_directions_are_reported_together_and_sorted() -> None:
	"""Every divergence is reported at once, in a stable order, so the issue body stays quiet."""
	list_out = catalog_divergence(frozenset({"Zeta", "Alfa"}), frozenset({"Beta", "Alfa"}))

	assert len(list_out) == 2
	assert "Zeta" in list_out[0]  # additions first, then removals
	assert "Beta" in list_out[1]


def test_published_tables_flattens_every_classification() -> None:
	"""Table names are collected across all classifications, not just the first."""
	list_payload = [
		{"name": "Renda fixa", "tables": {"DIover": {}, "Trade": {}}},
		{"name": "COE", "tables": {"COEInventory": {}}},
	]

	assert published_tables(list_payload) == frozenset({"DIover", "Trade", "COEInventory"})


def test_published_tables_raises_on_an_empty_index() -> None:
	"""An index listing nothing fails loudly instead of reporting all 69 entries as retired.

	An empty payload cannot be told apart from a total divergence, and the caller treats the raise
	as "skip this week" — silence beats 69 false alarms.
	"""
	with pytest.raises(ValueError, match="no table at all"):
		published_tables([{"name": "Vazia", "tables": {}}])


def test_the_issue_body_carries_the_marker_that_finds_it_again() -> None:
	"""The body embeds this job's marker — how the next run updates instead of duplicating."""
	str_body = build_issue_body(["algo divergiu"])

	assert "<!-- bdi-catalog-bot -->" in str_body
	assert "algo divergiu" in str_body


def test_the_catalog_issue_is_told_apart_from_the_drift_issue() -> None:
	"""The marker, not the shared label, is what identifies this job's issue.

	Both weekly jobs carry the same ``contract-drift`` label, so matching on the label alone would
	make each one hijack and overwrite the other's tracking issue.
	"""
	list_issues = [
		{"number": 1, "body": "<!-- contract-drift-bot -->\nlayout"},
		{"number": 2, "body": "<!-- bdi-catalog-bot -->\ncatalog"},
	]

	assert find_open_catalog_issue(list_issues) == 2
	assert find_open_catalog_issue([list_issues[0]]) is None


def test_every_catalogued_table_declares_a_destination() -> None:
	"""No entry may sit with a state but no reference — that is the defect being prevented.

	A table with nowhere to go is exactly what the audit found 32 of. Recording one in the catalog
	without a reader or an issue would reintroduce the gap while looking like coverage.
	"""
	list_bad = [
		str_table
		for str_table, tuple_meta in BDI_TABLES.items()
		if tuple_meta[2] not in {STATE_IMPLEMENTED, STATE_ISSUE} or not tuple_meta[3].strip()
	]

	assert list_bad == [], f"tables with no destination: {list_bad}"


def test_the_catalog_is_populated() -> None:
	"""Guard the catalog itself, so the gate above can never pass over an empty mapping."""
	assert len(BDI_TABLES) >= 69
