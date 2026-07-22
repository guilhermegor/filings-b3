"""Unit tests for the work-ledger gate's pure logic (offline; no git, no network).

Only the path-classification and ledger-validation seams are tested here — the git plumbing
(`merge-base`, `diff --cached`) belongs to an integration test, not a unit one.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("pr_gate")
ledger = _load("check_backlog_ledger")


def test_ledger_required_for_src_and_ci() -> None:
	"""A branch touching src/ or ci paths must carry a ledger."""
	assert ledger.needs_ledger(["src/model/loader.py"], gate) is True
	assert ledger.needs_ledger(["bin/venv.sh"], gate) is True


def test_ledger_not_required_for_routine_classes() -> None:
	"""docs/deps/tests-only branches are routine — a ledger there would be noise."""
	assert ledger.needs_ledger(["docs/usage.md"], gate) is False
	assert ledger.needs_ledger(["poetry.lock"], gate) is False
	assert ledger.needs_ledger(["tests/unit/test_x.py"], gate) is False


def test_membership_is_asked_per_path_not_over_the_whole_list() -> None:
	"""The regression this guards: a mixed branch must NOT escape the ledger requirement.

	``classify_risk`` returns the single most-dangerous class and ranks ``tests`` above ``ci``, so
	a branch touching both ``bin/`` and ``tests/`` collapses to ``tests`` — which is not a ledger
	class. Asking per path is what keeps the requirement honest.
	"""
	list_mixed = ["bin/venv.sh", "tests/unit/test_x.py"]
	assert gate.classify_risk(list_mixed) == "tests"  # whole-list view would escape...
	assert ledger.needs_ledger(list_mixed, gate) is True  # ...per-path view catches it


def test_a_valid_ledger_satisfies_the_branch() -> None:
	"""A correctly named ledger clears the requirement."""
	assert (
		ledger.find_ledger_problems(["src/a.py", "docs/backlog/my-topic_20260720_101500.md"]) == []
	)


def test_missing_ledger_is_reported() -> None:
	"""A src-touching branch with no ledger fails, and the message says what to create."""
	list_problems = ledger.find_ledger_problems(["src/a.py"])
	assert list_problems
	assert "docs/backlog" in list_problems[0]


def test_ledger_name_must_be_kebab_plus_timestamp() -> None:
	"""A misnamed ledger is rejected — the timestamped kebab name is the convention."""
	list_problems = ledger.find_ledger_problems(["src/a.py", "docs/backlog/BadName.md"])
	assert list_problems
	assert "kebab" in list_problems[0]
