"""Unit tests for the PR quality gate's classifier (pure, offline, no network).

Everything above ``main()`` in ``bin/pr_gate.py`` is a pure function precisely so the whole
classification policy is testable with no API access — the autouse network guard in
``tests/conftest.py`` would block a real call anyway.

``bin/`` is not a package, so the module is loaded **by path** via importlib.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_GATE_PATH = Path(__file__).resolve().parents[2] / "bin" / "pr_gate.py"


def _load_gate() -> ModuleType:
	"""Load ``bin/pr_gate.py`` as a module by path.

	Returns
	-------
	ModuleType
		The imported ``pr_gate`` module.
	"""
	cls_spec = importlib.util.spec_from_file_location("pr_gate", _GATE_PATH)
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules["pr_gate"] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load_gate()


@pytest.mark.parametrize(
	("str_path", "str_expected"),
	[
		("src/model/loader.py", "src"),
		("tests/unit/test_x.py", "tests"),
		(".github/workflows/tests.yaml", "ci"),
		("bin/venv.sh", "ci"),
		("pyproject.toml", "deps"),
		("poetry.lock", "deps"),
		("docs/usage.md", "docs"),
		("mkdocs.yml", "docs"),
		("some/unknown/thing.xyz", "other"),
	],
)
def test_classify_path_maps_each_class(str_path: str, str_expected: str) -> None:
	"""Each representative path lands in its documented risk class."""
	assert gate.classify_path(str_path) == str_expected


def test_classify_risk_returns_the_most_dangerous_class() -> None:
	"""A mixed PR collapses to its most dangerous class — docs never masks src."""
	assert gate.classify_risk(["docs/a.md", "src/x.py"]) == "src"
	assert gate.classify_risk(["docs/a.md", "tests/test_x.py"]) == "tests"


def test_classify_risk_treats_an_unknown_path_as_unsafe() -> None:
	"""An unmatched path outranks the safe classes: unknown is unsafe (default-deny)."""
	assert gate.classify_risk(["docs/a.md", "weird.bin"]) == "other"
	assert gate.classify_risk(["weird.bin"]) not in gate.AUTO_MERGEABLE


@pytest.mark.parametrize(
	("int_lines", "str_bucket"),
	[
		(0, "XS"),
		(10, "XS"),
		(11, "S"),
		(50, "S"),
		(51, "M"),
		(200, "M"),
		(201, "L"),
		(500, "L"),
		(501, "XL"),
	],
)
def test_classify_size_buckets(int_lines: int, str_bucket: str) -> None:
	"""Changed-line counts fall in the documented buckets, boundaries included."""
	assert gate.classify_size(int_lines) == str_bucket


def test_is_lockfile_only_is_narrow() -> None:
	"""Only a lockfile-ONLY diff qualifies — a hand-edited sibling must not."""
	assert gate.is_lockfile_only([gate.LOCKFILE]) is True
	assert gate.is_lockfile_only([gate.LOCKFILE, "pyproject.toml"]) is False
	assert gate.is_lockfile_only(["pyproject.toml"]) is False


def test_auto_merge_allows_safe_classes_without_a_label() -> None:
	"""Consent is opt-OUT: the safe classes merge with no label at all."""
	for str_risk in sorted(gate.AUTO_MERGEABLE):
		assert gate.is_auto_mergeable(str_risk, "M", []) is True


def test_auto_merge_refuses_dangerous_classes() -> None:
	"""src/tests define what 'passing' means; other is unknown — none may auto-merge."""
	for str_risk in ("src", "tests", "other"):
		assert gate.is_auto_mergeable(str_risk, "XS", []) is False


def test_block_label_is_the_opt_out() -> None:
	"""The do-not-merge label vetoes an otherwise-eligible PR."""
	assert gate.is_auto_mergeable("docs", "S", [gate.BLOCK_LABEL]) is False


def test_xl_veto_applies_to_handwritten_but_is_waived_for_a_lockfile() -> None:
	"""A huge hand-written diff is vetoed; a regenerated lockfile is exempt.

	The regression this guards: a lockfile's diff size tracks how many dependency hashes moved,
	not how much risk arrived — so without the exemption, whether the weekly bump self-merges
	depends on how many packages happened to move that week.
	"""
	assert gate.is_auto_mergeable("deps", "XL", []) is False
	assert gate.is_auto_mergeable("deps", "XL", [], bool_lockfile_only=True) is True


def test_gate_state_lets_red_outrank_pending() -> None:
	"""For DISPLAY, a known failure outranks a still-deciding axis."""
	assert gate.gate_state({"a": "failure", "b": "pending"}) == "failure"
	assert gate.gate_state({"a": "pending", "b": "success"}) == "pending"
	assert gate.gate_state({"a": "success"}) == "success"


def test_terminality_is_separate_from_display_state() -> None:
	"""A red-with-pending set is NOT terminal — conflating the two freezes the sticky comment.

	Breaking the poll loop on ``gate_state() != 'pending'`` would stop on the first transient red
	while other checks still run, and nothing re-renders the comment afterwards.
	"""
	dict_axes = {"a": "failure", "b": "pending"}
	assert gate.gate_state(dict_axes) == "failure"
	assert gate.axes_are_terminal(dict_axes) is False
	assert gate.axes_are_terminal({"a": "failure", "b": "success"}) is True


def test_axis_with_no_check_run_is_pending_not_failing() -> None:
	"""An axis with no check-run yet on this head SHA is awaiting a result, never a failure."""
	dict_axes, _ = gate.collect_axes([], {"tests": ("Run Automated Tests",)})
	assert dict_axes["tests"] == "pending"


def test_collect_axes_matches_the_analysis_not_the_umbrella() -> None:
	"""CodeQL's umbrella check must not decide the axis — the Analyze runs carry the conclusion."""
	list_runs = [
		{"name": "CodeQL", "status": "in_progress", "conclusion": None},
		{"name": "Analyze (python)", "status": "completed", "conclusion": "success"},
	]
	dict_axes, _ = gate.collect_axes(list_runs, {"code scanning": ("Analyze",)})
	assert dict_axes["code scanning"] == "success"


def test_failing_axis_names_its_checks() -> None:
	"""A failing axis reports WHICH checks failed — a bare count teaches the reader nothing."""
	list_runs = [
		{"name": "Run Automated Tests (ubuntu)", "status": "completed", "conclusion": "failure"}
	]
	dict_axes, dict_failing = gate.collect_axes(list_runs, {"tests": ("Run Automated Tests",)})
	assert dict_axes["tests"] == "failure"
	assert dict_failing["tests"] == ["Run Automated Tests (ubuntu)"]


def test_render_comment_carries_the_sticky_marker_and_the_failing_names() -> None:
	"""The rendered body carries the hidden marker (so it updates in place) and names failures."""
	str_body = gate.render_comment(
		"deps", "L", {"tests": "failure"}, False, {"tests": ["Run Automated Tests (ubuntu)"]}
	)
	assert gate.COMMENT_MARKER in str_body
	assert "Run Automated Tests (ubuntu)" in str_body
	assert "risk:" in str_body and "deps" in str_body
