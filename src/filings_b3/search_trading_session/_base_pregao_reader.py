"""Shared ingestion lifecycle for the Pesquisa por Pregão (trading-session) datasets.

The 42 datasets under ``www.b3.com.br/pesquisapregao/download?filelist=…`` all do the same four
things: download a file (usually a ZIP), reach the tabular member inside it, read that into a
typed, contract-validated DataFrame, and stamp provenance. :class:`_BasePregaoReader` factors
that **fetch → locate → read → stamp** lifecycle into one place; a concrete reader supplies only
the source-specific pieces — the URL, the :class:`FileContract`, the column dtypes, and (when
the download is not already the tabular file, e.g. a ZIP) how to reach it.

Note the endpoint is **query-only** — the path carries no filename — which is exactly the case
:func:`~filings_b3._internal.utils.http_downloader.url_filename` falls back to ``"download"``
for.

This base is deliberately **section-local**, not a library-wide base. It sits beside the
readers that share its lifecycle, and it implements the thin
:class:`~filings_b3._internal.config.ports.ingestion_reader.IngestionReader` port like any
other adapter. A dataset whose source does not fit this shape — the scraped ``clearing``
warranties, the legacy BMF portal under ``market_data`` — implements the port directly instead
of bending a hook onto this class.

It is a **library** base, not a service base:

- :meth:`read` **returns** a typed :class:`pandas.DataFrame`; it performs **no database
  insertion**. A distributable library has no runtime database — the consumer decides
  persistence. (This is the deliberate departure from the source monorepo's ``cls_db`` /
  ``insert_table_db`` base.)
- It imports **no** headless browser (``playwright`` / ``selenium``) and **no** PDF engine
  (``fitz`` / ``pdfplumber``): the lifecycle is plain HTTP + tabular parsing over the existing
  ``_internal`` seams. A source that genuinely needs a browser or a PDF parser gets a separate
  base behind the optional ``scraping`` / ``pdf`` extras — never this one.
- Logging is an **injected** :class:`LogEmitter` (stdlib default), never a hard-imported
  backend, and the retry schedule is an injected :class:`RetryPolicy`.

A concrete reader is tiny — it names its file code off the shared
:data:`PREGAO_DOWNLOAD_BASE` rather than repeating the host::

    class InstrumentsFileReader(_BasePregaoReader):
        str_source_key = "instruments_file"
        cls_contract = INSTRUMENTS_FILE     # from _internal.config.contracts
        dict_dtypes = {"code": "string", "price": "float64"}

        def build_url(self) -> str:
            return f"{PREGAO_DOWNLOAD_BASE}?filelist=IN{self.date_ref:%y%m%d}.zip"

ZIP sources additionally override :meth:`locate_table` to extract and pick the member.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pandas as pd

from filings_b3._internal.config.ports.ingestion_reader import IngestionReader
from filings_b3._internal.utils.http_downloader import url_filename
from filings_b3._internal.utils.provenance import (
	hash_artifact,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.raw_workspace import raw_workspace
from filings_b3._internal.utils.retry import LogEmitter, RetryPolicy
from filings_b3._internal.utils.tabular_reader import FileContract, read_table


# Root every trading-session download serves from. Declared once for the whole section so a
# reader composes its endpoint off it instead of repeating the host.
PREGAO_DOWNLOAD_BASE: str = "https://www.b3.com.br/pesquisapregao/download"

# Distribution name (hyphenated) for importlib.metadata — NOT the import package name.
_DISTRIBUTION_NAME: str = "filings-b3"
# Class attributes every concrete reader must define; checked at subclass-creation time so a
# reader that forgets one fails loudly when the class is imported, not deep inside read().
_REQUIRED_ATTRS: tuple[str, ...] = ("str_source_key", "cls_contract", "dict_dtypes")


class _BasePregaoReader(IngestionReader):
	"""Template-method base for a Boletim Diário (BDI) tabular-file reader.

	Subclasses set the three required class attributes (:attr:`str_source_key`,
	:attr:`cls_contract`, :attr:`dict_dtypes`), implement :meth:`build_url`, and — for
	ZIP/compound payloads — override :meth:`locate_table`. Everything else (download with
	retry, raw-artifact retention, contract enforcement, dtype coercion, provenance stamping)
	is inherited.

	Attributes
	----------
	str_source_key : str
		Source key routed into provenance (must be set by the subclass).
	cls_contract : FileContract
		The contract the downloaded table must satisfy (must be set by the subclass).
	dict_dtypes : dict of {str: str}
		Column→dtype mapping enforced via ``apply_dtypes`` (must be set by the subclass).
	list_date_cols : sequence of str or None
		Columns coerced to ``datetime.date`` (default ``None``).
	str_sheet : str
		Excel worksheet name; ``""`` reads the first sheet, ignored for CSV/JSON.
	str_csv_sep : str
		CSV delimiter (default ``";"``), ignored for Excel/JSON.
	"""

	# Required — declared as bare annotations so an unset subclass raises AttributeError; the
	# __init_subclass__ guard turns that into a clear error at class-definition time instead.
	str_source_key: str
	cls_contract: FileContract
	dict_dtypes: dict[str, str]

	# Optional read knobs with sensible defaults; a subclass overrides only what differs.
	list_date_cols: Sequence[str] | None = None
	str_sheet: str = ""
	str_csv_sep: str = ";"

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
		date_ref: date | None = None,
		path_raw: Path | None = None,
		cls_logger: LogEmitter | None = None,
		cls_retry_policy: RetryPolicy | None = None,
	) -> None:
		"""Initialize the reader.

		Parameters
		----------
		date_ref : datetime.date, optional
			Reference date the source URL is built for (default ``None`` — a source whose
			URL is date-independent ignores it).
		path_raw : pathlib.Path, optional
			Directory in which to **keep** the downloaded raw artifact (the datalake's bronze
			layer). ``None`` (default) uses a temporary directory removed on exit.
		cls_logger : LogEmitter, optional
			Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
		cls_retry_policy : RetryPolicy, optional
			Injected retry/backoff schedule for the download; ``None`` uses the download
			seam's own default.
		"""
		self.date_ref = date_ref
		self.path_raw = path_raw
		self._cls_logger = cls_logger if cls_logger is not None else LogEmitter()
		self._cls_retry_policy = cls_retry_policy

	@abstractmethod
	def build_url(self) -> str:
		"""Return the source URL to download (may depend on :attr:`date_ref`).

		Returns
		-------
		str
			The http/https URL of the source artifact.

		Raises
		------
		NotImplementedError
			Always — a concrete reader must implement this.
		"""
		raise NotImplementedError

	def locate_table(self, path_download: Path) -> Path:
		"""Return the path of the tabular file to read from the downloaded artifact.

		The default is identity: the download **is** the table (a direct CSV/XLSX/JSON). A
		ZIP or otherwise compound source overrides this to extract and select the member
		(e.g. via ``_internal.utils.zip_extractor``).

		Parameters
		----------
		path_download : pathlib.Path
			The file :meth:`read` downloaded.

		Returns
		-------
		pathlib.Path
			The tabular file to hand to the reader.
		"""
		return path_download

	def read(self) -> pd.DataFrame:
		"""Fetch, read, and provenance-stamp the source into a typed DataFrame.

		Downloads :meth:`build_url` into the workspace chosen by :attr:`path_raw` (a temporary
		directory when unset, a kept directory when set), reaches the tabular file via
		:meth:`locate_table`, reads it under :attr:`cls_contract` + :attr:`dict_dtypes`
		(raising :class:`ContractError` on violation), then stamps provenance (source URL,
		fetch time, content hash of the **raw** artifact, package version) and returns the
		frame. No persistence is performed.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped rows.

		Notes
		-----
		The download seam is imported inside this method rather than at module load, so that
		importing the package never triggers network setup — only a reader that actually runs
		pulls it in.
		"""
		from filings_b3._internal.utils.http_downloader import download_file

		str_url = self.build_url()
		with raw_workspace(self.path_raw) as path_dir:
			path_download = download_file(str_url, path_dir / url_filename(str_url))
			str_msg = f"downloaded {self.str_source_key} from {str_url}"
			self._cls_logger.log_message(str_msg, "info")
			path_table = self.locate_table(path_download)
			df_typed = read_table(
				path_table,
				self.str_sheet,
				self.dict_dtypes,
				self.cls_contract,
				list_date_cols=self.list_date_cols,
				str_csv_sep=self.str_csv_sep,
			)
			return stamp_provenance(
				df_typed,
				str_url,
				self.cls_contract,
				hash_artifact(path_download),
				resolve_package_version(_DISTRIBUTION_NAME),
			)
