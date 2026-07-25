"""Boletim Diário do Pregão (BDI) — B3's daily trading bulletin datasets.

Source: ``arquivos.b3.com.br/bdi/…``. This is the largest of the library's six macro-sections
(39 datasets), and the most homogeneous — every member is a CSV/ZIP download over the same
lifecycle — which is why it carries a section-local Template-Method base
(``_base_bdi_reader``) rather than each reader composing the seams itself.

Sub-families follow B3's own naming: ``btb`` (securities lending), ``derivatives``,
``equities``, ``fixed_income``, ``indexes``, ``securities``, ``stocks``, ``operations``.

Every concrete reader is re-exported here, and again from the package root, so consumers write
``from filings_b3 import BdiStocksSummaryReader`` — the nesting organises the source tree,
never the import.
"""

from filings_b3.daily_bulletin.btb_lending_open_positions import (
	BdiBtbLendingOpenPositionsReader,
)
from filings_b3.daily_bulletin.stocks_summary import BdiStocksSummaryReader


__all__ = ["BdiBtbLendingOpenPositionsReader", "BdiStocksSummaryReader"]
