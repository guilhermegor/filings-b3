"""BVBG.028 UP2DATA instruments-layout metadata reader.

B3 publishes the **authoritative field layout** of the BVBG.028 instruments family as an XLSX
(``BVBG.028 para UP2DATA.xlsx``) — one sheet per file type, each row a field with its name, tag
abbreviation, cardinality, data type, and BVBG.028 XML path. This reader downloads that asset and
parses the ``InstrumentsConsolidatedFile`` sheet (the layout of the Pesquisa por Pregão ``IN``
file) into a typed **layout snapshot**: one row per declared field, with the canonical
``UPPER_SNAKE`` column name derived exactly as the data readers derive theirs
(``pascal_to_upper_snake`` of the tag abbreviation).

Two uses:

- **Datalake snapshot** — a versionable record of B3's published layout, carrying provenance and
  the ``content_hash`` of the raw XLSX, so a datalake keeps the history of how the spec changed.
- **Contract-drift oracle** — ``bin/check_contract_drift.py`` reads the ``CANONICAL_COLUMN`` set
  and compares it to the shipped ``INSTRUMENTS_FILE`` contract, opening an issue when B3 adds or
  removes a field.

The metadata is a **spreadsheet**, so this reuses the tabular seam (``read_table``: the sheet's
header sits on the second row — the first is the sheet title — hence ``int_header_row=1``) rather
than the XML seam. It implements the ``IngestionReader`` port directly; the layout is a current
snapshot, so there is no ``date_ref``.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pandas as pd

from filings_b3._internal.config.contracts import INSTRUMENTS_LAYOUT_META
from filings_b3._internal.config.ports.ingestion_reader import IngestionReader
from filings_b3._internal.utils.dtypes import apply_dtypes
from filings_b3._internal.utils.provenance import (
	hash_artifact,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.raw_workspace import raw_workspace
from filings_b3._internal.utils.retry import LogEmitter, RetryPolicy
from filings_b3._internal.utils.tabular_reader import read_table
from filings_b3._internal.utils.text import pascal_to_upper_snake


_DISTRIBUTION_NAME = "filings-b3"

# B3's authoritative BVBG.028 field-mapping spreadsheet (the "para UP2DATA" layout). A B3 URL move
# is a single-point-of-change here — the drift job would fail to download and simply skip, never
# false-report drift.
_LAYOUT_XLSX_URL = (
	"https://www.b3.com.br/data/files/1A/45/CC/29/4C11881036DB3088AC094EA8/"
	"BVBG.028%20para%20UP2DATA.xlsx"
)

# Source (Portuguese) header column → canonical snapshot column. Only the columns the snapshot
# keeps; the sheet's remaining columns (examples, descriptions, notes) are dropped.
_COLUMN_RENAMES = {
	"Coluna": "COLUMN_ORDER",
	"Campo": "FIELD_NAME",
	"Abreviação do Campo": "FIELD_ABBREVIATION",
	"Card.": "CARDINALITY",
	"Tipo de Dado": "DATA_TYPE",
	"Campo no BVBG.028": "BVBG_PATH",
}


class InstrumentsLayoutMetaReader(IngestionReader):
	"""Reader for B3's BVBG.028 UP2DATA instruments-layout metadata (a snapshot, not a dataset).

	Downloads the UP2DATA XLSX, parses its :attr:`str_sheet` sheet into one layout row per field,
	derives the canonical ``UPPER_SNAKE`` column name from each tag abbreviation, and stamps
	provenance. No persistence — the frame is returned.

	Parameters
	----------
	path_raw : pathlib.Path, optional
		Directory in which to **keep** the downloaded raw ``.xlsx`` (the datalake's bronze layer).
		``None`` (default) uses a temporary directory removed on exit.
	cls_logger : LogEmitter, optional
		Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
	cls_retry_policy : RetryPolicy, optional
		Injected retry/backoff schedule for the download; ``None`` uses the seam's own default.

	Attributes
	----------
	str_sheet : str
		The UP2DATA sheet to parse. Subclass and override to read a sibling file type's layout.
	"""

	str_sheet: ClassVar[str] = "InstrumentsConsolidatedFile"

	def __init__(
		self,
		path_raw: Path | None = None,
		cls_logger: LogEmitter | None = None,
		cls_retry_policy: RetryPolicy | None = None,
	) -> None:
		self.path_raw = path_raw
		self._cls_logger = cls_logger if cls_logger is not None else LogEmitter()
		self._cls_retry_policy = cls_retry_policy

	def read(self) -> pd.DataFrame:
		"""Download and parse the layout sheet into a typed, provenance-stamped snapshot.

		Returns
		-------
		pd.DataFrame
			One row per declared field: ``COLUMN_ORDER`` (Int64), ``FIELD_NAME``,
			``FIELD_ABBREVIATION``, ``CANONICAL_COLUMN``, ``CARDINALITY``, ``DATA_TYPE``,
			``BVBG_PATH``, plus the provenance columns.

		Raises
		------
		ContractError
			When the sheet does not carry the expected layout header.
		"""
		from filings_b3._internal.utils.http_downloader import download_file, url_filename

		with raw_workspace(self.path_raw) as path_dir:
			path_xlsx = download_file(_LAYOUT_XLSX_URL, path_dir / url_filename(_LAYOUT_XLSX_URL))
			self._cls_logger.log_message(
				f"downloaded instruments_layout_meta from {_LAYOUT_XLSX_URL}", "info"
			)
			df_raw = read_table(
				path_xlsx,
				self.str_sheet,
				dict.fromkeys(_COLUMN_RENAMES, "str"),
				INSTRUMENTS_LAYOUT_META,
				int_header_row=1,
			)
			df_snapshot = self._build_snapshot(df_raw)
			return stamp_provenance(
				df_snapshot,
				_LAYOUT_XLSX_URL,
				INSTRUMENTS_LAYOUT_META,
				hash_artifact(path_xlsx),
				resolve_package_version(_DISTRIBUTION_NAME),
			)

	def _build_snapshot(self, df_raw: pd.DataFrame) -> pd.DataFrame:
		"""Select, rename, drop blank rows, derive canonical names, and type the layout frame.

		Parameters
		----------
		df_raw : pd.DataFrame
			The sheet as read (Portuguese headers, all text).

		Returns
		-------
		pd.DataFrame
			The clean layout snapshot (source columns only; provenance is stamped by the caller).
		"""
		df_snapshot = df_raw[list(_COLUMN_RENAMES)].rename(columns=_COLUMN_RENAMES)
		# Drop the sheet's trailing/blank rows — a real field row always names a field.
		df_snapshot = df_snapshot[df_snapshot["FIELD_NAME"].notna()].copy()
		df_snapshot["CANONICAL_COLUMN"] = df_snapshot["FIELD_ABBREVIATION"].map(
			pascal_to_upper_snake
		)
		df_snapshot = apply_dtypes(df_snapshot, dict_dtypes={"COLUMN_ORDER": "Int64"})
		return df_snapshot[
			[
				"COLUMN_ORDER",
				"FIELD_NAME",
				"FIELD_ABBREVIATION",
				"CANONICAL_COLUMN",
				"CARDINALITY",
				"DATA_TYPE",
				"BVBG_PATH",
			]
		]
