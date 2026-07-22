"""Unit tests for the BDI daily average stocks summary reader.

The lifecycle itself is covered by ``test_base_bdi_reader``; what matters here is that this
reader **declares** the right things — endpoint, contract, dtypes, pagination mode — and that
its declarations actually produce a correct frame end to end, offline.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from filings_b3._internal.config.contracts import BDI_STOCKS_SUMMARY
from filings_b3.daily_bulletin import BdiStocksSummaryReader


_DATE = date(2025, 1, 2)


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Serve one page shaped like B3's DailyAverageStocks payload.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam at its own module boundary.
	"""
	dict_payload = {
		"table": {
			"columns": [
				{"name": "TckrSymb"},
				{"name": "NmbrTradesDay"},
				{"name": "VlmTradedDay"},
				{"name": "ColOrder"},
			],
			"values": [
				["PETR4", 125_430, 1_984_223_115.42, 1],
				["VALE3", 98_211, 1_233_004_910.10, 2],
			],
		}
	}

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 30) -> Path:
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(json.dumps(dict_payload).encode("utf-8"))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)


def test_reader_targets_the_daily_average_stocks_endpoint() -> None:
	"""The URL names B3's DailyAverageStocks table for the requested session."""
	str_url = BdiStocksSummaryReader(_DATE).build_url(1)

	assert "/DailyAverageStocks/" in str_url
	assert "/2025-01-02/2025-01-02/" in str_url


def test_reader_is_declared_single_page() -> None:
	"""Answering in one response, this endpoint must keep the single-page default.

	Declared explicitly as a test because getting it wrong towards ``None`` on an echoing
	endpoint multiplies the dataset — a corruption every row would survive a contract check.
	"""
	assert BdiStocksSummaryReader.int_max_pages == 1


def test_read_returns_the_contract_columns_typed(_patch_download: None) -> None:
	"""The frame carries the contract's columns, typed as declared, plus provenance."""
	df_out = BdiStocksSummaryReader(_DATE).read()

	assert len(df_out) == 2
	for str_col in BDI_STOCKS_SUMMARY.output_columns:
		assert str_col in df_out.columns
	assert str(df_out["TCKR_SYMB"].dtype) == "string"
	assert str(df_out["NMBR_TRADES_DAY"].dtype) == "Int64"
	assert str(df_out["VLM_TRADED_DAY"].dtype) == "float64"


def test_every_source_column_is_explicitly_typed(_patch_download: None) -> None:
	"""No column reaches the frame with a pandas-inferred dtype.

	The contract lists only what a consumer depends on, so a source column outside it — here
	``COL_ORDER`` — still passes through to the datalake. If it were absent from
	``dict_dtypes`` its type would be whatever pandas guessed from the first page's values,
	which can differ between sessions (an all-integer page vs one with a null). Typing every
	source column is what keeps the bronze schema stable across runs.
	"""
	df_out = BdiStocksSummaryReader(_DATE).read()
	set_provenance = set(BDI_STOCKS_SUMMARY.PROVENANCE_COLUMNS)
	set_source_cols = {str_col for str_col in df_out.columns if str_col not in set_provenance}

	assert set_source_cols == set(BdiStocksSummaryReader.dict_dtypes), (
		"every column the source sends must be declared in dict_dtypes"
	)
	assert str(df_out["COL_ORDER"].dtype) == "Int64"


def test_read_preserves_the_source_values(_patch_download: None) -> None:
	"""Values land under the right names — the positional mapping is not scrambled."""
	df_out = BdiStocksSummaryReader(_DATE).read()
	dict_petr = df_out[df_out["TCKR_SYMB"] == "PETR4"].iloc[0]

	assert dict_petr["NMBR_TRADES_DAY"] == 125_430
	assert dict_petr["VLM_TRADED_DAY"] == pytest.approx(1_984_223_115.42)


def test_read_stamps_this_readers_source_key(_patch_download: None) -> None:
	"""Provenance carries this dataset's key, so bronze rows are attributable."""
	df_out = BdiStocksSummaryReader(_DATE).read()

	assert (df_out["source_key"] == "bdi_stocks_summary").all()
	assert df_out["url"].iloc[0].endswith("/1/1000")


def test_reader_is_exported_from_the_package_root() -> None:
	"""A consumer imports from the package root, never from the section module path."""
	import filings_b3

	assert filings_b3.BdiStocksSummaryReader is BdiStocksSummaryReader
	assert "BdiStocksSummaryReader" in filings_b3.__all__
