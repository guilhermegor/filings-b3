"""Unit tests for the provenance seam (``_internal.utils.provenance``).

Provenance is what makes a bronze row answer *where did this come from, how stale is it, and
did the source change*. The hashing half is tested hardest here, because a wrong
``content_hash`` does not fail loudly — it silently reports "unchanged" for a source that
changed, which is the exact failure the column exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from filings_b3._internal.utils.provenance import (
	hash_artifact,
	hash_artifacts,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.tabular_reader import FileContract


# Contracts are normally constructed only in config/contracts (ruff TID251); tests are exempt.
_CONTRACT = FileContract("Sample", "sample_source", ("code",), ())


def _write(path_dir: Path, str_name: str, bytes_body: bytes) -> Path:
	"""Write one artifact and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to write into.
	str_name : str
		File name.
	bytes_body : bytes
		File contents.

	Returns
	-------
	pathlib.Path
		The written path.
	"""
	path_file = path_dir / str_name
	path_file.write_bytes(bytes_body)
	return path_file


def test_hash_artifact_is_stable_and_content_sensitive(tmp_path: Path) -> None:
	"""The same bytes hash the same; one changed byte changes the digest.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	path_a = _write(tmp_path, "a.csv", b"code\nABC\n")
	path_b = _write(tmp_path, "b.csv", b"code\nABC\n")
	path_c = _write(tmp_path, "c.csv", b"code\nABD\n")

	assert hash_artifact(path_a) == hash_artifact(path_b)
	assert hash_artifact(path_a) != hash_artifact(path_c)


def test_hash_artifacts_detects_a_change_in_any_artifact(tmp_path: Path) -> None:
	"""A change in a LATER artifact changes the composite digest.

	This is the regression that motivated the function. The BDI base previously stamped
	``hash_artifact(page_1)``, so a dataset whose page 1 was unchanged but whose page 3 gained
	or lost rows produced an identical ``content_hash`` — the lake would report "source
	unchanged" while the source had, in fact, drifted. Hashing page 1 alone is not a weaker
	check; it is a check that answers the wrong question.
	"""
	path_p1 = _write(tmp_path, "page_0001.json", b'{"values": [1]}')
	path_p2 = _write(tmp_path, "page_0002.json", b'{"values": [2]}')
	path_p3 = _write(tmp_path, "page_0003.json", b'{"values": [3]}')
	str_before = hash_artifacts([path_p1, path_p2, path_p3])

	# Page 1 and 2 untouched; only the third artifact drifts.
	path_p3.write_bytes(b'{"values": [3, 4]}')
	str_after = hash_artifacts([path_p1, path_p2, path_p3])

	assert str_before != str_after, "drift on a later page must change the composite hash"
	assert hash_artifact(path_p1) == hash_artifact(path_p1), "page 1 itself is unchanged"


def test_hash_artifacts_is_deterministic(tmp_path: Path) -> None:
	"""The same artifacts in the same order always yield the same digest.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	path_p1 = _write(tmp_path, "p1", b"one")
	path_p2 = _write(tmp_path, "p2", b"two")

	assert hash_artifacts([path_p1, path_p2]) == hash_artifacts([path_p1, path_p2])


def test_hash_artifacts_is_order_sensitive(tmp_path: Path) -> None:
	"""Reordering the artifacts changes the digest — a re-paginated source is detectable.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	path_p1 = _write(tmp_path, "p1", b"one")
	path_p2 = _write(tmp_path, "p2", b"two")

	assert hash_artifacts([path_p1, path_p2]) != hash_artifacts([path_p2, path_p1])


def test_hash_artifacts_of_one_file_is_a_composite_not_the_file_hash(tmp_path: Path) -> None:
	"""A single-artifact composite deliberately differs from that file's own digest.

	If the two coincided, a dataset growing from one page to two would silently change what
	its stored hash *means*, and a diff of old-vs-new stamps could not tell "the source
	changed" from "the read shape changed".
	"""
	path_only = _write(tmp_path, "only.json", b"payload")

	assert hash_artifacts([path_only]) != hash_artifact(path_only)


def test_hash_artifacts_of_nothing_is_well_defined() -> None:
	"""An empty read yields the digest of no bytes rather than raising."""
	assert hash_artifacts([]) == (
		"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	)


def test_stamp_appends_provenance_after_the_source_columns() -> None:
	"""Stamping preserves source columns and order, appending provenance behind them."""
	df_in = pd.DataFrame({"code": ["ABC", "DEF"]})

	df_out = stamp_provenance(df_in, "https://example.com/x.csv", _CONTRACT, "deadbeef", "1.2.3")

	assert list(df_out.columns) == list(_CONTRACT.output_columns)
	assert df_out["code"].tolist() == ["ABC", "DEF"]
	assert (df_out["content_hash"] == "deadbeef").all()
	assert (df_out["package_version"] == "1.2.3").all()
	assert (df_out["url"] == "https://example.com/x.csv").all()
	assert (df_out["source_key"] == "sample_source").all()


def test_stamp_does_not_mutate_the_input_frame() -> None:
	"""The input frame is left untouched — stamping returns a new frame."""
	df_in = pd.DataFrame({"code": ["ABC"]})

	stamp_provenance(df_in, "https://example.com/x.csv", _CONTRACT, "hash", "1.0.0")

	assert list(df_in.columns) == ["code"]


def test_stamp_shares_one_run_id_across_every_row() -> None:
	"""All rows of one read share an ingestion_run_id, so a read is reconstructable."""
	df_in = pd.DataFrame({"code": ["A", "B", "C"]})

	df_out = stamp_provenance(df_in, "https://example.com/x.csv", _CONTRACT, "hash", "1.0.0")

	set_run_ids = set(df_out["ingestion_run_id"])
	assert len(set_run_ids) == 1


def test_stamp_marks_updated_at_as_tz_aware_utc() -> None:
	"""updated_at is tz-aware UTC — lossless and unambiguous at the warehouse boundary."""
	df_out = stamp_provenance(
		pd.DataFrame({"code": ["A"]}), "https://example.com/x", _CONTRACT, "h", "1.0.0"
	)

	assert str(df_out["updated_at"].dtype) == "datetime64[ns, UTC]"


def test_stamp_handles_an_empty_frame() -> None:
	"""An empty read still yields the full provenance schema, so the sink shape is stable."""
	df_out = stamp_provenance(
		pd.DataFrame({"code": []}), "https://example.com/x", _CONTRACT, "h", "1.0.0"
	)

	assert list(df_out.columns) == list(_CONTRACT.output_columns)
	assert len(df_out) == 0


def test_resolve_package_version_falls_back_for_an_uninstalled_distribution() -> None:
	"""An uninstalled distribution stamps the stub version rather than raising."""
	assert resolve_package_version("no-such-distribution-anywhere") == "0.0.0"


def test_hash_artifact_rejects_a_missing_file(tmp_path: Path) -> None:
	"""Hashing an absent artifact fails loudly — a silent empty hash would be far worse.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory.
	"""
	with pytest.raises(OSError, match=r"(?i)no such file|not found"):
		hash_artifact(tmp_path / "absent.csv")
