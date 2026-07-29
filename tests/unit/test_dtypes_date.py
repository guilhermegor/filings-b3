"""Tests for out-of-bounds-safe date coercion in ``apply_dtypes``.

B3 uses ``9999-12-31`` as a "perpetual / no end date" sentinel (e.g. ``TradgEndDt`` for a
non-expiring instrument). That date is valid for :class:`datetime.date` but beyond pandas'
nanosecond ``Timestamp`` range (~year 2262), so a naive ``to_datetime`` overflows. These pin that
the sentinel is preserved as a real date, never dropped or raised on.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from filings_b3._internal.utils.dtypes import apply_dtypes


def test_apply_dtypes_preserves_a_far_future_date_sentinel() -> None:
	"""A ``9999-12-31`` date column becomes a real ``datetime.date``, not ``NaT`` or an error."""
	df_in = pd.DataFrame({"END_DATE": ["2026-07-29", "9999-12-31"]})

	df_out = apply_dtypes(df_in, list_date_cols=("END_DATE",))

	assert list(df_out["END_DATE"]) == [date(2026, 7, 29), date(9999, 12, 31)]


def test_apply_dtypes_dates_keep_missing_as_missing() -> None:
	"""A blank date cell stays missing rather than becoming a bogus date."""
	df_in = pd.DataFrame({"END_DATE": ["9999-12-31", ""]})

	df_out = apply_dtypes(df_in, list_date_cols=("END_DATE",))

	assert df_out["END_DATE"].iloc[0] == date(9999, 12, 31)
	assert pd.isna(df_out["END_DATE"].iloc[1])


def test_apply_dtypes_in_range_dates_still_coerce() -> None:
	"""Ordinary in-range dates coerce exactly as before (the fast path is unchanged)."""
	df_in = pd.DataFrame({"D": ["2025-01-02", "2025-12-31"]})

	df_out = apply_dtypes(df_in, list_date_cols=("D",))

	assert list(df_out["D"]) == [date(2025, 1, 2), date(2025, 12, 31)]
