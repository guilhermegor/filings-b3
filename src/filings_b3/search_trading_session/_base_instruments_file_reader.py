"""Shared lifecycle for every reader of B3's instruments file ``IN{yymmdd}.zip`` (BVBG.028.02).

One download, many datasets. B3 serves the whole trading session's instrument registry as a
single ISO-20022 XML: one ``<Instrm>`` record per instrument, whose type-specific fields nest
under exactly **one** of 20 ``<InstrmInf>`` sub-blocks (``EqtyInf`` for an equity, ``ADRInf``
for an ADR, ``OptnOnEqtsInf`` for an equity option, …). The consolidated reader flattens every
record with a ``*`` wildcard; a per-type reader keeps the records carrying its own sub-block and
maps that block's full field list.

That makes them the same read with different projections, so the lifecycle — build the URL,
download with retry, retain the raw artifact, extract the single XML member, flatten through
:func:`~filings_b3._internal.utils.xml_reader.read_xml`, validate, type, stamp provenance —
lives here **once**, and a concrete reader declares only what differs:

    class InstrumentsFileAdrReader(_BaseInstrumentsFileReader):
        str_source_key = "instruments_file_adr"
        cls_contract = INSTRUMENTS_FILE_ADR
        str_sub_block = "ADRInf"              # the row filter and the path prefix
        dict_own_paths = {"TCKR_SYMB": "TckrSymb", ...}

Like ``_base_pregao_reader``, this is a **section-local** base sitting beside the readers that
share it, and it implements the thin
:class:`~filings_b3._internal.config.ports.ingestion_reader.IngestionReader` port like any other
adapter. It is a *separate* base from ``_base_pregao_reader`` because the payload is nested XML,
not a tabular member — the case that base's docstring defers to the port.

**Column naming.** Canonical column = ``pascal_to_upper_snake`` of the BVBG.028 tag abbreviation
(``TckrSymb`` → ``TCKR_SYMB``, ``CFICd`` → ``CFICD``), the library-wide convention shared with
``daily_bulletin``. Where a leaf tag is too generic to stand alone (``OthrId/Id``,
``OthrId/Tp/Prtry``, ``FinInstrmAttrCmon/Desc``), the name is qualified by its parent block
(``OTHR_ID``, ``OTHR_ID_TP``, ``INSTRM_DESC``) — a bare ``ID`` or ``DESC`` column would be
meaningless in a datalake, and ``DESC`` is a reserved word in most SQL engines.

**Memory scales with the rows kept, not the file size** (#167). ``read_xml`` streams the document
and releases each record once projected, so a per-type read no longer pays for the whole 660 MB
artifact: measured against a real ``IN260729``, a 2-row ``FICInf`` read peaks at ~1.13 GB against
the consolidated reader's ~1.86 GB, where both previously cost ~3.0–3.6 GB.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from filings_b3._internal.config.ports.ingestion_reader import IngestionReader
from filings_b3._internal.utils.provenance import (
	hash_artifact,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.raw_workspace import raw_workspace
from filings_b3._internal.utils.retry import LogEmitter, RetryPolicy
from filings_b3._internal.utils.tabular_reader import FileContract
from filings_b3._internal.utils.xml_reader import read_xml
from filings_b3._internal.utils.zip_extractor import extract_all
from filings_b3.search_trading_session._base_pregao_reader import PREGAO_DOWNLOAD_BASE


# Distribution name (hyphenated) for importlib.metadata — NOT the import package name.
_DISTRIBUTION_NAME: str = "filings-b3"

# Local name of the repeating instrument-record element, confirmed against a live IN file:
# BVBG.028 wraps each instrument in <Instrm> (not the guessed <InstrmRcrd>).
_ROW_TAG: str = "Instrm"

# The per-record blocks that sit *outside* InstrmInf and are therefore common to every
# instrument type: report parameters, the instrument identification, and the common attributes.
# All 13 were observed on all 183,164 records of a real IN file (issue #143's fixture), which is
# why a per-type reader inherits them rather than each redeclaring its own identity columns.
_COMMON_PATHS: dict[str, str] = {
	"RPT_DT": "RptParams/RptDtAndTm/Dt",
	"ACTVTY_IND": "RptParams/ActvtyInd",
	"FRQCY": "RptParams/Frqcy",
	"NET_POS_ID": "RptParams/NetPosId",
	"UPD_TP": "RptParams/UpdTp",
	"OTHR_ID": "FinInstrmId/OthrId/Id",
	"OTHR_ID_TP": "FinInstrmId/OthrId/Tp/Prtry",
	"MKT_IDR_CD": "FinInstrmId/PlcOfListg/MktIdrCd",
	"ASST": "FinInstrmAttrCmon/Asst",
	"ASST_DESC": "FinInstrmAttrCmon/AsstDesc",
	"MKT_NM": "FinInstrmAttrCmon/Mkt",
	"SGMT_NM": "FinInstrmAttrCmon/Sgmt",
	"INSTRM_DESC": "FinInstrmAttrCmon/Desc",
}

# Date columns of the common block — declared here so a subclass never restates them.
_COMMON_DATE_COLS: tuple[str, ...] = ("RPT_DT",)

# Class attributes every concrete reader must define; checked at subclass-creation time so a
# reader that forgets one fails loudly when the class is imported, not deep inside read().
_REQUIRED_ATTRS: tuple[str, ...] = ("str_source_key", "cls_contract")


class _BaseInstrumentsFileReader(IngestionReader):
	"""Template-method base for a reader of the BVBG.028.02 instruments file.

	A subclass sets :attr:`str_source_key` and :attr:`cls_contract`, then declares its
	projection: either :attr:`str_sub_block` + :attr:`dict_own_paths` (a per-type reader) or
	:attr:`dict_paths` outright (the consolidated reader, which spans every type).

	Attributes
	----------
	str_source_key : str
		Source key routed into provenance (must be set by the subclass).
	cls_contract : FileContract
		The contract the flattened frame must satisfy (must be set by the subclass).
	str_sub_block : str or None
		Local name of the ``InstrmInf`` sub-block this reader projects (``"ADRInf"``). When set,
		only records carrying that block become rows, and every path in :attr:`dict_own_paths`
		is resolved beneath it. ``None`` (default) reads every record.
	dict_own_paths : mapping of {str: str}
		Column → path **relative to the sub-block** (``"TckrSymb"``, ``"Ppsn/Ccy"``). Ignored
		when :attr:`str_sub_block` is ``None``.
	dict_common_paths : mapping of {str: str}
		The per-record blocks outside ``InstrmInf``, prepended to every reader's columns.
		Defaults to :data:`_COMMON_PATHS`; the consolidated reader overrides it to ``{}``
		because its column set is pinned to B3's published UP2DATA layout by the drift oracle.
	list_date_cols : sequence of str
		Sub-block columns coerced to ``datetime.date`` (the common block's are added for you).
	list_decimal_cols : sequence of str
		Columns coerced to exact :class:`decimal.Decimal` — money, quantities and multipliers,
		never a binary float.
	"""

	# Required — bare annotations so the __init_subclass__ guard reports a clear error.
	str_source_key: str
	cls_contract: FileContract

	# How this reader projects the file. A per-type reader names its sub-block and that block's
	# own fields; a reader spanning every type supplies whole paths and drops the common columns.
	str_sub_block: str | None = None
	dict_own_paths: Mapping[str, str] = {}  # noqa: RUF012 - immutable by convention, never mutated
	dict_common_paths: Mapping[str, str] = _COMMON_PATHS
	dict_full_paths: Mapping[str, tuple[str, ...]] | None = None
	dict_joins: Mapping[str, tuple[str, str, str]] = {}  # noqa: RUF012 - never mutated

	list_date_cols: Sequence[str] = ()
	list_decimal_cols: Sequence[str] = ()

	def __init_subclass__(cls, **kwargs: object) -> None:
		"""Fail loudly at subclass creation if a required class attribute is missing.

		Parameters
		----------
		**kwargs : object
			Forwarded to :meth:`object.__init_subclass__`.

		Raises
		------
		NotImplementedError
			If the subclass does not set every attribute in :data:`_REQUIRED_ATTRS`.
		"""
		super().__init_subclass__(**kwargs)
		list_missing = [str_attr for str_attr in _REQUIRED_ATTRS if not hasattr(cls, str_attr)]
		if list_missing:
			raise NotImplementedError(
				f"{cls.__name__} must set class attribute(s): {', '.join(list_missing)}"
			)

	def __init__(
		self,
		date_ref: date,
		path_raw: Path | None = None,
		cls_logger: LogEmitter | None = None,
		cls_retry_policy: RetryPolicy | None = None,
	) -> None:
		"""Initialize the reader.

		Parameters
		----------
		date_ref : datetime.date
			Trading session to read; the URL is built for this date.
		path_raw : pathlib.Path, optional
			Directory in which to **keep** the downloaded raw ``.zip`` (the datalake's bronze
			layer). ``None`` (default) uses a temporary directory removed on exit.
		cls_logger : LogEmitter, optional
			Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
		cls_retry_policy : RetryPolicy, optional
			Injected retry/backoff schedule for the download; ``None`` uses the seam's default.
		"""
		self.date_ref = date_ref
		self.path_raw = path_raw
		self._cls_logger = cls_logger if cls_logger is not None else LogEmitter()
		self._cls_retry_policy = cls_retry_policy

	def build_url(self) -> str:
		"""Return the ``IN{yymmdd}.zip`` download URL for :attr:`date_ref`.

		Returns
		-------
		str
			The Pesquisa por Pregão download URL for the session's instruments file.
		"""
		return f"{PREGAO_DOWNLOAD_BASE}?filelist=IN{self.date_ref:%y%m%d}.zip"

	@property
	def dict_paths(self) -> dict[str, tuple[str, ...]]:
		"""Return the full column → alternative-paths map this reader flattens with.

		Composed from the common per-record blocks plus this reader's own sub-block fields,
		each prefixed with ``InstrmInf/<sub_block>/``. A reader that spans every type (the
		consolidated one) sets :attr:`dict_full_paths` instead and supplies whole paths.

		Returns
		-------
		dict of {str: tuple of str}
			Column → the ordered alternative record-relative paths, as ``read_xml`` expects.
		"""
		dict_out: dict[str, tuple[str, ...]] = {
			str_col: (str_path,) for str_col, str_path in self.dict_common_paths.items()
		}
		if self.dict_full_paths is not None:
			return {**dict_out, **self.dict_full_paths}
		if self.str_sub_block is None:
			return dict_out
		str_prefix = f"InstrmInf/{self.str_sub_block}"
		for str_col, str_path in self.dict_own_paths.items():
			dict_out[str_col] = (f"{str_prefix}/{str_path}",)
		return dict_out

	@property
	def dict_dtypes(self) -> dict[str, str]:
		"""Return the dtype map: text for every column that is not a date or a decimal.

		Every column the source sends must be typed explicitly — never pandas' inference — so
		this is derived from :attr:`dict_paths` rather than restated per reader. Non-date,
		non-decimal columns stay source text, keeping the source's exact bytes for fidelity.

		Returns
		-------
		dict of {str: str}
			Column → dtype string for :func:`~filings_b3._internal.utils.dtypes.apply_dtypes`.
		"""
		set_typed = {*self.list_all_date_cols, *self.list_decimal_cols}
		return {
			str_col: "str"
			for str_col in (*self.dict_paths, *self.dict_joins)
			if str_col not in set_typed
		}

	@property
	def list_all_date_cols(self) -> tuple[str, ...]:
		"""Return the reader's date columns, including the common block's.

		Returns
		-------
		tuple of str
			Every column coerced to ``datetime.date``.
		"""
		list_common = [
			str_col for str_col in _COMMON_DATE_COLS if str_col in self.dict_common_paths
		]
		return (*list_common, *self.list_date_cols)

	def _locate_xml(self, path_download: Path, path_dir: Path) -> Path:
		"""Extract the ZIP and return its single XML member.

		Parameters
		----------
		path_download : pathlib.Path
			The downloaded ``IN{yymmdd}.zip``.
		path_dir : pathlib.Path
			The workspace directory to extract into.

		Returns
		-------
		pathlib.Path
			The extracted XML file.

		Raises
		------
		ValueError
			If the archive does not contain exactly one ``.xml`` member (fail loudly rather
			than guess which member to parse).
		"""
		list_xml = [
			path_member
			for path_member in extract_all(path_download, path_dir)
			if path_member.suffix.lower() == ".xml"
		]
		if len(list_xml) != 1:
			raise ValueError(
				f"expected exactly one .xml member in {path_download.name}, "
				f"found {[p.name for p in list_xml]}"
			)
		return list_xml[0]

	def read(self) -> pd.DataFrame:
		"""Fetch, flatten, and provenance-stamp this reader's projection of the file.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped rows.

		Raises
		------
		ContractError
			When the flattened frame violates :attr:`cls_contract`.
		ValueError
			When the archive does not hold exactly one XML member.

		Notes
		-----
		The download seam is imported inside this method rather than at module load, so that
		importing the package never triggers network setup — only a reader that runs pulls it in.
		"""
		from filings_b3._internal.utils.http_downloader import download_file, url_filename

		str_url = self.build_url()
		with raw_workspace(self.path_raw) as path_dir:
			path_download = download_file(str_url, path_dir / url_filename(str_url))
			self._cls_logger.log_message(
				f"downloaded {self.str_source_key} from {str_url}", "info"
			)
			path_xml = self._locate_xml(path_download, path_dir)
			df_typed = read_xml(
				path_xml,
				_ROW_TAG,
				self.dict_paths,
				self.dict_dtypes,
				self.cls_contract,
				list_date_cols=self.list_all_date_cols,
				list_decimal_cols=self.list_decimal_cols,
				str_row_filter=(
					None if self.str_sub_block is None else f"InstrmInf/{self.str_sub_block}"
				),
				dict_joins=self.dict_joins,
			)
			return stamp_provenance(
				df_typed,
				str_url,
				self.cls_contract,
				hash_artifact(path_download),
				resolve_package_version(_DISTRIBUTION_NAME),
			)
