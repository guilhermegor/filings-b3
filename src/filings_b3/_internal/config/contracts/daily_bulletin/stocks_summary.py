"""Data contract — BDI daily average stocks summary (``DailyAverageStocks``).

The per-session summary of the cash equities market published in B3's Boletim Diário do Pregão:
one row per instrument, carrying the day's trade count and traded volume.

Column names are the API's PascalCase field names converted to ``UPPER_SNAKE_CASE`` by the BDI
base, so ``TckrSymb`` is declared here as ``TCKR_SYMB``. ``COL_ORDER`` is the source's own
display-ordering field; it is carried through rather than dropped, so a consumer can reproduce
B3's presentation order without a second fetch.

Derived from the ``b3_bdi_stocks_summary`` module being migrated out of the stpstone monorepo —
that module is the authoritative spec for this migration. ``tuple_required`` deliberately lists
only the three columns a consumer actually depends on, so B3 adding a column is not a breaking
change; a *removed* required column still fails loudly.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


# str_name (human label), str_source_key (routes provenance), tuple_required, tuple_cnpj_cols.
# No CNPJ column: this dataset keys on ticker symbols, not legal entities.
BDI_STOCKS_SUMMARY = FileContract(
	"BDI Daily Average Stocks",
	"bdi_stocks_summary",
	("TCKR_SYMB", "NMBR_TRADES_DAY", "VLM_TRADED_DAY"),
	(),
)
