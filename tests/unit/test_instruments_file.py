"""Unit tests for the Pesquisa por Pregão instruments-file reader.

The reader downloads ``IN{yymmdd}.zip``. These tests mock the download boundary — the one seam
that touches the network — with a **real B3 sample**:
``tests/fixtures/instruments_IN_sample.zip`` is a 50-record slice of a genuine ``IN260729.zip``,
trimmed to cover all 17 instrument sub-block types (equities, options, futures, fixed income,
international/national bonds, cash, OTC, BTC, ADR, …). Reconciled live against the full file
(issue #143): the row element is ``<Instrm>``, ``RptParams`` is per-record, and a ``*`` wildcard
path resolves whichever sub-block a record carries.

**The fixture reproduces the archive's real shape** (issue #180): a ZIP whose only member is
another ZIP, holding one XML per intraday snapshot — an early partial (40 records,
``CreDtAndTm`` 00:20:11) and the definitive post-close one (all 50, 18:39:48), the later written
first so archive order cannot pass for snapshot selection. The previous fixture was a flat ZIP of
a single XML, a shape B3 never publishes, which is why every reader in the family passed its
tests while failing on every real file.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import shutil
import zipfile

import pytest

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
import filings_b3._internal.utils.http_downloader as http_downloader
from filings_b3.search_trading_session import InstrumentsFileReader


_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "instruments_IN_sample.zip"
# The sample was taken from the 2026-07-29 trading session; every record carries that report date.
_SESSION = date(2026, 7, 29)


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Patch the download seam to drop the real sample ``IN.zip`` where the reader expects it."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		shutil.copy(_FIXTURE, path_dest)
		return path_dest

	monkeypatch.setattr(http_downloader, "download_file", _fake_download)


def test_read_flattens_real_records_types_and_stamps_provenance(_patch_download: None) -> None:
	"""The reader flattens each <Instrm> into a typed, provenance-stamped row from real B3 XML."""
	df_out = InstrumentsFileReader(_SESSION).read()

	assert len(df_out) == 50
	# The per-record report date resolves for every row and is the session date.
	assert (df_out["RPT_DT"] == _SESSION).all()
	# The common attribute block is present on every instrument type, so these never go null.
	for str_col in ("ASST", "ASST_DESC", "SGMT_NM", "MKT_NM"):
		assert df_out[str_col].notna().all(), str_col
	# A known real ticker from the sample resolves via the wildcard.
	assert "AZPL15L" in set(df_out["TCKR_SYMB"])
	# Provenance travels with the data.
	for str_col in INSTRUMENTS_FILE.PROVENANCE_COLUMNS:
		assert str_col in df_out.columns
	assert (df_out["source_key"] == "instruments_file").all()


def test_wildcard_resolves_ticker_isin_for_every_type_that_carries_them(
	_patch_download: None,
) -> None:
	"""TCKR_SYMB / ISIN are null only for the instrument types that genuinely lack them.

	The 50-record sample over-samples exotic types. Five sub-blocks (CshInf, FICInf, IntlBdInf,
	NtlBdInf, OTCInf) carry no ``TckrSymb`` and four (BTCInf, CshInf, FICInf, OTCInf) no ``ISIN`` —
	so those rows are legitimately null, never a wildcard miss. This pins that the wildcard
	resolves the field for **every** type that has it (36 tickers, 39 ISINs in this sample).
	"""
	df_out = InstrumentsFileReader(_SESSION).read()

	assert int(df_out["TCKR_SYMB"].notna().sum()) == 36
	assert int(df_out["ISIN"].notna().sum()) == 39


def test_decimal_columns_stay_exact(_patch_download: None) -> None:
	"""A contract-multiplier value keeps its exact source scale — never a lossy binary float."""
	df_out = InstrumentsFileReader(_SESSION).read()

	series_mult = df_out["CTRCT_MLTPLR"].dropna()
	if not series_mult.empty:  # futures/options carry a multiplier; the sample includes them
		assert all(isinstance(v, Decimal) for v in series_mult)


def test_monetary_values_carry_their_own_currency_attribute(_patch_download: None) -> None:
	"""Every monetary value ships the ``@Ccy`` attribute beside it, never bare (#147).

	In ISO-20022 the currency of a value is an *attribute* of the value element
	(``<ExrcPric Ccy="BRL">27.35</ExrcPric>``), so a path that reads element text cannot see it and
	the consolidated reader silently dropped it.

	``TRADG_CCY`` is **not** a substitute. Measured on a real ``IN260729``: 1,074 values carry a
	``@Ccy`` while their record has no ``TradgCcy`` at all — ``IssePric`` in USD/EUR/MXN/XXX,
	``MtrtyVal``, ``BaseDtPric``. For those the currency is simply unrecoverable without reading
	the attribute, so the companion columns are the only correct answer.
	"""
	df_out = InstrumentsFileReader(_SESSION).read()

	for str_value, str_ccy in (("EXRC_PRIC", "EXRC_PRIC_CCY"), ("MKT_CPTLSTN", "MKT_CPTLSTN_CCY")):
		series_present = df_out[str_value].notna()
		assert series_present.any(), f"{str_value} absent from the sample — fixture drifted"
		assert not (series_present & df_out[str_ccy].isna()).any(), (
			f"{str_value} has a value with no {str_ccy} — the currency attribute was dropped"
		)
		# A currency without a value would mean the attribute path resolved off the wrong element.
		assert not (df_out[str_ccy].notna() & ~series_present).any(), str_ccy


def test_currency_columns_are_iso_4217_codes(_patch_download: None) -> None:
	"""The currency companions carry ISO-4217 codes, not the numeric value they belong to.

	Guards the attribute path resolving to the element's *text* instead of its attribute — which
	would silently fill the column with prices and still look populated.
	"""
	df_out = InstrumentsFileReader(_SESSION).read()

	for str_ccy in ("EXRC_PRIC_CCY", "MKT_CPTLSTN_CCY"):
		set_values = set(df_out[str_ccy].dropna())
		assert set_values, f"{str_ccy} entirely null — the attribute path did not resolve"
		assert all(len(v) == 3 and v.isalpha() for v in set_values), f"{str_ccy}: {set_values}"


def test_build_url_is_date_addressed() -> None:
	"""The download URL carries the session date as ``IN{yymmdd}.zip``."""
	str_url = InstrumentsFileReader(date(2025, 1, 2)).build_url()

	assert str_url.endswith("filelist=IN250102.zip")


def test_read_raises_when_archive_holds_no_xml(monkeypatch: pytest.MonkeyPatch) -> None:
	"""An archive with no XML member anywhere fails loudly, never guesses a member."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		with zipfile.ZipFile(path_dest, "w") as cls_zip:
			cls_zip.writestr("readme.txt", "not xml")
		return path_dest

	monkeypatch.setattr(http_downloader, "download_file", _fake_download)

	with pytest.raises(ValueError, match="no .xml member"):
		InstrumentsFileReader(date(2025, 1, 2)).read()


def test_read_takes_the_latest_snapshot_of_the_session(_patch_download: None) -> None:
	"""Of the archive's intraday snapshots, the one with the greatest CreDtAndTm is read.

	The snapshots are cumulative — measured on a real ``IN260729``, the post-close file held all
	183,164 instruments of the pre-open one plus 10 more, and removed none. Reading the earlier
	snapshot therefore drops the session's late registrations without any error. The fixture
	mirrors that: 40 records early, all 50 late, and the *late* one written first in the archive
	so a reader that took the first member (or the last) would land on the wrong count here.
	"""
	df_out = InstrumentsFileReader(_SESSION).read()

	assert len(df_out) == 50
	# These tickers are absent from the early snapshot, so they land only when the late one wins.
	assert {"CMIG3 BZ", "GFSA3 BZ", "OTCGOVSPEC"} <= set(df_out["TCKR_SYMB"])


def test_read_raises_when_a_snapshot_does_not_declare_its_generation_time(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A snapshot with no CreDtAndTm fails loudly — an undated snapshot cannot be ordered."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		buf_inner = io.BytesIO()
		with zipfile.ZipFile(buf_inner, "w") as cls_inner:
			cls_inner.writestr("BVBG.028.02_UNDATED.xml", "<Document><BizFileHdr/></Document>")
		with zipfile.ZipFile(path_dest, "w") as cls_outer:
			cls_outer.writestr("IN250102.zip", buf_inner.getvalue())
		return path_dest

	monkeypatch.setattr(http_downloader, "download_file", _fake_download)

	with pytest.raises(ValueError, match="no <CreDtAndTm>"):
		InstrumentsFileReader(date(2025, 1, 2)).read()
