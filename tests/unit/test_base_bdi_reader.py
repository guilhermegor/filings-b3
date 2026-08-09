"""Unit tests for the BDI section's paginated-JSON base (``daily_bulletin._base_bdi_reader``).

Exercised **offline**: ``download_file`` is patched at its own module boundary to materialise
JSON page fixtures instead of hitting the network, so the tests prove pagination, the positional
values → named columns mapping, raw-page retention, contract enforcement, dtype coercion and
provenance stamping — deterministically, with no real I/O.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from filings_b3._internal.utils.tabular_reader import ContractError, FileContract
from filings_b3.daily_bulletin._base_bdi_reader import (
	BDI_TABLE_BASE,
	_BaseBdiReader,
)


# Contracts are normally built only in config/contracts (ruff TID251); tests are exempt, and a
# throwaway contract keeps this file independent of whichever real datasets exist.
_CONTRACT = FileContract("Sample BDI", "sample_bdi", ("TCKR_SYMB", "VLM_TRADED_DAY"), ())
_DATE = date(2025, 1, 2)


def _page(list_rows: list[list[object]]) -> bytes:
	"""Render a BDI API page payload.

	Parameters
	----------
	list_rows : list of list
		Positional row values, exactly as the API returns them.

	Returns
	-------
	bytes
		The encoded JSON payload.
	"""
	dict_payload = {
		"table": {
			"columns": [{"name": "TckrSymb"}, {"name": "VlmTradedDay"}],
			"values": list_rows,
		}
	}
	return json.dumps(dict_payload).encode("utf-8")


class _SampleBdiReader(_BaseBdiReader):
	"""Minimal concrete BDI adapter over the throwaway contract (test-only).

	Declares itself **paginated** so the pagination tests below exercise the multi-page path;
	the single-page default is covered separately by :class:`_DefaultPagingReader`.
	"""

	str_source_key = "sample_bdi"
	str_endpoint = "DailyAverageStocks"
	cls_contract = _CONTRACT
	dict_dtypes = {"TCKR_SYMB": "str", "VLM_TRADED_DAY": "float64"}
	int_max_pages = None


class _DefaultPagingReader(_BaseBdiReader):
	"""Adapter that declares no pagination, so it inherits the single-page default."""

	str_source_key = "default_paging"
	str_endpoint = "DailyAverageStocks"
	cls_contract = _CONTRACT
	dict_dtypes = {"TCKR_SYMB": "str", "VLM_TRADED_DAY": "float64"}


@pytest.fixture
def _patch_pages(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Serve two rows on page 1, two on page 2, then an empty page 3.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam at its own module boundary.
	"""
	dict_pages = {
		1: _page([["PETR4", 1.5], ["VALE3", 2.5]]),
		2: _page([["ITUB4", 3.5], ["BBAS3", 4.5]]),
	}

	def _fake_download(
		str_url: str,
		path_dest: Path,
		int_timeout_s: int = 30,
		bytes_payload: bytes | None = None,
		str_content_type: str | None = None,
	) -> Path:
		int_page = int(str_url.rstrip("/").split("/")[-2])
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(dict_pages.get(int_page, _page([])))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)


def test_read_requests_each_page_as_a_json_post(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Every page is fetched with POST and an empty JSON body — the bulletin rejects GET.

	Measured against the live service: a GET returns **405 Method Not Allowed**, with or without
	browser headers and cookies, so the whole section downloads nothing. Pins the *wiring*: the
	seam only sends a body when a caller passes one, and this reader is the caller that knows
	the bulletin is a POST API whose query travels in the URL path.
	"""
	list_calls: list[tuple[bytes | None, str | None]] = []

	def _fake_download(
		str_url: str,  # noqa: ARG001
		path_dest: Path,
		int_timeout_s: int = 30,  # noqa: ARG001
		bytes_payload: bytes | None = None,
		str_content_type: str | None = None,
	) -> Path:
		list_calls.append((bytes_payload, str_content_type))
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(_page([["PETR4", 1.5]]))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)

	_DefaultPagingReader(_DATE).read()

	assert list_calls == [(b"{}", "application/json")]


def test_read_paginates_until_an_empty_page(_patch_pages: None) -> None:
	"""Pages are concatenated, and the empty page ends the loop rather than being appended."""
	df_out = _SampleBdiReader(_DATE).read()

	assert len(df_out) == 4
	assert df_out["TCKR_SYMB"].tolist() == ["PETR4", "VALE3", "ITUB4", "BBAS3"]


def test_single_page_is_the_default_and_stops_after_page_one(_patch_pages: None) -> None:
	"""A reader that does not declare pagination reads exactly one page.

	32 of the 38 BDI datasets are single-page, so this is the safe default: it cannot
	multiply an echoing endpoint, and a genuinely paginated dataset opts in explicitly.
	"""
	df_out = _DefaultPagingReader(_DATE).read()

	assert _DefaultPagingReader.int_max_pages == 1
	assert df_out["TCKR_SYMB"].tolist() == ["PETR4", "VALE3"], "only page 1"


def test_an_echoing_endpoint_is_not_multiplied(monkeypatch: pytest.MonkeyPatch) -> None:
	"""An endpoint serving the SAME rows for every page number stops at the first repeat.

	Three BDI endpoints behave this way. Without the digest check an unbounded read would
	append the same rows once per page up to the 500-page ceiling — a corruption no contract
	check could catch, because every duplicated row is individually valid.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam.
	"""

	def _fake_download(
		str_url: str,
		path_dest: Path,
		int_timeout_s: int = 30,
		bytes_payload: bytes | None = None,
		str_content_type: str | None = None,
	) -> Path:
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(_page([["PETR4", 1.5], ["VALE3", 2.5]]))  # same, every page
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)

	class _EchoingReader(_SampleBdiReader):
		"""Wrongly declared as paginated against an endpoint that echoes."""

		int_max_pages = None

	df_out = _EchoingReader(_DATE).read()

	assert len(df_out) == 2, "the echoed page must be read once, not once per page number"


def test_read_maps_positional_values_onto_named_columns(_patch_pages: None) -> None:
	"""Values arrive as positional arrays; ``columns`` is what gives them names.

	The regression this guards is silent column misalignment — the worst failure mode here,
	because it produces a plausible frame with the data under the wrong headers.
	"""
	df_out = _SampleBdiReader(_DATE).read()

	assert "TCKR_SYMB" in df_out.columns
	assert "VLM_TRADED_DAY" in df_out.columns
	assert df_out.loc[df_out["TCKR_SYMB"] == "PETR4", "VLM_TRADED_DAY"].iloc[0] == 1.5


def test_read_applies_declared_dtypes(_patch_pages: None) -> None:
	"""Declared dtypes are enforced, never left to pandas' inference."""
	df_out = _SampleBdiReader(_DATE).read()

	assert str(df_out["TCKR_SYMB"].dtype) == "string"
	assert str(df_out["VLM_TRADED_DAY"].dtype) == "float64"


def test_read_stamps_provenance(_patch_pages: None) -> None:
	"""Rows carry the source URL they came from and the dataset's source key."""
	df_out = _SampleBdiReader(_DATE).read()

	assert df_out["url"].str.startswith(BDI_TABLE_BASE).all()
	assert df_out["source_key"].iloc[0] == _CONTRACT.str_source_key


def test_raw_json_pages_are_kept_when_path_raw_is_set(_patch_pages: None, tmp_path: Path) -> None:
	"""Every raw JSON page survives the read — this is the datalake's bronze record.

	The whole point of persisting the untouched payload is that a *future* parser version can
	re-interpret an artifact fetched today. So this asserts the bytes on disk are the API's
	own payload, not a re-serialised or transformed copy.

	Parameters
	----------
	_patch_pages : None
		Fixture patching the download seam.
	tmp_path : pathlib.Path
		pytest-provided directory standing in for a bronze-layer location.
	"""
	path_bronze = tmp_path / "bronze" / "bdi" / "20250102"
	_SampleBdiReader(_DATE, path_raw=path_bronze).read()

	list_pages = sorted(path_bronze.glob("page_*.json"))
	assert len(list_pages) == 3, "two data pages plus the terminating empty page"

	dict_first = json.loads(list_pages[0].read_text(encoding="utf-8"))
	assert dict_first["table"]["values"] == [["PETR4", 1.5], ["VALE3", 2.5]]
	assert dict_first["table"]["columns"][0]["name"] == "TckrSymb", (
		"the ORIGINAL PascalCase name must survive on disk — the snake_case mapping is this "
		"library's interpretation, and a future version must be free to redo it"
	)


def test_content_hash_covers_every_page_not_just_the_first(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Drift on a LATER page changes content_hash — the whole read is fingerprinted.

	The regression this guards, end to end: the base once stamped ``hash_artifact(page_1)``, so
	a source whose first page was byte-identical but whose second page gained a row produced
	the *same* ``content_hash``. The lake would then report "source unchanged" for a source
	that had drifted — a silent failure in the mechanism built to catch silent failures.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam.
	"""

	def _make_download(list_page_two_rows: list[list[object]]) -> object:
		def _fake_download(
			str_url: str,
			path_dest: Path,
			int_timeout_s: int = 30,
			bytes_payload: bytes | None = None,
			str_content_type: str | None = None,
		) -> Path:
			int_page = int(str_url.rstrip("/").split("/")[-2])
			dict_pages = {
				1: _page([["PETR4", 1.5]]),  # identical across both reads
				2: _page(list_page_two_rows),  # this is what drifts
			}
			path_dest.parent.mkdir(parents=True, exist_ok=True)
			path_dest.write_bytes(dict_pages.get(int_page, _page([])))
			return path_dest

		return _fake_download

	monkeypatch.setattr(
		"filings_b3._internal.utils.http_downloader.download_file",
		_make_download([["VALE3", 2.5]]),
	)
	str_hash_before = _SampleBdiReader(_DATE).read()["content_hash"].iloc[0]

	monkeypatch.setattr(
		"filings_b3._internal.utils.http_downloader.download_file",
		_make_download([["VALE3", 2.5], ["ITUB4", 3.5]]),
	)
	str_hash_after = _SampleBdiReader(_DATE).read()["content_hash"].iloc[0]

	assert str_hash_before != str_hash_after


def test_default_workspace_leaves_no_pages_behind(_patch_pages: None) -> None:
	"""Without path_raw the pages are temporary — nothing persists."""
	cls_reader = _SampleBdiReader(_DATE)
	df_out = cls_reader.read()

	assert len(df_out) == 4
	assert cls_reader.path_raw is None


def test_read_raises_contract_error_when_a_required_column_is_missing(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A payload missing a contract column fails before typing.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam.
	"""

	def _fake_download(
		str_url: str,
		path_dest: Path,
		int_timeout_s: int = 30,
		bytes_payload: bytes | None = None,
		str_content_type: str | None = None,
	) -> Path:
		int_page = int(str_url.rstrip("/").split("/")[-2])
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		dict_payload = {
			"table": {
				"columns": [{"name": "TckrSymb"}],  # VlmTradedDay missing
				"values": [["PETR4"]] if int_page == 1 else [],
			}
		}
		path_dest.write_bytes(json.dumps(dict_payload).encode("utf-8"))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)
	with pytest.raises(ContractError, match="VLM_TRADED_DAY"):
		_SampleBdiReader(_DATE).read()


def test_missing_required_attr_raises_at_subclass_definition() -> None:
	"""An adapter omitting a required class attribute fails when the class is created."""
	with pytest.raises(NotImplementedError, match="str_endpoint"):

		class _Incomplete(_BaseBdiReader):
			str_source_key = "incomplete"
			cls_contract = _CONTRACT
			dict_dtypes = {"TCKR_SYMB": "str"}
			# str_endpoint deliberately omitted


def test_build_url_carries_endpoint_date_page_and_size() -> None:
	"""The URL is composed off the shared base, with the session date repeated start/end."""
	str_url = _SampleBdiReader(date(2025, 1, 2)).build_url(3)

	assert str_url == f"{BDI_TABLE_BASE}/DailyAverageStocks/2025-01-02/2025-01-02/3/1000"


def _page_wide(list_rows: list[list[object]], int_extra: int) -> bytes:
	"""Serialize a page whose rows carry ``int_extra`` positions past the named columns."""
	dict_page = {
		"table": {
			"columns": [{"name": "TckrSymb"}, {"name": "VlmTradedDay"}],
			"values": [[*list_row, *([None] * int_extra)] for list_row in list_rows],
		}
	}
	return json.dumps(dict_page).encode("utf-8")


def _patch_bytes(monkeypatch: pytest.MonkeyPatch, bytes_page: bytes) -> None:
	"""Serve one fixed page for page 1 and an empty page afterwards."""

	def _fake_download(
		str_url: str,
		path_dest: Path,
		int_timeout_s: int = 30,  # noqa: ARG001
		bytes_payload: bytes | None = None,  # noqa: ARG001
		str_content_type: str | None = None,  # noqa: ARG001
	) -> Path:
		int_page = int(str_url.rstrip("/").split("/")[-2])
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(bytes_page if int_page == 1 else _page([]))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)


def test_rows_wider_than_the_header_drop_their_empty_tail(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A table shipping more positions than it names still reads, when the surplus is empty.

	`DailyAverageStocks` declares four columns and sends five positions per row, the fifth
	always null, while `EconomicIndicators` matches exactly — so this is per-table, not a
	property of the payload format, and a reader cannot assume either shape.
	"""
	_patch_bytes(monkeypatch, _page_wide([["PETR4", 1.5], ["VALE3", 2.5]], 1))

	df_out = _DefaultPagingReader(_DATE).read()

	assert df_out["TCKR_SYMB"].tolist() == ["PETR4", "VALE3"]


def test_a_value_with_no_column_name_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A populated position past the header is an error, never a silent trim.

	The payload is positional, so a surplus value cannot be named — and dropping it quietly is
	exactly how a source column stops arriving without anything going red.
	"""
	dict_page = {
		"table": {
			"columns": [{"name": "TckrSymb"}, {"name": "VlmTradedDay"}],
			"values": [["PETR4", 1.5, "orphan"]],
		}
	}
	_patch_bytes(monkeypatch, json.dumps(dict_page).encode("utf-8"))

	with pytest.raises(ValueError, match="unnamed tail is not empty"):
		_DefaultPagingReader(_DATE).read()
