"""Unit tests for the BVBG.028 UP2DATA instruments-layout metadata reader.

The reader downloads B3's ``BVBG.028 para UP2DATA.xlsx`` and parses its
``InstrumentsConsolidatedFile`` sheet into a typed layout snapshot (one row per field: the field
name, its tag abbreviation, the canonical column name, cardinality, data type, XML path) with
provenance. These tests mock the download with a **synthetic** minimal XLSX shaped like the real
sheet — a title row, a header row, then a few field rows and a trailing blank — so the parse is
pinned without the live 227 KB asset.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

import filings_b3._internal.utils.http_downloader as http_downloader
from filings_b3.search_trading_session import InstrumentsLayoutMetaReader


_HEADER = [
	"Coluna",
	"Campo",
	"Abreviação do Campo",
	"Card.",
	"Tipo de Dado",
	"Detalhe do Tipo de Dado",
	"Descrição",
	"Campo no BVBG.028",
	"Exemplo UP2DATA",
	"Exemplo BVBG.028",
	"Observações",
]
_ROWS = [
	[1, "ReportDate", "RptDt", "[1..1]", "ISODate", "date", "", "<RptParams>", "2022", "", ""],
	[
		2,
		"TickerSymbol",
		"TckrSymb",
		"[1..1]",
		"TickerIdentifier",
		"",
		"",
		"<EqtyInf>",
		"B3SA3",
		"",
		"",
	],
	[16, "CFICode", "CFICd", "[1..1]", "Max6Text", "", "", "<EqtyInf>", "FFFCSX", "", ""],
	[None, None, None, None, None, None, None, None, None, None, None],  # trailing blank row
]


def _write_xlsx(path_dest: Path) -> Path:
	cls_wb = openpyxl.Workbook()
	cls_ws = cls_wb.active
	cls_ws.title = "InstrumentsConsolidatedFile"
	cls_ws.append(["InstrumentsConsolidatedFile"])  # row 0: sheet title
	cls_ws.append(_HEADER)  # row 1: header
	for list_row in _ROWS:
		cls_ws.append(list_row)
	cls_wb.save(path_dest)
	return path_dest


@pytest.fixture
def _patch_download(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Patch the download seam to drop a synthetic UP2DATA XLSX where the reader expects it."""

	def _fake(str_url: str, path_dest: Path, int_timeout_s: int = 0) -> Path:  # noqa: ARG001
		return _write_xlsx(path_dest)

	monkeypatch.setattr(http_downloader, "download_file", _fake)


def test_read_parses_layout_rows_with_canonical_names_and_provenance(
	_patch_download: None,
) -> None:
	"""Each field row becomes a layout row; the canonical column matches the library convention."""
	df_out = InstrumentsLayoutMetaReader().read()

	# Trailing blank row is dropped — only the three real fields remain.
	assert list(df_out["FIELD_NAME"]) == ["ReportDate", "TickerSymbol", "CFICode"]
	# The canonical column derives from the tag abbreviation, matching the instruments contract.
	assert list(df_out["CANONICAL_COLUMN"]) == ["RPT_DT", "TCKR_SYMB", "CFICD"]
	assert list(df_out["COLUMN_ORDER"]) == [1, 2, 16]
	assert list(df_out["BVBG_PATH"]) == ["<RptParams>", "<EqtyInf>", "<EqtyInf>"]
	# Provenance travels with the snapshot.
	assert (df_out["source_key"] == "instruments_layout_meta").all()
	assert "content_hash" in df_out.columns


def test_canonical_columns_cover_the_instruments_contract(_patch_download: None) -> None:
	"""Every canonical name the reader derives is a real UPPER_SNAKE column (no empty/NaN)."""
	df_out = InstrumentsLayoutMetaReader().read()

	assert all(str_col.isupper() and str_col for str_col in df_out["CANONICAL_COLUMN"])
