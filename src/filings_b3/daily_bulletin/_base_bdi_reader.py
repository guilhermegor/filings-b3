"""Shared ingestion lifecycle for the Boletim Diário do Pregão (BDI) datasets.

38 of the 39 BDI datasets are served by **one paginated JSON API**::

    https://arquivos.b3.com.br/bdi/table/<Endpoint>/<start>/<end>/<page>/<pageSize>

whose payload is a single ``table`` object::

    {"table": {"columns": [{"name": "TckrSymb"}, …],
               "values":  [[…], [—]]}}          # positional rows; [] ⇒ past the last page

So a BDI reader is **not** a file reader: there is no filename in the path, no extension to
dispatch a parser on, and the rows arrive as positional arrays that only mean something once
zipped against ``columns``. :class:`_BaseBdiReader` factors that
**paginate → persist → assemble → validate → type → stamp** lifecycle into one place; a concrete
reader supplies only :attr:`str_endpoint`, its :class:`FileContract`, and its dtypes.

(The 39th, ``b3_bdi_stocks_trade_by_trade``, serves a CSV from ``drp.b3.com.br`` and implements
the port directly rather than bending a hook onto this class.)

Pagination is **declared, never assumed**
-----------------------------------------
``…/<page>/<pageSize>`` looks uniformly paginated. It is not, and guessing corrupts data:

- **32 of the 38** datasets are single-page — hence :attr:`int_max_pages` defaults to ``1``.
- **5** are genuinely paginated and set ``int_max_pages = None`` to read until exhaustion.
- **3** are actively hostile: the endpoint **echoes the same rows for every page number**. A
  naive "loop until ``values`` is empty" would append those rows once per page up to the
  ceiling, silently multiplying the dataset — a corruption no contract check would catch,
  because every row is individually valid.

So an unbounded read additionally compares each page's digest against the previous page's and
stops on the first repeat. Declaring the mode is the primary guard; the digest check is the
backstop for an endpoint that starts echoing after a reader was written.

Each page is still **downloaded to a file** rather than held in memory, so the untouched JSON
response lands in the workspace and — when ``path_raw`` is set — survives as the datalake's
bronze record. A contract break is then replayable against the exact bytes that caused it.

This base is deliberately **section-local**, not a library-wide base. It implements the thin
:class:`~filings_b3._internal.config.ports.ingestion_reader.IngestionReader` port like any other
adapter; the file-download families (Pesquisa por Pregão) have their own base.

It is a **library** base, not a service base:

- :meth:`read` **returns** a typed :class:`pandas.DataFrame`; it performs **no database
  insertion**. A distributable library has no runtime database — the consumer decides
  persistence.
- It imports **no** headless browser and **no** PDF engine: plain HTTP + JSON over the existing
  ``_internal`` seams.
- Logging is an **injected** :class:`LogEmitter` (stdlib default), never a hard-imported backend.

Numbers are never binary floats
------------------------------
The payload is parsed with ``parse_float=Decimal``. Python's default would turn
``1984223115.42`` into a float holding ``1984223115.4200000762939453125`` — the source's exact
value destroyed **before** any dtype could be applied, irreversibly and silently. Any column
whose fractional part carries meaning is declared in :attr:`list_decimal_cols` and kept exact;
no precision is *chosen* here, since that is a downstream decision this layer cannot make.

A concrete BDI reader is tiny::

    class BdiStocksSummaryReader(_BaseBdiReader):
        str_source_key = "bdi_stocks_summary"
        str_endpoint = "DailyAverageStocks"
        cls_contract = BDI_STOCKS_SUMMARY   # from _internal.config.contracts
        dict_dtypes = {"TCKR_SYMB": "str", "NMBR_TRADES_DAY": "Int64"}
        list_decimal_cols = ("VLM_TRADED_DAY",)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from filings_b3._internal.config.ports.ingestion_reader import IngestionReader
from filings_b3._internal.utils.dtypes import apply_dtypes
from filings_b3._internal.utils.provenance import (
	hash_artifact,
	hash_artifacts,
	resolve_package_version,
	stamp_provenance,
)
from filings_b3._internal.utils.raw_workspace import raw_workspace
from filings_b3._internal.utils.retry import LogEmitter
from filings_b3._internal.utils.tabular_reader import (
	ContractError,
	FileContract,
	find_contract_problems,
)
from filings_b3._internal.utils.text import pascal_to_upper_snake
from filings_b3._internal.utils.typing import TypeChecker, type_checker


# Root every BDI dataset serves from. Declared once for the whole section so a reader names only
# its endpoint — if B3 moves the bulletin, one line changes.
BDI_TABLE_BASE: str = "https://arquivos.b3.com.br/bdi/table"

# The bulletin's service answers **405 Method Not Allowed** to a GET: it is a POST API whose query
# travels entirely in the URL path, so the body is an empty JSON object. Measured against
# `EconomicIndicators` and `DailyAverageStocks` — a bare POST with these two lines returns 200 with
# no cookie, no browser user-agent and no `origin` header, so this is the method, not a bot check.
_REQUEST_PAYLOAD: bytes = b"{}"
_REQUEST_CONTENT_TYPE: str = "application/json"

# Distribution name (hyphenated) for importlib.metadata — NOT the import package name.
_DISTRIBUTION_NAME: str = "filings-b3"
# Class attributes every concrete reader must define; checked at subclass-creation time so a
# reader that forgets one fails loudly when the class is imported, not deep inside read().
_REQUIRED_ATTRS: tuple[str, ...] = (
	"str_source_key",
	"str_endpoint",
	"cls_contract",
	"dict_dtypes",
)
# B3 caps a page at 1 000 rows; a hard ceiling on pages stops a malformed response (one that
# never returns an empty `values`) from looping forever against a live endpoint.
_DEFAULT_PAGE_SIZE: int = 1_000
_MAX_PAGES: int = 500


@type_checker
def _trim_unnamed_tail(list_values: list[object], int_cols: int) -> list[object]:
	"""Drop trailing row positions the header does not name, refusing to drop a real value.

	Some bulletin tables send rows **wider than their own header**: ``DailyAverageStocks``
	declares four columns and ships five positions per row, the fifth always ``null``, while
	``EconomicIndicators`` matches exactly. Since the payload is positional, the surplus cannot
	be named — but discarding it blindly is how a source column silently stops arriving, so
	anything other than an empty tail is an error rather than a trim.

	Parameters
	----------
	list_values : list of object
		The page's rows, each a positional list.
	int_cols : int
		How many columns the header names.

	Returns
	-------
	list of object
		The rows, each truncated to ``int_cols`` positions.

	Raises
	------
	ValueError
		If a trimmed position holds anything but ``None`` — a value with no column name.
	"""
	list_out: list[object] = []
	for list_row in list_values:
		if not isinstance(list_row, list) or len(list_row) <= int_cols:
			list_out.append(list_row)
			continue
		list_tail = list_row[int_cols:]
		if any(obj_extra is not None for obj_extra in list_tail):
			raise ValueError(
				f"row carries {len(list_row)} values for {int_cols} named columns, and the "
				f"unnamed tail is not empty: {list_tail!r}"
			)
		list_out.append(list_row[:int_cols])
	return list_out


@dataclass(frozen=True)
class _Page(metaclass=TypeChecker):
	"""One downloaded BDI page: its file, source URL, parsed rows, and content digest.

	The value :meth:`_BaseBdiReader._read_page` returns and :meth:`_BaseBdiReader.read`
	generalises over — grouping the four facts of a single page so the pagination loop reads as
	orchestration rather than plumbing.
	"""

	path_file: Path
	str_url: str
	df_rows: pd.DataFrame
	str_digest: str


class _BaseBdiReader(IngestionReader):
	"""Template-method base for a Boletim Diário (BDI) paginated-JSON reader.

	Subclasses set the four required class attributes (:attr:`str_source_key`,
	:attr:`str_endpoint`, :attr:`cls_contract`, :attr:`dict_dtypes`). Everything else —
	pagination, raw-page retention, column mapping, contract enforcement, dtype coercion,
	provenance stamping — is inherited.

	Attributes
	----------
	str_source_key : str
		Source key routed into provenance (must be set by the subclass).
	str_endpoint : str
		The API endpoint segment, e.g. ``"DailyAverageStocks"`` (must be set by the subclass).
	cls_contract : FileContract
		The contract the assembled table must satisfy (must be set by the subclass).
	dict_dtypes : dict of {str: str}
		Column→dtype mapping enforced via ``apply_dtypes`` (must be set by the subclass).
	list_date_cols : sequence of str or None
		Columns coerced to ``datetime.date`` (default ``None``).
	list_decimal_cols : sequence of str or None
		Columns coerced to exact :class:`decimal.Decimal` (default ``None``). Every number
		whose fractional part carries meaning belongs here — money, volumes, rates, quantities
		— never a binary float dtype in :attr:`dict_dtypes`.
	int_page_size : int
		Rows requested per page (default 1 000, B3's cap).
	int_max_pages : int or None
		How many pages this dataset actually has: ``1`` (the default, and correct for most BDI
		datasets), an explicit count, or ``None`` to read until the source is exhausted. Get
		this wrong towards ``None`` on an echoing endpoint and the dataset multiplies; get it
		wrong towards ``1`` on a paginated one and rows are silently dropped — so set it from
		the source's observed behaviour, never from the URL shape.
	"""

	# Required — declared as bare annotations so an unset subclass raises AttributeError; the
	# __init_subclass__ guard turns that into a clear error at class-definition time instead.
	str_source_key: str
	str_endpoint: str
	cls_contract: FileContract
	dict_dtypes: dict[str, str]

	# Optional knobs with sensible defaults; a subclass overrides only what differs.
	list_date_cols: Sequence[str] | None = None
	# Columns coerced to exact Decimal — any number whose fractional part carries meaning.
	list_decimal_cols: Sequence[str] | None = None
	int_page_size: int = _DEFAULT_PAGE_SIZE
	# Pagination is DECLARED, never assumed — see the module docstring. One page by default,
	# which is what 32 of the 38 BDI datasets serve; a genuinely paginated dataset sets None.
	int_max_pages: int | None = 1

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
	) -> None:
		"""Initialize the reader.

		Parameters
		----------
		date_ref : datetime.date
			Trading session to read. **Required, with no default**: the BDI endpoint is
			date-addressed, so there is no such thing as a date-less read. Defaulting to
			"the last business day" was rejected deliberately — it would silently read a
			*different* session than the caller meant whenever the guess is wrong (holidays,
			a late publication, a backfill), and a wrong session is far worse than a
			`TypeError` at construction. A caller wanting the previous business day computes
			it and passes it.
		path_raw : pathlib.Path, optional
			Directory in which to **keep** each downloaded raw JSON page (the datalake's
			bronze layer). ``None`` (default) uses a temporary directory removed on exit.
		cls_logger : LogEmitter, optional
			Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
		"""
		self.date_ref = date_ref
		self.path_raw = path_raw
		self._cls_logger = cls_logger if cls_logger is not None else LogEmitter()

	def build_url(self, int_page: int) -> str:
		"""Return the API URL for one page of this dataset's table.

		The BDI endpoint takes an inclusive start/end date pair; a single-session read passes
		the same date twice. A reader whose dataset spans a range overrides this.

		Parameters
		----------
		int_page : int
			The 1-indexed page to request.

		Returns
		-------
		str
			The fully-formed endpoint URL for that page.
		"""
		str_day = f"{self.date_ref:%Y-%m-%d}"
		return (
			f"{BDI_TABLE_BASE}/{self.str_endpoint}/{str_day}/{str_day}"
			f"/{int_page}/{self.int_page_size}"
		)

	def read(self) -> pd.DataFrame:
		"""Read the endpoint into one typed, provenance-stamped DataFrame.

		Orchestrates two phases inside the raw workspace: :meth:`_paginate` loops
		:meth:`_read_page` to collect the result's pages, then :meth:`_finalize` validates,
		types, and stamps the assembled frame **once**.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped rows.

		Raises
		------
		ContractError
			If the assembled table violates :attr:`cls_contract` (raised by :meth:`_finalize`).
		"""
		with raw_workspace(self.path_raw) as path_dir:
			list_frames, list_pages, str_first_url = self._paginate(path_dir)
			return self._finalize(list_frames, list_pages, str_first_url)

	def _paginate(self, path_dir: Path) -> tuple[list[pd.DataFrame], list[Path], str]:
		"""Loop :meth:`_read_page` in page order until the source is exhausted (or echoes).

		Stops at the first empty page, the first echoed page (see :meth:`_is_echoed_page`), or
		the declared page ceiling — whichever comes first.

		Parameters
		----------
		path_dir : pathlib.Path
			Directory each raw JSON page is downloaded into.

		Returns
		-------
		tuple of (list of pandas.DataFrame, list of pathlib.Path, str)
			The row-bearing page frames, every downloaded page path (for hashing — the
			terminating empty page included, since it is as much a part of what the source said
			as the pages carrying rows), and the first page's URL (for provenance).
		"""
		list_frames: list[pd.DataFrame] = []
		list_pages: list[Path] = []
		str_first_url = ""
		str_prev_digest = ""
		int_ceiling = self.int_max_pages if self.int_max_pages is not None else _MAX_PAGES

		for int_page in range(1, int_ceiling + 1):
			cls_page = self._read_page(int_page, path_dir)
			list_pages.append(cls_page.path_file)
			str_first_url = str_first_url or cls_page.str_url

			if self._is_echoed_page(cls_page, str_prev_digest, int_page):
				break
			str_prev_digest = cls_page.str_digest

			if cls_page.df_rows.empty:
				break
			int_rows = len(cls_page.df_rows)
			self._cls_logger.log_message(
				f"{self.str_source_key}: page {int_page} fetched ({int_rows} rows)",
				"info",
			)
			list_frames.append(cls_page.df_rows)
		else:
			if self.int_max_pages is None:
				self._cls_logger.log_message(
					f"{self.str_source_key}: stopped at the {_MAX_PAGES}-page ceiling",
					"warning",
				)
		return list_frames, list_pages, str_first_url

	def _finalize(
		self,
		list_frames: list[pd.DataFrame],
		list_pages: list[Path],
		str_first_url: str,
	) -> pd.DataFrame:
		"""Assemble the pages, enforce the contract, apply dtypes, and stamp provenance.

		Runs **once** on the whole result, never per page: the contract validates the assembled
		table, ``apply_dtypes`` coerces it, and provenance is stamped against the **first** page's
		URL and the content hash of **every** page — so a source change on any later page is
		caught, not just the first.

		Parameters
		----------
		list_frames : list of pandas.DataFrame
			The row-bearing page frames (empty when the endpoint returned no rows).
		list_pages : list of pathlib.Path
			Every downloaded page, hashed together into the provenance fingerprint.
		str_first_url : str
			The first page's URL, recorded as the row's source URL.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped rows.

		Raises
		------
		ContractError
			If the assembled table violates :attr:`cls_contract`.
		"""
		df_all = (
			pd.concat(list_frames, ignore_index=True)
			if list_frames
			else pd.DataFrame(columns=list(self.cls_contract.tuple_required))
		)
		list_problems = find_contract_problems(df_all, self.cls_contract)
		if list_problems:
			raise ContractError(list_problems)

		df_typed = apply_dtypes(
			df_all,
			self.dict_dtypes,
			list_date_cols=self.list_date_cols,
			list_decimal_cols=self.list_decimal_cols,
		)
		return stamp_provenance(
			df_typed,
			str_first_url,
			self.cls_contract,
			hash_artifacts(list_pages),
			resolve_package_version(_DISTRIBUTION_NAME),
		)

	def _is_echoed_page(self, cls_page: _Page, str_prev_digest: str, int_page: int) -> bool:
		"""Return whether this page byte-for-byte repeats the previous one, logging if so.

		Some BDI endpoints ignore the page number and **echo the same rows for every page**. A
		naive "loop until ``values`` is empty" would append those rows once per page up to the
		ceiling, silently multiplying the dataset — a corruption no contract check would catch,
		since every row is individually valid. Comparing the untouched-bytes digest to the
		previous page's catches it on the **first** repeat, before any duplicate row reaches the
		frame.

		Parameters
		----------
		cls_page : _Page
			The page just read.
		str_prev_digest : str
			Content digest of the previous page (``""`` before the first page).
		int_page : int
			The 1-indexed page number, for the log message.

		Returns
		-------
		bool
			``True`` when the page repeats its predecessor (the caller must stop paginating).
		"""
		if cls_page.str_digest != str_prev_digest:
			return False
		self._cls_logger.log_message(
			f"{self.str_source_key}: page {int_page} repeats page {int_page - 1} — "
			"endpoint is not paginated; stopping",
			"warning",
		)
		return True

	def _read_page(self, int_page: int, path_dir: Path) -> _Page:
		"""Download and parse a single page of this dataset's table — the atomic read unit.

		Fetches exactly one page to a file in ``path_dir`` (kept when :attr:`path_raw` is set),
		fingerprints the untouched bytes, and maps the positional ``values`` onto their column
		names. It applies **no** contract and **no** dtypes — those run once, in :meth:`read`, on
		the assembled frame.

		Parameters
		----------
		int_page : int
			The 1-indexed page to fetch.
		path_dir : pathlib.Path
			Directory the raw JSON page is downloaded into.

		Returns
		-------
		_Page
			The page's file path, source URL, parsed rows, and content digest.

		Notes
		-----
		The download seam is imported inside this method, not at module load, so importing the
		package never triggers network setup — only a reader that actually runs pulls it in.
		"""
		from filings_b3._internal.utils.http_downloader import download_file

		str_url = self.build_url(int_page)
		path_page = download_file(
			str_url,
			path_dir / f"page_{int_page:04d}.json",
			bytes_payload=_REQUEST_PAYLOAD,
			str_content_type=_REQUEST_CONTENT_TYPE,
		)
		return _Page(
			path_file=path_page,
			str_url=str_url,
			df_rows=self._frame_from_payload(path_page),
			str_digest=hash_artifact(path_page),
		)

	def _frame_from_payload(self, path_page: Path) -> pd.DataFrame:
		"""Build a named DataFrame from one downloaded JSON page.

		``values`` arrives as positional arrays, so the column names in ``columns`` are what
		give them meaning — zipped by index, never by guessing. An empty ``values`` means the
		page is past the end of the result set and yields an empty frame.

		Parameters
		----------
		path_page : pathlib.Path
			The downloaded JSON page.

		Returns
		-------
		pd.DataFrame
			The page's rows under ``UPPER_SNAKE_CASE`` column names, or an empty frame.

		Raises
		------
		ValueError
			When a row carries a **value** in a position no column names — that would be source
			data silently thrown away, so it fails instead of guessing a name for it.
		"""
		# Decimal parsing here is load-bearing, not a nicety. Left to its default, json turns
		# a traded volume into a binary float that already holds a slightly different number,
		# so the source's exact value is gone BEFORE any dtype can be applied. Parsing to
		# Decimal keeps the source text exact; apply_dtypes then preserves it.
		dict_payload: dict[str, dict[str, list[object]]] = json.loads(
			path_page.read_text(encoding="utf-8"), parse_float=Decimal
		)
		dict_table = dict_payload.get("table") or {}
		list_values: list[object] = dict_table.get("values") or []
		if not list_values:
			return pd.DataFrame()

		list_cols: list[str] = [
			pascal_to_upper_snake(str(dict_col["name"]))
			for dict_col in dict_table.get("columns", [])
			if isinstance(dict_col, dict)
		]
		return pd.DataFrame(_trim_unnamed_tail(list_values, len(list_cols)), columns=list_cols)
