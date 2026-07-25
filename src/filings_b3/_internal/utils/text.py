"""Text normalisation for matching strings across heterogeneous sources.

Labels and names arrive from different sources with inconsistent casing, accents,
tabs and stray or doubled whitespace. :func:`normalize_text` collapses all of that
to a single canonical form so matching is robust: lower-cased (casefold), accents
stripped, internal whitespace collapsed to single spaces, and trimmed.

Typical use is normalising an environment name or a free-text key before an
allow-list membership test (e.g. ``normalize_text(ENV) in {"prod", "production"}``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
import unicodedata


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


_RE_WHITESPACE = re.compile(r"\s+")
# PascalCase/camelCase boundary: "TckrSymb" -> "TCKR_SYMB", "VlmTradedDay" -> "VLM_TRADED_DAY".
_RE_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


@type_checker
def normalize_text(str_value: str) -> str:
	"""Return a canonical, accent-free, lower-cased form of ``str_value``.

	Parameters
	----------
	str_value : str
		Raw text (may carry accents, tabs, doubled or edge whitespace).

	Returns
	-------
	str
		Lower-cased, accent-stripped text with whitespace collapsed and trimmed.
	"""
	str_decomposed = unicodedata.normalize("NFKD", str(str_value))
	str_ascii = "".join(ch for ch in str_decomposed if not unicodedata.combining(ch))
	return _RE_WHITESPACE.sub(" ", str_ascii).strip().casefold()


@type_checker
def safe_str(value: object, default: str = "") -> str:
	"""Stringify ``value`` without ever producing the literal ``"nan"``.

	``str(float("nan"))`` is ``"nan"`` and ``str(None)`` is ``"None"`` — both are
	invalid-data sentinels that, once written to a cell/export, masquerade as real text
	and ship silently. This returns ``default`` for ``None`` and for any float NaN (so a
	missing numeric never becomes the four-letter string ``"nan"``); everything else is
	stringified normally and stripped.

	Parameters
	----------
	value : object
		The value to stringify.
	default : str, optional
		Returned for ``None`` or a NaN float, by default ``""``.

	Returns
	-------
	str
		``str(value).strip()``, or ``default`` when ``value`` is ``None``/NaN.
	"""
	if value is None:
		return default
	if isinstance(value, float) and value != value:  # NaN is the only value != itself
		return default
	return str(value).strip()


@type_checker
def pascal_to_upper_snake(str_name: str) -> str:
	"""Convert a PascalCase/camelCase name to ``UPPER_SNAKE_CASE``.

	Splits on each lower→upper (or digit→upper) boundary and upper-cases the result, so
	``"TckrSymb"`` becomes ``"TCKR_SYMB"`` and ``"VlmTradedDay"`` becomes ``"VLM_TRADED_DAY"``.
	An all-caps acronym has no internal boundary, so ``"ISIN"`` stays ``"ISIN"``.

	Parameters
	----------
	str_name : str
		A PascalCase or camelCase identifier (e.g. an API column name).

	Returns
	-------
	str
		The snake-cased, upper-cased name.
	"""
	return _RE_CASE_BOUNDARY.sub("_", str_name).upper()
