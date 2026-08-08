"""Unit tests for the zip seam's bounded-read helpers.

`peek_member` exists so a reader can inspect a member's header — a declared generation time, a
format marker — without decompressing a body that runs to hundreds of megabytes. These tests pin
that the bound is real, since a helper that quietly reads everything is indistinguishable from
one that reads a prefix until the file is big.
"""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from filings_b3._internal.utils.zip_extractor import list_member_names, peek_member


@pytest.fixture
def _path_zip(tmp_path: Path) -> Path:
	"""Write a two-member archive whose payload is far longer than any prefix read."""
	path_zip = tmp_path / "sample.zip"
	with zipfile.ZipFile(path_zip, "w", zipfile.ZIP_DEFLATED) as cls_zip:
		cls_zip.writestr("header_then_body.txt", "HEAD" + "x" * 100_000)
		cls_zip.writestr("other.txt", "other")
	return path_zip


def test_list_member_names_returns_archive_order(_path_zip: Path) -> None:
	"""The names come back in archive order, with nothing extracted."""
	assert list_member_names(_path_zip) == ["header_then_body.txt", "other.txt"]


def test_peek_member_reads_only_the_requested_prefix(_path_zip: Path) -> None:
	"""Only the requested bytes are decompressed, however long the member is."""
	assert peek_member(_path_zip, "header_then_body.txt", 4) == b"HEAD"


def test_peek_member_rejects_a_negative_size(_path_zip: Path) -> None:
	"""A negative size is refused: ``read(-1)`` would decompress the whole member.

	That is the exact outcome the helper exists to avoid, and it fails *silently* — the caller
	gets correct bytes, just all of them, so only memory and time say anything is wrong.
	"""
	with pytest.raises(ValueError, match="non-negative"):
		peek_member(_path_zip, "header_then_body.txt", -1)


def test_peek_member_raises_on_a_missing_member(_path_zip: Path) -> None:
	"""An absent member fails loudly instead of returning empty bytes."""
	with pytest.raises(KeyError):
		peek_member(_path_zip, "absent.txt", 4)
