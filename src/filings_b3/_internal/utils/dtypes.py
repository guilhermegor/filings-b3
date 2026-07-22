"""Explicit column typing for DataFrames loaded from a source.

A single place to enforce the project rule *every DataFrame or SQL-to-memory load
must declare its column types* — instead of trusting pandas' inference, which silently
turns a zero-padded code into an int or a mixed column into ``object``. Pass an
``astype`` dict for the plain types plus optional lists for ``date`` / ``datetime``
columns, which need ``to_datetime`` rather than ``astype``.
"""

from __future__ import annotations

from collections.abc import Sequence
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
def apply_dtypes(
	df_input: pd.DataFrame,
	dict_dtypes: dict[str, str] | None = None,
	list_date_cols: Sequence[str] | None = None,
	list_datetime_cols: Sequence[str] | None = None,
) -> pd.DataFrame:
	"""Coerce a DataFrame's columns to declared types, returning a new frame.

	Validation runs first (fail fast): every referenced column must exist, and the
	three column sets must be disjoint. Then, on a copy: the ``astype`` dict is applied,
	``list_datetime_cols`` are parsed to full timestamps, and ``list_date_cols`` to pure
	``date`` objects.

	Parameters
	----------
	df_input : pd.DataFrame
		The source frame (left unmodified — work happens on a copy).
	dict_dtypes : dict of {str: str}, optional
		Column→dtype mapping passed to :meth:`pandas.DataFrame.astype` (e.g. ``"str"``,
		``"int64"``, ``"float64"``). A ``"str"`` declaration is normalised to the nullable
		``"string"`` dtype so a missing value stays NA instead of becoming the literal
		``"nan"`` on pandas 2 — see :data:`_DTYPE_TEXT`.
	list_date_cols : sequence of str, optional
		Columns coerced to ``datetime.date`` (date only, no time component).
	list_datetime_cols : sequence of str, optional
		Columns coerced to ``datetime64`` timestamps.

	Returns
	-------
	pd.DataFrame
		A new frame with the requested types applied.

	Raises
	------
	KeyError
		If any referenced column is absent from ``df_input``.
	ValueError
		If a column appears in more than one of the three sets, or a date/datetime
		column cannot be parsed (``to_datetime`` uses ``errors="raise"``).
	"""
	dict_dtypes = dict_dtypes or {}
	list_date_cols = list(list_date_cols or [])
	list_datetime_cols = list(list_datetime_cols or [])

	list_referenced = list(dict_dtypes.keys()) + list_date_cols + list_datetime_cols
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
		df_typed[str_col] = pd.to_datetime(df_typed[str_col], errors="raise").dt.date

	return df_typed
