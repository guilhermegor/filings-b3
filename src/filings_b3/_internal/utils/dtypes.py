"""Explicit column typing for DataFrames loaded from a source.

A single place to enforce the project rule *every DataFrame or SQL-to-memory load
must declare its column types* — instead of trusting pandas' inference, which silently
turns a zero-padded code into an int or a mixed column into ``object``. Pass an
``astype`` dict for the plain types plus optional lists for ``date`` / ``datetime``
columns, which need ``to_datetime`` rather than ``astype``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pandas as pd


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from filings_b3._internal.utils.typing import type_checker
else:
	try:
		from filings_b3._internal.utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from filings_b3._internal.utils.typing import type_checker


# pandas < 3 has no real ``str`` dtype: ``astype("str")`` on a missing value yields the
# LITERAL three-character string ``"nan"`` (object dtype), and ``.isna()`` then reports
# ``False`` — a blank source field becomes indistinguishable from one the source actually
# sent, and nothing raises. pandas 3 introduced a true ``str`` dtype that preserves NA.
# A ``poetry.lock`` routinely ships BOTH majors keyed by Python marker, so the same dtype
# declaration would produce different DATA on different CI legs (and a dev box on pandas 3
# sees a fully green suite). The nullable ``"string"`` dtype behaves identically on 2 and 3,
# and its elements are still ordinary ``str`` — ``isinstance(x, str)`` keeps passing.
_DTYPE_TEXT = "string"


@type_checker
def _resolve_text_dtypes(dict_dtypes: dict[str, str]) -> dict[str, str]:
	"""Swap ``"str"`` declarations for the NA-safe nullable ``"string"`` dtype.

	Callers keep writing the obvious ``"str"``; this is the single place that knows the
	pandas-major caveat.

	Parameters
	----------
	dict_dtypes : dict of {str: str}
		The caller's column→dtype mapping.

	Returns
	-------
	dict of {str: str}
		The same mapping with every ``"str"`` replaced by ``"string"``.
	"""
	return {
		str_col: (_DTYPE_TEXT if str_dtype == "str" else str_dtype)
		for str_col, str_dtype in dict_dtypes.items()
	}


@type_checker
def _to_decimal(value: object) -> object:
	"""Convert one source value to an exact :class:`~decimal.Decimal`.

	Accepts the two forms a lossless pipeline can deliver — text (``"1984223115.42"``, the
	usual shape from CSV or from JSON parsed with ``parse_float=Decimal``) and ``int`` — plus
	``Decimal`` itself, which passes through untouched. Missing values stay missing.

	A binary ``float`` is **rejected rather than converted**. By the time a float exists the
	source's exact value is already gone, so converting it would launder a lossy value into a
	type that advertises exactness — the silent failure this seam exists to prevent. The fix
	belongs upstream at the parse boundary (``json.loads(..., parse_float=Decimal)``, or
	reading the column as text), never here.

	Parameters
	----------
	value : object
		One cell from a decimal-typed column.

	Returns
	-------
	object
		A :class:`decimal.Decimal`, or :data:`pandas.NA` for a missing value.

	Raises
	------
	ValueError
		If ``value`` is a binary ``float`` — precision was already lost upstream.
	"""
	if value is None or value is pd.NA:
		return pd.NA
	if isinstance(value, Decimal):
		return value
	# NaN is a float, but it means "missing", not "a value we lost precision on" — pandas uses
	# it as the missing marker in any numeric column. Test it before the float rejection below,
	# or every blank cell in such a column would raise instead of staying NA.
	if isinstance(value, float) and value != value:
		return pd.NA
	if isinstance(value, float):
		raise ValueError(
			f"Refusing to convert float {value!r} to Decimal: the source's exact value is "
			"already lost. Parse the source losslessly instead — "
			"json.loads(..., parse_float=Decimal), or read the column as text."
		)
	if isinstance(value, int):
		return Decimal(value)
	str_value = str(value).strip()
	if not str_value or str_value.lower() in {"nan", "none", "<na>"}:
		return pd.NA
	return Decimal(str_value)


@type_checker
def _parse_date_scalar(value: object) -> object:
	"""Parse one source value to a :class:`datetime.date`, tolerating far-future sentinels.

	Python's :class:`datetime.date` spans years 1–9999, so a source sentinel like B3's
	``9999-12-31`` ("perpetual / no end date") parses to a real date here — where pandas'
	nanosecond ``Timestamp`` (max ~2262) would overflow. Only the out-of-bounds fallback in
	:func:`_to_date_series` routes through this; the common in-range path stays vectorised pandas.

	Parameters
	----------
	value : object
		One cell from a date-typed column (ISO ``YYYY-MM-DD``, optionally with a time component).

	Returns
	-------
	object
		A :class:`datetime.date`, or :data:`pandas.NA` for a missing value.
	"""
	if value is None or value is pd.NA:
		return pd.NA
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	str_value = str(value).strip()
	if not str_value or str_value.lower() in {"nan", "nat", "none", "<na>"}:
		return pd.NA
	# B3's ISODate is ISO 8601; datetime.fromisoformat handles both the date-only and the
	# date-with-time forms on the project's Python floor, and both convert to a pure date.
	return datetime.fromisoformat(str_value).date()


@type_checker
def _to_date_series(series_input: pd.Series) -> pd.Series:
	"""Coerce a text column to ``datetime.date``, out-of-bounds-safe.

	The fast path is vectorised pandas (``to_datetime``), which handles every in-range date and a
	variety of formats. A source that carries a date beyond pandas' nanosecond ``Timestamp`` range
	— B3 uses ``9999-12-31`` as a "no end / perpetual" sentinel in ``TradgEndDt`` / ``XprtnDt`` —
	makes ``to_datetime`` raise ``OutOfBoundsDatetime``; only then does it fall back to per-element
	:func:`_parse_date_scalar`, which yields real :class:`datetime.date` objects that preserve the
	sentinel rather than dropping it to ``NaT``. Readers with only in-range dates keep the fast
	path unchanged.

	Parameters
	----------
	series_input : pandas.Series
		The date column as read (text).

	Returns
	-------
	pandas.Series
		A column of :class:`datetime.date` objects (object dtype).
	"""
	try:
		return pd.to_datetime(series_input, errors="raise").dt.date
	except (pd.errors.OutOfBoundsDatetime, OverflowError, ValueError):
		return series_input.map(_parse_date_scalar)


@type_checker
def apply_dtypes(
	df_input: pd.DataFrame,
	dict_dtypes: dict[str, str] | None = None,
	list_date_cols: Sequence[str] | None = None,
	list_datetime_cols: Sequence[str] | None = None,
	list_decimal_cols: Sequence[str] | None = None,
) -> pd.DataFrame:
	"""Coerce a DataFrame's columns to declared types, returning a new frame.

	Validation runs first (fail fast): every referenced column must exist, and the
	four column sets must be disjoint. Then, on a copy: the ``astype`` dict is applied,
	``list_datetime_cols`` are parsed to full timestamps, ``list_date_cols`` to pure
	``date`` objects, and ``list_decimal_cols`` to exact :class:`decimal.Decimal` values.

	Parameters
	----------
	df_input : pd.DataFrame
		The source frame (left unmodified — work happens on a copy).
	dict_dtypes : dict of {str: str}, optional
		Column→dtype mapping passed to :meth:`pandas.DataFrame.astype` (e.g. ``"str"``,
		``"int64"``). A ``"str"`` declaration is normalised to the nullable ``"string"``
		dtype so a missing value stays NA instead of becoming the literal ``"nan"`` on
		pandas 2 — see :data:`_DTYPE_TEXT`. **Do not declare a binary float dtype for an
		ingested source column** — use ``list_decimal_cols`` (see below).
	list_date_cols : sequence of str, optional
		Columns coerced to ``datetime.date`` (date only, no time component).
	list_datetime_cols : sequence of str, optional
		Columns coerced to ``datetime64`` timestamps.
	list_decimal_cols : sequence of str, optional
		Columns coerced to exact :class:`decimal.Decimal` values (``object`` dtype), for any
		number whose fractional part carries meaning — money, volumes, rates, quantities.
		``float64`` cannot represent most decimal fractions: ``1984223115.42`` is stored as
		``1984223115.4200000762939453125``, and that loss is **irreversible and silent**,
		surfacing later as a reconciliation that misses by a hair. The source's own scale is
		preserved exactly; no precision is *chosen* here, because choosing one is a
		downstream (warehouse) decision this layer cannot make.

	Returns
	-------
	pd.DataFrame
		A new frame with the requested types applied.

	Raises
	------
	KeyError
		If any referenced column is absent from ``df_input``.
	ValueError
		If a column appears in more than one of the four sets, a date/datetime column
		cannot be parsed (``to_datetime`` uses ``errors="raise"``), or a decimal column
		already holds a binary ``float`` (see :func:`_to_decimal`).
	"""
	dict_dtypes = dict_dtypes or {}
	list_date_cols = list(list_date_cols or [])
	list_datetime_cols = list(list_datetime_cols or [])
	list_decimal_cols = list(list_decimal_cols or [])

	list_referenced = (
		list(dict_dtypes.keys()) + list_date_cols + list_datetime_cols + list_decimal_cols
	)
	set_missing = {str_col for str_col in list_referenced if str_col not in df_input.columns}
	if set_missing:
		raise KeyError(f"Columns not found in DataFrame: {sorted(set_missing)}")

	set_seen: set[str] = set()
	set_overlap: set[str] = set()
	for str_col in list_referenced:
		if str_col in set_seen:
			set_overlap.add(str_col)
		set_seen.add(str_col)
	if set_overlap:
		raise ValueError(f"Columns assigned more than one target type: {sorted(set_overlap)}")

	df_typed = df_input.copy()

	if dict_dtypes:
		df_typed = df_typed.astype(_resolve_text_dtypes(dict_dtypes))

	for str_col in list_datetime_cols:
		df_typed[str_col] = pd.to_datetime(df_typed[str_col], errors="raise")

	for str_col in list_date_cols:
		df_typed[str_col] = _to_date_series(df_typed[str_col])

	for str_col in list_decimal_cols:
		df_typed[str_col] = df_typed[str_col].map(_to_decimal)

	return df_typed
