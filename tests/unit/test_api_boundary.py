"""The public/private boundary gate — four deterministic checks, no prose required.

``_internal`` ships inside the wheel (so imports resolve after ``pip install``) but is **not**
public API. That is a convention, and a convention guarded only by a paragraph in a
``CLAUDE.md`` is probabilistic: it holds when whoever is editing happens to read it. These four
tests make it mechanical, so the boundary survives contributors, sessions, and models:

1. :func:`test_public_surface_matches_the_frozen_snapshot` — widening the API is a deliberate
   one-line diff in this file, never an accident.
2. :func:`test_internal_never_imports_the_public_layer` — dependencies point inward only.
3. :func:`test_published_docs_never_teach_the_private_import_path` — the leak that actually
   creates de-facto public API is documentation, not code.
4. :func:`test_importing_the_package_pulls_no_optional_heavy_dependency` — importing the
   library must not drag in a headless browser or a PDF engine.

Everything here is derived (the package name, the module list, the published-docs set) rather
than hand-listed, so the file ports to a sibling package unchanged and cannot silently stop
covering anything. The one deliberate exception is :data:`_PUBLIC_SURFACE` — a snapshot is only
a gate *because* it is hand-maintained.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_DOCS = _REPO_ROOT / "docs"
_MKDOCS = _REPO_ROOT / "mkdocs.yml"


def _package_name() -> str:
	"""Return the import package name — the single directory under ``src/``.

	Derived rather than hard-coded so this gate ports to a sibling ``filings-*`` package
	with no edit.

	Returns
	-------
	str
		The import package name (e.g. ``filings_b3``).

	Raises
	------
	AssertionError
		If ``src/`` does not hold exactly one package directory.
	"""
	list_pkgs = [
		path for path in _SRC.iterdir() if path.is_dir() and (path / "__init__.py").exists()
	]
	assert len(list_pkgs) == 1, f"expected exactly one package under src/, found {list_pkgs}"
	return list_pkgs[0].name


_PKG = _package_name()
_PKG_DIR = _SRC / _PKG
_INTERNAL_DIR = _PKG_DIR / "_internal"

# The frozen public API. Adding a name here is the deliberate act of publishing it — and the
# only way this test goes green again after an export changes. A name may legitimately be
# *promoted* out of `_internal` by re-exporting it from the package `__init__` (filings-cvm
# does exactly this with `RetryPolicy`); what this snapshot forbids is that happening by
# accident.
_PUBLIC_SURFACE: frozenset[str] = frozenset(
	{
		"__version__",
		"BdiBtbLendingOpenPositionsReader",
		"BdiStocksSummaryReader",
		"InstrumentsFileAdrReader",
		"InstrumentsFileBtcReader",
		"InstrumentsFileEqtyFwdReader",
		"InstrumentsFileEqtyReader",
		"InstrumentsFileExrcEqtsReader",
		"InstrumentsFileFxdIncmReader",
		"InstrumentsFileOptnOnEqtsReader",
		"InstrumentsFileOptnOnSpotAndFuturesReader",
		"InstrumentsFileReader",
		"InstrumentsLayoutMetaReader",
	}
)

# The per-section public surface. Each macro-section directory is itself a stable public import
# path (`from filings_b3.daily_bulletin import …`), not merely a source-tree folder — so its
# `__all__` is API too, and earns the same frozen-snapshot treatment as the root. The keys are the
# public sections; a section appearing, or a reader added to one, is a deliberate one-line diff
# here, never an accident. A section whose first reader has not landed yet
# (`search_trading_session`) is listed with an empty set: the path is public, it exports nothing.
_SECTION_SURFACE: dict[str, frozenset[str]] = {
	"daily_bulletin": frozenset({"BdiBtbLendingOpenPositionsReader", "BdiStocksSummaryReader"}),
	"search_trading_session": frozenset(
		{
			"InstrumentsFileAdrReader",
			"InstrumentsFileBtcReader",
			"InstrumentsFileEqtyFwdReader",
			"InstrumentsFileEqtyReader",
			"InstrumentsFileExrcEqtsReader",
			"InstrumentsFileFxdIncmReader",
			"InstrumentsFileOptnOnEqtsReader",
			"InstrumentsFileOptnOnSpotAndFuturesReader",
			"InstrumentsFileReader",
			"InstrumentsLayoutMetaReader",
		}
	),
}

# Optional-extra modules that must never be imported at package-import time. The `Reader` port
# is plain HTTP + tabular parsing; a source genuinely needing a browser or a PDF engine gets a
# separate base behind the `scraping` / `pdf` extras, imported lazily inside the method that
# needs it — never at module scope.
_HEAVY_MODULES: tuple[str, ...] = (
	"playwright",
	"selenium",
	"fitz",
	"pdfplumber",
)


def _public_sections() -> list[str]:
	"""Return every public macro-section package directly under the package root.

	A public section is a subpackage of ``<pkg>`` carrying an ``__init__.py`` whose name is not
	underscore-prefixed — which excludes ``_internal`` and ``__pycache__`` without naming either.
	Derived rather than listed so a newly added section cannot silently escape the gate.

	Returns
	-------
	list of str
		Sorted section package names (e.g. ``["daily_bulletin", "search_trading_session"]``).
	"""
	return sorted(
		path.name
		for path in _PKG_DIR.iterdir()
		if path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith("_")
	)


def _internal_modules() -> list[Path]:
	"""Return every Python module under the private ``_internal`` tree.

	Returns
	-------
	list of pathlib.Path
		Sorted module paths, so parametrised test ids are stable.
	"""
	return sorted(_INTERNAL_DIR.rglob("*.py"))


def _published_docs() -> list[Path]:
	"""Return the Markdown files MkDocs actually publishes, plus the README.

	MkDocs builds **every** ``.md`` under ``docs/`` — a file absent from ``nav:`` is merely
	unlisted, still reachable by URL — so the published set is everything under ``docs/``
	minus the ``exclude_docs`` patterns declared in ``mkdocs.yml``. Those patterns are parsed
	from the config rather than duplicated here: a folder added to ``exclude_docs`` (a new
	backlog-style working area) must not silently start failing this gate.

	Returns
	-------
	list of pathlib.Path
		Sorted paths of published Markdown files.
	"""
	set_excluded = _exclude_doc_patterns()
	list_published = [
		path
		for path in sorted(_DOCS.rglob("*.md"))
		if not _is_excluded(path.relative_to(_DOCS), set_excluded)
	]
	return [_REPO_ROOT / "README.md", *list_published]


def _exclude_doc_patterns() -> set[str]:
	"""Parse the ``exclude_docs:`` block of ``mkdocs.yml`` into a set of patterns.

	A plain text parse of the literal block, deliberately dependency-free — PyYAML lives in
	the docs group, and a unit test must not require it.

	Returns
	-------
	set of str
		The declared patterns (e.g. ``{"backlog/", "superpowers/", "CLAUDE.md"}``).
	"""
	set_patterns: set[str] = set()
	bool_in_block = False
	for str_line in _MKDOCS.read_text(encoding="utf-8").splitlines():
		if str_line.startswith("exclude_docs:"):
			bool_in_block = True
			continue
		if not bool_in_block:
			continue
		# The literal block ends at the first line that is neither blank nor indented.
		if str_line.strip() and not str_line.startswith((" ", "\t")):
			break
		str_pattern = str_line.strip()
		if str_pattern and not str_pattern.startswith("#"):
			set_patterns.add(str_pattern)
	return set_patterns


def _is_excluded(path_rel: Path, set_patterns: set[str]) -> bool:
	"""Return whether a docs-relative path matches an ``exclude_docs`` pattern.

	Supports the two gitignore forms actually used: ``dir/`` (any file beneath it) and a bare
	file or basename (e.g. ``CLAUDE.md``).

	Parameters
	----------
	path_rel : pathlib.Path
		Path relative to ``docs/``.
	set_patterns : set of str
		Patterns from :func:`_exclude_doc_patterns`.

	Returns
	-------
	bool
		True when the file is excluded from the built site.
	"""
	set_parts = set(path_rel.parts)
	for str_pattern in set_patterns:
		if str_pattern.endswith("/") and str_pattern.rstrip("/") in set_parts:
			return True
		if str_pattern == path_rel.name or str_pattern == str(path_rel):
			return True
	return False


# --------------------------
# Gate 1 — the public surface is a frozen, deliberate snapshot
# --------------------------
def test_public_surface_matches_the_frozen_snapshot() -> None:
	"""``__all__`` equals the snapshot — widening the API cannot happen by accident.

	The failure this prevents: a helper re-exported "just for a test" or for one consumer's
	convenience becomes API the moment it ships, and semver then forbids removing it. Making
	the surface a snapshot turns every widening into a reviewable diff in one file.
	"""
	cls_pkg = __import__(_PKG)

	assert frozenset(cls_pkg.__all__) == _PUBLIC_SURFACE, (
		"the public surface changed; update _PUBLIC_SURFACE in this file if that was deliberate"
	)


def test_every_exported_name_actually_resolves() -> None:
	"""Every name in ``__all__`` is a real attribute — a stale export is a broken import.

	``from <pkg> import *`` raises ``AttributeError`` on a name listed in ``__all__`` that no
	longer exists, so an export left behind by a rename breaks consumers, not this package.
	"""
	cls_pkg = __import__(_PKG)

	for str_name in cls_pkg.__all__:
		assert hasattr(cls_pkg, str_name), f"{_PKG}.__all__ lists {str_name!r}, which is absent"


def test_no_exported_name_is_underscore_private() -> None:
	"""No name in ``__all__`` is underscore-prefixed, except the dunder ``__version__``.

	Exporting a ``_``-prefixed name publishes something whose own name says "do not use me" —
	either it is API and should be renamed, or it is not and should not be exported.
	"""
	cls_pkg = __import__(_PKG)

	for str_name in cls_pkg.__all__:
		bool_dunder = str_name.startswith("__") and str_name.endswith("__")
		assert bool_dunder or not str_name.startswith("_"), (
			f"{str_name!r} is private by name but exported; rename it or drop the export"
		)


def test_public_sections_match_the_frozen_snapshot() -> None:
	"""The set of public macro-sections equals the snapshot — a new section is deliberate.

	A section directory is a public import path (#122), so its *appearance* widens the API surface
	exactly as a new root export does. Deriving the set from the tree and comparing it to a
	hand-maintained snapshot turns adding a section into a reviewable one-line diff in this file.
	"""
	assert set(_public_sections()) == set(_SECTION_SURFACE), (
		"the set of public macro-sections changed; update _SECTION_SURFACE if that was deliberate"
	)


@pytest.mark.parametrize("str_section", sorted(_SECTION_SURFACE), ids=lambda s: s)
def test_public_section_surface_matches_the_frozen_snapshot(str_section: str) -> None:
	"""Each section's ``__all__`` equals its snapshot — widening a section is deliberate.

	The same guarantee gate 1 gives the root, applied to every public section path: a reader
	re-exported "just for convenience" becomes API the moment it ships, so each widening is a
	reviewable diff in ``_SECTION_SURFACE`` rather than an accident.

	Parameters
	----------
	str_section : str
		A public macro-section package name.
	"""
	mod_section = __import__(f"{_PKG}.{str_section}", fromlist=["__all__"])

	assert frozenset(mod_section.__all__) == _SECTION_SURFACE[str_section], (
		f"{_PKG}.{str_section} surface changed; update _SECTION_SURFACE if that was deliberate"
	)


@pytest.mark.parametrize("str_section", sorted(_SECTION_SURFACE), ids=lambda s: s)
def test_every_section_export_is_reexported_at_the_root(str_section: str) -> None:
	"""Every section reader is also exported flat from the root — the convenience never rots.

	#122 keeps the flat root import as a backward-compatible convenience beside the organised
	section path. That promise is real only if enforced: a reader added to a section but forgotten
	at the root would leave ``from filings_b3 import <Reader>`` broken for that name.

	Parameters
	----------
	str_section : str
		A public macro-section package name.
	"""
	mod_section = __import__(f"{_PKG}.{str_section}", fromlist=["__all__"])

	for str_name in mod_section.__all__:
		assert str_name in _PUBLIC_SURFACE, (
			f"{_PKG}.{str_section} exports {str_name!r} but the root does not re-export it — "
			"add it to the package __init__ so the flat import stays valid"
		)


# --------------------------
# Gate 2 — dependencies point inward: _internal never imports the public layer
# --------------------------
def test_internal_tree_is_non_empty() -> None:
	"""Guard the discovery itself, so the per-module gate can never cover nothing.

	Without this, a moved or renamed ``_internal`` directory would make
	:func:`test_internal_never_imports_the_public_layer` parametrise over an empty list and
	pass vacuously — a green gate guarding nothing is worse than no gate.
	"""
	assert _internal_modules(), f"no modules found under {_INTERNAL_DIR}"


@pytest.mark.parametrize("path_module", _internal_modules(), ids=lambda p: p.name)
def test_internal_never_imports_the_public_layer(path_module: Path) -> None:
	"""A private module imports only ``_internal`` — never the package's public layer.

	Dependencies must point inward. An ``_internal`` helper reaching back up to a public
	module inverts that, creates an import cycle risk, and — worse — makes the public layer
	load-bearing for the private one, so the "private" tree can no longer be reasoned about
	or reused on its own.

	Relative imports are rejected outright rather than resolved: enough leading dots escape
	the private tree just as effectively, and the project mandates absolute imports anyway,
	so rejecting is both stricter and simpler than resolving each one.

	Parameters
	----------
	path_module : pathlib.Path
		A module under ``_internal/``.
	"""
	cls_tree = ast.parse(path_module.read_text(encoding="utf-8"), filename=str(path_module))
	str_where = path_module.relative_to(_REPO_ROOT)

	for cls_node in ast.walk(cls_tree):
		if isinstance(cls_node, ast.Import):
			for cls_alias in cls_node.names:
				assert not _is_upward_import(cls_alias.name), (
					f"{str_where}:{cls_node.lineno} imports {cls_alias.name!r} — "
					"_internal must not import the public layer"
				)
		elif isinstance(cls_node, ast.ImportFrom):
			assert cls_node.level == 0, (
				f"{str_where}:{cls_node.lineno} uses a relative import — use an absolute one"
			)
			assert cls_node.module is None or not _is_upward_import(cls_node.module), (
				f"{str_where}:{cls_node.lineno} imports from {cls_node.module!r} — "
				"_internal must not import the public layer"
			)


def _is_upward_import(str_module: str) -> bool:
	"""Return whether a module path reaches out of ``_internal`` into the public layer.

	Parameters
	----------
	str_module : str
		A dotted module path from an ``import`` statement.

	Returns
	-------
	bool
		True for ``<pkg>`` or ``<pkg>.<public>``; False for ``<pkg>._internal…`` and for any
		third-party or stdlib module.
	"""
	if str_module != _PKG and not str_module.startswith(f"{_PKG}."):
		return False
	return not str_module.startswith(f"{_PKG}._internal")


# --------------------------
# Gate 3 — published documentation never teaches the private import path
# --------------------------
def test_published_docs_set_is_non_empty() -> None:
	"""Guard the discovery: the published-docs set must not be empty.

	If ``exclude_docs`` parsing ever over-matches, this gate would silently scan nothing.
	"""
	assert _published_docs(), "no published docs discovered — the exclude_docs parse is wrong"


@pytest.mark.parametrize("path_doc", _published_docs(), ids=lambda p: p.name)
def test_published_docs_never_teach_the_private_import_path(path_doc: Path) -> None:
	"""No published page shows an import of ``_internal``.

	This is the leak that matters. Code can be refactored; documentation cannot be recalled.
	The day a usage example prints ``from <pkg>._internal.utils… import …``, consumers copy it,
	the underscore stops meaning anything, and the next refactor of a "private" helper is a
	breaking change. Working notes under ``exclude_docs`` (``docs/backlog/``) are exempt —
	they are not published, and discussing the internals is exactly their job.

	Parameters
	----------
	path_doc : pathlib.Path
		A published Markdown file.
	"""
	str_text = path_doc.read_text(encoding="utf-8")
	str_where = path_doc.relative_to(_REPO_ROOT)

	for int_no, str_line in enumerate(str_text.splitlines(), start=1):
		assert f"{_PKG}._internal" not in str_line, (
			f"{str_where}:{int_no} shows the private import path in a PUBLISHED page: "
			f"{str_line.strip()!r} — document the public API instead"
		)


# --------------------------
# Gate 4 — importing the package pulls no optional heavy dependency
# --------------------------
def test_importing_the_package_pulls_no_optional_heavy_dependency() -> None:
	"""``import <pkg>`` loads no headless browser and no PDF engine.

	Run in a **subprocess** deliberately: an in-process ``sys.modules`` check would be
	satisfied by the module merely not being installed, so the gate would pass today and rot
	the moment ``scraping`` lands in the dev environment. A clean interpreter asserts the real
	property — that the import graph does not reach them — regardless of what is installed.

	``PYTHONPATH`` is seeded from the parent's ``sys.path`` because this project uses a src
	layout and pytest injects ``src`` via ``pythonpath`` in ``pytest.ini``. A bare subprocess
	inherits none of that, so without this it resolves the package only when it happens to be
	pip-installed into the environment — which is true on a dev machine and **not** guaranteed
	on a CI runner whose cached venv skipped the project install. Inheriting the parent's
	resolution path keeps the gate measuring the import *graph*, never the install *method*;
	``sys.modules`` still starts empty in the child, which is the property under test.
	"""
	str_code = (
		f"import {_PKG}, sys; "
		f"print(','.join(sorted(m for m in {_HEAVY_MODULES!r} if m in sys.modules)))"
	)
	dict_env = {
		**os.environ,
		"PYTHONPATH": os.pathsep.join(str_p for str_p in sys.path if str_p),
	}
	cls_proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
		[sys.executable, "-c", str_code],
		capture_output=True,
		text=True,
		check=False,
		cwd=_REPO_ROOT,
		env=dict_env,
	)

	assert cls_proc.returncode == 0, f"importing {_PKG} failed:\n{cls_proc.stderr}"
	str_leaked = cls_proc.stdout.strip()
	assert not str_leaked, (
		f"importing {_PKG} pulled optional heavy dependencies: {str_leaked} — "
		"import them lazily, inside the method that needs them"
	)
