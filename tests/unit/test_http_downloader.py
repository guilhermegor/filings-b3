"""Unit tests for the HTTP download seam's request shape.

The seam issues a ``GET`` by default, and a ``POST`` when the caller hands it a body — some
published datasets are served by endpoints that answer **405** to a GET (B3's Boletim Diário
tables). These tests inspect the :class:`urllib.request.Request` the seam builds, patching the
opener, so the request shape is pinned without touching the network.
"""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request

import pytest

import filings_b3._internal.utils.http_downloader as http_downloader


class _FakeResponse:
	"""Minimal stand-in for the object ``urlopen`` yields."""

	status = 200

	def __enter__(self) -> _FakeResponse:
		return self

	def __exit__(self, *args: object) -> None:
		return None

	def read(self) -> bytes:
		return b'{"ok": true}'


@pytest.fixture
def _capture_request(monkeypatch: pytest.MonkeyPatch) -> list[Request]:
	"""Capture the request the seam builds instead of sending it."""
	list_seen: list[Request] = []

	def _fake_open(cls_request: Request, **kwargs: object) -> _FakeResponse:  # noqa: ARG001
		list_seen.append(cls_request)
		return _FakeResponse()

	# The host check resolves DNS, which a unit test must not do; the request shape is the subject.
	monkeypatch.setattr(http_downloader, "_assert_public_host", lambda str_url: None)  # noqa: ARG005
	monkeypatch.setattr(http_downloader._OPENER, "open", _fake_open)
	return list_seen


def test_download_file_issues_a_get_when_no_payload_is_given(
	_capture_request: list[Request], tmp_path: Path
) -> None:
	"""The default stays a plain GET with no body — the shape every existing caller relies on."""
	http_downloader.download_file("https://example.com/data", tmp_path / "out.json")

	cls_request = _capture_request[0]
	assert cls_request.get_method() == "GET"
	assert cls_request.data is None


def test_download_file_issues_a_post_carrying_the_payload_and_content_type(
	_capture_request: list[Request], tmp_path: Path
) -> None:
	"""A payload turns the request into a POST that carries the body and its declared type.

	B3's bulletin service answers 405 to a GET: the query travels in the URL path and the body is
	an empty JSON object. Without this the whole Boletim Diário section downloads nothing.
	"""
	http_downloader.download_file(
		"https://example.com/bdi/table/X/2026-08-07/2026-08-07/1/100",
		tmp_path / "out.json",
		bytes_payload=b"{}",
		str_content_type="application/json",
	)

	cls_request = _capture_request[0]
	assert cls_request.get_method() == "POST"
	assert cls_request.data == b"{}"
	assert cls_request.get_header("Content-type") == "application/json"


def test_download_file_sends_no_content_type_when_the_caller_declares_none(
	_capture_request: list[Request], tmp_path: Path
) -> None:
	"""The seam never infers what the bytes mean — an undeclared type is simply not sent.

	Guessing one encoding here would make it the silent default for every future endpoint,
	which is the caller's decision, not the seam's.
	"""
	http_downloader.download_file(
		"https://example.com/x", tmp_path / "out.bin", bytes_payload=b"raw"
	)

	assert _capture_request[0].get_header("Content-type") is None


def test_download_file_writes_the_response_body(
	_capture_request: list[Request], tmp_path: Path
) -> None:
	"""The response body reaches disk untouched, POST or GET."""
	path_out = http_downloader.download_file(
		"https://example.com/x", tmp_path / "out.json", bytes_payload=b"{}"
	)

	assert path_out.read_bytes() == b'{"ok": true}'
