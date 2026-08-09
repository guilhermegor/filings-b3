"""Unit tests for the BDI exchange-rate history reader (Resolução BCB nº 120).

The lifecycle itself is covered by ``test_base_bdi_reader``; what matters here is that this
reader **declares** the right things — endpoint, contract, renames, dtypes — and that those
declarations produce a correct frame end to end, offline.

The payload fixture is copied from a live ``HistoricalExchange`` response, **including its two
quirks**: the API publishes the asset under ``TckrSymb`` and the instrument under ``Symb`` (the
reverse of the glossary), and it pads two of the field names with a trailing space. Both are
real, both are per-table, and a fixture that tidied them would test a source B3 does not serve.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest

from filings_b3._internal.config.contracts import BDI_HISTORICAL_EXCHANGE
from filings_b3.daily_bulletin import BdiHistoricalExchangeReader


_DATE = date(2026, 8, 7)


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Serve one page shaped exactly like B3's HistoricalExchange payload.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Fixture used to replace the download seam at its own module boundary.
	"""
	dict_payload = {
		"table": {
			"columns": [
				{"name": "RptDt"},
				{"name": "TckrSymb"},  # holds the ASSET, per the live response
				{"name": "Symb "},  # padded by the source, and holds the INSTRUMENT
				{"name": "EcncIndDesc"},
				{"name": "PricVal "},  # padded by the source
			],
			"values": [
				["2026-08-07T00:00:00", "DOL", "RTDOLD2", "Indicadores gerais", 5.0819],
				["2026-08-07T00:00:00", "DOL", "RTDOLD1", "Indicador Econômico", 5.0808],
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


def test_read_publishes_the_glossary_semantics_not_the_api_naming(_patch_download: None) -> None:
	"""The asset lands in ``ASST`` and the instrument in ``TCKR_SYMB`` — the glossary's meaning.

	The endpoint names these two fields the other way round. Publishing its naming would make
	``TCKR_SYMB`` hold an *asset* here while it holds an *instrument* in every
	``search_trading_session`` reader, so joining the two on that column would match ``DOL``
	against instrument tickers and return silence rather than an error (#165).
	"""
	df_out = BdiHistoricalExchangeReader(_DATE).read()

	assert df_out["ASST"].tolist() == ["DOL", "DOL"]
	assert df_out["TCKR_SYMB"].tolist() == ["RTDOLD2", "RTDOLD1"]


def test_read_strips_the_padding_the_source_puts_on_field_names(_patch_download: None) -> None:
	"""A padded source field yields an addressable column, not one with a trailing space.

	``PricVal `` arrives padded on this table (and not on its siblings). Left alone it produces a
	column that *prints* as ``PRIC_VAL`` while only ``df["PRIC_VAL "]`` reaches it — so the
	contract's required column reads as missing and every consumer lookup raises ``KeyError``.
	"""
	df_out = BdiHistoricalExchangeReader(_DATE).read()

	assert [str_col for str_col in df_out.columns if str_col != str_col.strip()] == []
	assert "PRIC_VAL" in df_out.columns


def test_rates_keep_their_exact_source_scale(_patch_download: None) -> None:
	"""An exchange rate stays an exact ``Decimal`` at the scale the source published it.

	The rate multiplies notionals, so its fractional part is the entire content. Measured on
	live sessions, B3 publishes rates at differing scales on the same instrument (``5.16`` and
	``5.162``); a ``float64`` cannot represent either exactly and silently loses the scale.
	"""
	df_out = BdiHistoricalExchangeReader(_DATE).read()

	assert all(isinstance(obj_val, Decimal) for obj_val in df_out["PRIC_VAL"])
	assert str(df_out["PRIC_VAL"].iloc[0]) == "5.0819"


def test_read_types_the_session_date_and_stamps_provenance(_patch_download: None) -> None:
	"""The report date is a real date and the rows carry where they came from."""
	df_out = BdiHistoricalExchangeReader(_DATE).read()

	assert df_out["RPT_DT"].tolist() == [_DATE, _DATE]
	assert (df_out["source_key"] == BDI_HISTORICAL_EXCHANGE.str_source_key).all()
	assert df_out["url"].str.contains("HistoricalExchange").all()


def test_reader_declares_the_resolution_120_endpoint() -> None:
	"""The endpoint is the exchange-rate history table, not the broader indicators one.

	``EconomicIndicators`` is a different table — 300 distinct indicators across currencies,
	commodities and indices — and was the dataset this work originally aimed at by mistake.
	"""
	assert BdiHistoricalExchangeReader.str_endpoint == "HistoricalExchange"
	assert BdiHistoricalExchangeReader.int_max_pages == 1
