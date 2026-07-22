"""Unit tests for the raw-artifact workspace seam (``_internal.utils.raw_workspace``).

This seam decides whether the bytes a reader downloaded survive the read. That is the
datalake's bronze layer, so the two branches are asserted directly: ``None`` must leave
nothing behind, a path must keep everything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from filings_b3._internal.utils.raw_workspace import raw_workspace


def test_default_workspace_is_removed_on_exit() -> None:
	"""With no path, the workspace is temporary and gone once the block exits.

	The regression this guards: a reader that leaked its tempdir would slowly fill the disk of
	any long-running consumer, and the leak is invisible until it isn't.
	"""
	with raw_workspace() as path_dir:
		assert path_dir.is_dir()
		(path_dir / "artifact.csv").write_bytes(b"a;b\n1;2\n")
		path_seen = path_dir

	assert not path_seen.exists()


def test_given_path_keeps_the_artifact_after_exit(tmp_path: Path) -> None:
	"""With a path, the directory and everything written into it survive the block.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory standing in for a bronze-layer location.
	"""
	path_bronze = tmp_path / "bronze" / "b3" / "bdi" / "20250102"
	with raw_workspace(path_bronze) as path_dir:
		(path_dir / "IN250102.zip").write_bytes(b"PK\x03\x04stub")

	assert path_bronze.is_dir()
	assert (path_bronze / "IN250102.zip").read_bytes() == b"PK\x03\x04stub"


def test_given_path_is_created_with_parents(tmp_path: Path) -> None:
	"""A deep bronze-layer path is created wholesale — the caller pre-creates nothing.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	path_deep = tmp_path / "a" / "b" / "c"
	assert not path_deep.exists()

	with raw_workspace(path_deep) as path_dir:
		assert path_dir == path_deep
		assert path_dir.is_dir()


def test_existing_directory_is_reused_not_cleared(tmp_path: Path) -> None:
	"""Re-reading into an existing bronze directory must not wipe what is already there.

	The failure this prevents is silent data loss: a second run of the same dataset for a
	different member would otherwise destroy the first run's artifact.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	path_bronze = tmp_path / "bronze"
	path_bronze.mkdir()
	(path_bronze / "earlier.csv").write_bytes(b"kept")

	with raw_workspace(path_bronze) as path_dir:
		(path_dir / "later.csv").write_bytes(b"also kept")

	assert (path_bronze / "earlier.csv").read_bytes() == b"kept"
	assert (path_bronze / "later.csv").read_bytes() == b"also kept"


def test_rejects_a_non_path_argument() -> None:
	"""A string path is rejected at the boundary — the seam is runtime type-checked.

	``path_raw`` is annotated ``Path | None`` and the module is under ``@type_checker``, so
	passing a ``str`` (the easy mistake) fails loudly instead of half-working.
	"""
	with pytest.raises(Exception, match=r"(?i)type|annotat"), raw_workspace("not-a-path-object"):  # type: ignore[arg-type]
		pass
