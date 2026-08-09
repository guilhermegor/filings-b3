"""Unit tests for the BDI securities-lending open positions reader.

The lifecycle itself is covered by ``test_base_bdi_reader``; what matters here is that this
reader **declares** the right things — endpoint, contract, dtypes, pagination mode — and that
its declarations actually produce a correct frame end to end, offline.

The fixture payload mirrors a **live** ``BTBLendingOpenPosition`` response: ten columns whose
codes (``RptDt``, ``DtRef``, ``TckrSymb`` …) are exactly what the JSON API returns, including
the two leading date columns the stpstone port dropped.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest

from filings_b3._internal.config.contracts import BDI_BTB_LENDING_OPEN_POSITIONS
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader


_DATE = date(2025, 1, 2)


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Serve one page shaped like a live B3 BTBLendingOpenPosition payload.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam at its own module boundary.
	"""
	dict_payload = {
		"table": {
			"columns": [
				{"name": "RptDt"},
				{"name": "DtRef"},
				{"name": "TckrSymb"},
				{"name": "ISIN"},
				{"name": "Company"},
				{"name": "Type"},
				{"name": "Market"},
				{"name": "StockBalance"},
				{"name": "AvgPric"},
				{"name": "Balance"},
			],
			"values": [
				[
					"2025-01-02T00:00:00",
					"2025-01-02T00:00:00",
					"PETR4",
					"BRPETRACNPR6",
					"PETROBRAS",
					"PN",
					"Registro",
					1_250_000,
					38.4712,
					48_089_000.55,
				],
				[
					"2025-01-02T00:00:00",
					"2025-01-02T00:00:00",
					"VALE3",
					"BRVALEACNOR0",
					"VALE",
					"ON",
					"Neg. Eletrônica D+1",
					980_000,
					61.1900,
					59_966_200.10,
				],
			],
		}
	}

	def _fake_download(
		str_url: str,
		path_dest: Path,
		int_timeout_s: int = 30,
		bytes_payload: bytes | None = None,
		str_content_type: str | None = None,
	) -> Path:
		path_dest.parent.mkdir(parents=True, exist_ok=True)
		path_dest.write_bytes(json.dumps(dict_payload).encode("utf-8"))
		return path_dest

	monkeypatch.setattr("filings_b3._internal.utils.http_downloader.download_file", _fake_download)


def test_reader_targets_the_btb_lending_open_position_endpoint() -> None:
	"""The URL names B3's BTBLendingOpenPosition table for the requested session."""
	str_url = BdiBtbLendingOpenPositionsReader(_DATE).build_url(1)

	assert "/BTBLendingOpenPosition/" in str_url
	assert "/2025-01-02/2025-01-02/" in str_url


def test_reader_is_declared_single_page() -> None:
	"""Answering in one response, this endpoint must keep the single-page default.

	Declared explicitly as a test because getting it wrong towards ``None`` on an echoing
	endpoint multiplies the dataset — a corruption every row would survive a contract check.
	"""
	assert BdiBtbLendingOpenPositionsReader.int_max_pages == 1


def test_read_returns_the_contract_columns_typed(_patch_download: None) -> None:
	"""The frame carries the contract's columns, typed as declared, plus provenance."""
	df_out = BdiBtbLendingOpenPositionsReader(_DATE).read()

	assert len(df_out) == 2
	for str_col in BDI_BTB_LENDING_OPEN_POSITIONS.output_columns:
		assert str_col in df_out.columns
	assert str(df_out["TCKR_SYMB"].dtype) == "string"
	assert str(df_out["STOCK_BALANCE"].dtype) == "Int64"
	assert df_out["DT_REF"].iloc[0] == date(2025, 1, 2)
	assert df_out["RPT_DT"].iloc[0] == date(2025, 1, 2)
	assert all(isinstance(cls_v, Decimal) for cls_v in df_out["AVG_PRIC"])
	assert all(isinstance(cls_v, Decimal) for cls_v in df_out["BALANCE"])


def test_every_source_column_is_explicitly_typed(_patch_download: None) -> None:
	"""No column reaches the frame with a pandas-inferred dtype.

	The contract lists only what a consumer depends on, so a source column outside it still
	passes through to the datalake. If it were absent from ``dict_dtypes`` / ``list_date_cols``
	/ ``list_decimal_cols`` its type would be whatever pandas guessed from the first page's
	values, which can differ between sessions. Typing every source column — including the two
	date columns the stpstone port dropped — is what keeps the bronze schema stable across runs.
	"""
	df_out = BdiBtbLendingOpenPositionsReader(_DATE).read()
	set_provenance = set(BDI_BTB_LENDING_OPEN_POSITIONS.PROVENANCE_COLUMNS)
	set_source_cols = {str_col for str_col in df_out.columns if str_col not in set_provenance}
	set_declared = (
		set(BdiBtbLendingOpenPositionsReader.dict_dtypes)
		| set(BdiBtbLendingOpenPositionsReader.list_date_cols)
		| set(BdiBtbLendingOpenPositionsReader.list_decimal_cols)
	)

	assert set_source_cols == set_declared, (
		"every column the source sends must be declared in "
		"dict_dtypes / list_date_cols / list_decimal_cols"
	)


def test_read_preserves_the_source_values(_patch_download: None) -> None:
	"""Values land under the right names — the positional mapping is not scrambled."""
	df_out = BdiBtbLendingOpenPositionsReader(_DATE).read()
	dict_petr = df_out[df_out["TCKR_SYMB"] == "PETR4"].iloc[0]

	assert dict_petr["ISIN"] == "BRPETRACNPR6"
	assert dict_petr["STOCK_BALANCE"] == 1_250_000
	assert dict_petr["BALANCE"] == Decimal("48089000.55")


def test_money_columns_are_exact_not_approximate(_patch_download: None) -> None:
	"""Average price and balance equal the source **exactly** — no tolerance, no drift.

	This is the assertion a ``float64`` column cannot pass. Parsed as a binary float, the
	source's exact decimal becomes a slightly different number: close enough to print
	correctly, wrong enough that summing a session's positions and reconciling against B3's
	published total misses by a hair, with nothing to point at. The equality here is exact —
	``pytest.approx`` would defeat the purpose of the test.
	"""
	df_out = BdiBtbLendingOpenPositionsReader(_DATE).read()

	assert df_out["AVG_PRIC"].iloc[0] == Decimal("38.4712")
	assert df_out["BALANCE"].iloc[0] == Decimal("48089000.55")
	# Summing money must stay exact too — this is what the warehouse will do.
	assert sum(df_out["BALANCE"]) == Decimal("108055200.65")


def test_read_stamps_this_readers_source_key(_patch_download: None) -> None:
	"""Provenance carries this dataset's key, so bronze rows are attributable."""
	df_out = BdiBtbLendingOpenPositionsReader(_DATE).read()

	assert (df_out["source_key"] == "bdi_btb_lending_open_positions").all()
	assert df_out["url"].iloc[0].endswith("/1/1000")


def test_reader_is_exported_from_its_section_and_not_from_the_root() -> None:
	"""A consumer imports from the macro-section — the flat root export was removed in 0.2.0.

	Inverted from the #122 contract by #163: the section path is now the only public one, so the
	root must NOT resolve the name (a re-export would quietly restore the flat surface).
	"""
	import filings_b3
	from filings_b3 import daily_bulletin

	assert daily_bulletin.BdiBtbLendingOpenPositionsReader is BdiBtbLendingOpenPositionsReader
	assert "BdiBtbLendingOpenPositionsReader" in daily_bulletin.__all__
	assert not hasattr(filings_b3, "BdiBtbLendingOpenPositionsReader")
	assert "BdiBtbLendingOpenPositionsReader" not in filings_b3.__all__
