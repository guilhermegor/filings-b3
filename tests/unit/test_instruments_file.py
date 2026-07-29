"""Unit tests for the Pesquisa por Pregão instruments-file reader.

The reader downloads ``IN{yymmdd}.zip`` (a ZIP of one BVBG.028.02 XML). These tests mock the
download boundary — the one seam that touches the network — with a **synthetic** ZIP holding a
minimal two-record XML (an equity and a future, whose fields live under different sub-blocks), so
the reader's compose-and-type behaviour is pinned without a live B3 file. The exact XML structure
and column casing are reconciled against a real file before merge (issue #68).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import zipfile

import pytest

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
import filings_b3._internal.utils.http_downloader as http_downloader
from filings_b3.search_trading_session import InstrumentsFileReader


_NS = "urn:bvmf.100.02.xsd"

_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="{_NS}">
  <BizGrp>
    <RptParams><RptDtAndTm><Dt>2025-01-02</Dt></RptDtAndTm></RptParams>
    <InstrmRcrd>
      <FinInstrmAttrCmon><Asst>PETR</Asst><AsstDesc>Petrobras</AsstDesc>
        <Sgmt>EQUITY</Sgmt><Mkt>CASH</Mkt></FinInstrmAttrCmon>
      <InstrmInf><EqtyInf><TckrSymb>PETR4</TckrSymb><ISIN>BRPETRACNPR6</ISIN>
        <AllcnRndLot>100</AllcnRndLot><CrpnNm>PETROLEO BRASILEIRO SA</CrpnNm></EqtyInf></InstrmInf>
    </InstrmRcrd>
    <InstrmRcrd>
      <FinInstrmAttrCmon><Asst>DOL</Asst><AsstDesc>Dolar</AsstDesc>
        <Sgmt>FINANCIAL</Sgmt><Mkt>FUTURE</Mkt></FinInstrmAttrCmon>
      <InstrmInf><FutrCtrctsInf><TckrSymb>DOLF25</TckrSymb><ISIN>BRBMEFDOL250</ISIN>
        <AllcnRndLot>5</AllcnRndLot><CtrctMltplr>50.00025</CtrctMltplr>
        <XprtnDt>2025-01-02</XprtnDt></FutrCtrctsInf></InstrmInf>
    </InstrmRcrd>
  </BizGrp>
</Document>
"""


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Patch the download seam to drop a synthetic ``IN.zip`` where the reader expects it."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		with zipfile.ZipFile(path_dest, "w") as cls_zip:
			cls_zip.writestr("IN250102.xml", _XML)
		return path_dest

	monkeypatch.setattr(http_downloader, "download_file", _fake_download)


def test_read_flattens_records_types_and_stamps_provenance(_patch_download: None) -> None:
	"""Each instrument record becomes one typed, provenance-stamped row."""
	df_out = InstrumentsFileReader(date(2025, 1, 2)).read()

	assert list(df_out["TCKR_SYMB"]) == ["PETR4", "DOLF25"]
	assert list(df_out["ISIN"]) == ["BRPETRACNPR6", "BRBMEFDOL250"]
	# Scalar report date broadcasts to every row and is a real date.
	assert list(df_out["RPT_DT"]) == [date(2025, 1, 2), date(2025, 1, 2)]
	# The future's multiplier is exact Decimal; the equity has none.
	assert df_out.loc[1, "CTRCT_MLTPLR"] == Decimal("50.00025")
	assert str(df_out.loc[1, "CTRCT_MLTPLR"]) == "50.00025"
	# Provenance travels with the data.
	for str_col in INSTRUMENTS_FILE.PROVENANCE_COLUMNS:
		assert str_col in df_out.columns
	assert (df_out["source_key"] == "instruments_file").all()


def test_build_url_is_date_addressed() -> None:
	"""The download URL carries the session date as ``IN{yymmdd}.zip``."""
	str_url = InstrumentsFileReader(date(2025, 1, 2)).build_url()

	assert str_url.endswith("filelist=IN250102.zip")


def test_read_raises_when_archive_has_no_single_xml(monkeypatch: pytest.MonkeyPatch) -> None:
	"""An archive without exactly one XML member fails loudly, never guesses a member."""

	def _fake_download(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		with zipfile.ZipFile(path_dest, "w") as cls_zip:
			cls_zip.writestr("readme.txt", "not xml")
		return path_dest

	monkeypatch.setattr(http_downloader, "download_file", _fake_download)

	with pytest.raises(ValueError, match="exactly one .xml"):
		InstrumentsFileReader(date(2025, 1, 2)).read()
