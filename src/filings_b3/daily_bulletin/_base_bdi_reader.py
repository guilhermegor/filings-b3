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
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re

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
from filings_b3._internal.utils.typing import type_checker


# Root every BDI dataset serves from. Declared once for the whole section so a reader names only
# its endpoint — if B3 moves the bulletin, one line changes.
BDI_TABLE_BASE: str = "https://arquivos.b3.com.br/bdi/table"

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
# PascalCase/camelCase boundary: "TckrSymb" -> "TCKR_SYMB", "VlmTradedDay" -> "VLM_TRADED_DAY".
_RE_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


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
		"""Page through the endpoint and return one typed, provenance-stamped DataFrame.

		Downloads each page into the workspace chosen by :attr:`path_raw` (kept when set),
		stops at the first page whose ``values`` is empty, concatenates the pages, enforces
		:attr:`cls_contract`, applies :attr:`dict_dtypes`, and stamps provenance against the
		**first** page's URL and content hash.

		Returns
		-------
		pd.DataFrame
			The typed, contract-validated, provenance-stamped rows.

		Raises
		------
		ContractError
			If the assembled table violates :attr:`cls_contract`.

		Notes
		-----
		The download seam is imported inside this method rather than at module load, so that
		importing the package never triggers network setup — only a reader that actually runs
		pulls it in.
		"""
		from filings_b3._internal.utils.http_downloader import download_file

		with raw_workspace(self.path_raw) as path_dir:
			list_frames: list[pd.DataFrame] = []
			# Every page fetched, in page order — the terminating empty page included, since it
			# is as much a part of what the source said as the pages carrying rows.
			list_pages: list[Path] = []
			str_first_url = ""

			int_ceiling = self.int_max_pages if self.int_max_pages is not None else _MAX_PAGES
			str_prev_digest = ""

			for int_page in range(1, int_ceiling + 1):
				str_url = self.build_url(int_page)
				path_page = download_file(str_url, path_dir / f"page_{int_page:04d}.json")
				list_pages.append(path_page)
				if not str_first_url:
					str_first_url = str_url

				# An endpoint that echoes the previous page would otherwise be appended over and
				# over until the ceiling, silently multiplying the dataset. Comparing digests
				# catches it on the FIRST repeat, before any duplicate row reaches the frame.
				str_digest = hash_artifact(path_page)
				if str_digest == str_prev_digest:
					self._cls_logger.log_message(
						f"{self.str_source_key}: page {int_page} repeats page {int_page - 1} — "
						"endpoint is not paginated; stopping",
						"warning",
					)
					break
				str_prev_digest = str_digest

				df_page = self._frame_from_payload(path_page)
				if df_page.empty:
					break
				self._cls_logger.log_message(
					f"{self.str_source_key}: page {int_page} fetched ({len(df_page)} rows)",
					"info",
				)
				list_frames.append(df_page)
			else:
				if self.int_max_pages is None:
					self._cls_logger.log_message(
						f"{self.str_source_key}: stopped at the {_MAX_PAGES}-page ceiling",
						"warning",
					)

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
			# Every page is fingerprinted. Were only the first one hashed, a source change on
			# any later page would go unnoticed — precisely the drift this column must catch.
			return stamp_provenance(
				df_typed,
				str_first_url,
				self.cls_contract,
				hash_artifacts(list_pages),
				resolve_package_version(_DISTRIBUTION_NAME),
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
			_upper_snake(str(dict_col["name"]))
			for dict_col in dict_table.get("columns", [])
			if isinstance(dict_col, dict)
		]
		return pd.DataFrame(list_values, columns=list_cols)


@type_checker
def _upper_snake(str_name: str) -> str:
	"""Convert a PascalCase API column name to ``UPPER_SNAKE_CASE``.

	Parameters
	----------
	str_name : str
		The API's column name, e.g. ``"TckrSymb"``.

	Returns
	-------
	str
		The snake-cased, upper-cased name, e.g. ``"TCKR_SYMB"``.
	"""
	return _RE_CASE_BOUNDARY.sub("_", str_name).upper()
