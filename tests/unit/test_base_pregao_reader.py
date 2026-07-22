"""Unit tests for the Pesquisa por Pregao section base (``_base_pregao_reader``).

The lifecycle is exercised **offline**: ``download_file`` is patched at its own module
boundary to materialise a fixture instead of hitting the network, so the test proves the
fetch → locate → read → stamp orchestration, contract enforcement, dtype coercion, and
provenance stamping — deterministically, with no real I/O.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from filings_b3._internal.config.contracts import EXAMPLE_SOURCE
from filings_b3._internal.utils.http_downloader import url_filename
from filings_b3._internal.utils.tabular_reader import ContractError, FileContract
from filings_b3.search_trading_session._base_pregao_reader import _BasePregaoReader


# EXAMPLE_SOURCE requires columns ("code", "amount"); the fixture below satisfies it.
_FIXTURE_CSV: bytes = b"code;amount\nABC;1.50\nDEF;2.25\n"
_FAKE_URL: str = "https://www.b3.com.br/data/sample.csv"


class _SampleReader(_BasePregaoReader):
	"""Minimal concrete adapter over the shipped EXAMPLE_SOURCE contract (test-only)."""

	str_source_key = "sample_reader"
	cls_contract = EXAMPLE_SOURCE
	dict_dtypes = {"code": "string", "amount": "float64"}

	def build_url(self) -> str:
		"""Return the (fake) source URL.

		Returns
		-------
		str
			A fixed http URL ending in ``.csv`` so the reader parses it as CSV.
		"""
		return _FAKE_URL


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Patch ``download_file`` to write the CSV fixture instead of hitting the network.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam at its own module boundary (where
		``run`` imports it lazily).
	"""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 30) -> Path:
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(_FIXTURE_CSV)
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)


def test_run_returns_typed_contract_validated_frame(_patch_download: None) -> None:
	"""read() yields the source columns typed as declared, plus provenance columns."""
	df_out = _SampleReader().read()

	assert list(df_out.columns) == list(EXAMPLE_SOURCE.output_columns)
	assert len(df_out) == 2
	assert str(df_out["code"].dtype) == "string"
	assert str(df_out["amount"].dtype) == "float64"
	assert df_out["amount"].tolist() == [1.50, 2.25]


def test_run_stamps_source_url_provenance(_patch_download: None) -> None:
	"""Every stamped row carries the exact source URL read() fetched from."""
	df_out = _SampleReader().read()

	assert (df_out["url"] == _FAKE_URL).all()
	assert df_out["source_key"].iloc[0] == EXAMPLE_SOURCE.str_source_key


def test_run_raises_contract_error_when_required_column_missing(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A payload missing a required column fails the contract before typing."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 30) -> Path:
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(b"code\nABC\n")  # 'amount' missing
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)
	with pytest.raises(ContractError):
		_SampleReader().read()


def test_locate_table_default_is_identity(tmp_path: Path) -> None:
	"""The default locate_table returns the downloaded path unchanged.

	Parameters
	----------
	tmp_path : pathlib.Path
		pytest-provided temporary directory (the path need not exist — identity is
		asserted on the value, not on the file).
	"""
	path_in = tmp_path / "whatever.csv"
	assert _SampleReader().locate_table(path_in) == path_in


def test_missing_required_attr_raises_at_subclass_definition() -> None:
	"""An adapter omitting a required class attribute fails when the class is created."""
	with pytest.raises(NotImplementedError, match="dict_dtypes"):

		class _Incomplete(_BasePregaoReader):
			str_source_key = "incomplete"
			cls_contract = EXAMPLE_SOURCE
			# dict_dtypes deliberately omitted

			def build_url(self) -> str:
				return _FAKE_URL


@pytest.mark.parametrize(
	("str_url", "str_expected"),
	[
		("https://www.b3.com.br/data/IN250102.zip", "IN250102.zip"),
		("https://www.b3.com.br/pesquisapregao/download?filelist=IN.zip", "download"),
		("https://example.com/", "download"),
	],
)
def test_url_filename_derivation(str_url: str, str_expected: str) -> None:
	"""url_filename takes the last path segment, falling back to 'download'."""
	assert url_filename(str_url) == str_expected


def test_base_contract_type_is_filecontract() -> None:
	"""The sample reader's contract is a FileContract (sanity: correct seam wired)."""
	assert isinstance(_SampleReader.cls_contract, FileContract)
