"""Data contract — BDI securities-lending open positions (``BTBLendingOpenPosition``).

The end-of-session snapshot of B3's securities-lending market (*banco de títulos*, "BTB")
published in the Boletim Diário do Pregão: one row per instrument still on loan, carrying the
quantity of shares out on loan and the financial balance of those positions.

Column names are the API's PascalCase field names converted to ``UPPER_SNAKE_CASE`` by the BDI
base, so ``TckrSymb`` is declared here as ``TCKR_SYMB``.

Column names are confirmed against a **live** ``BTBLendingOpenPosition`` response and B3's
official *Posição em Aberto* glossary (v1, 05/09/2023). The source sends ten columns:
``RPT_DT`` (hidden report date), ``DT_REF`` (session), ``TCKR_SYMB``, ``ISIN``, ``COMPANY``,
``TYPE``, ``MARKET``, ``STOCK_BALANCE``, ``AVG_PRIC``, ``BALANCE``.

This is a **full-column** contract: ``tuple_required`` pins the source's *complete* header, in
order, and ``bool_full_column=True``. That is the honest shape for a fidelity ingestion reader
— the reader already types every one of these ten columns (via ``list_date_cols`` /
``dict_dtypes`` / ``list_decimal_cols``), so ``apply_dtypes`` already fails on a *missing*
column; pinning them here upgrades that to a clean :class:`ContractError` and, with the
full-column flag, additionally surfaces a B3-*added* column as drift instead of letting it slip
through untyped.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


# str_name, str_source_key (routes provenance), tuple_required (the full header, in source
# order), tuple_cnpj_cols, bool_full_column. No CNPJ column: this dataset keys on ticker
# symbols / ISINs, not legal entities.
BDI_BTB_LENDING_OPEN_POSITIONS = FileContract(
	"BDI BTB Lending Open Positions",
	"bdi_btb_lending_open_positions",
	(
		"RPT_DT",
		"DT_REF",
		"TCKR_SYMB",
		"ISIN",
		"COMPANY",
		"TYPE",
		"MARKET",
		"STOCK_BALANCE",
		"AVG_PRIC",
		"BALANCE",
	),
	(),
	bool_full_column=True,
)
