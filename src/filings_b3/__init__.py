"""filings-b3 — typed access to B3 (Brazil's exchange) public datasets.

Six macro-sections organise every dataset, each named after the B3 source it reads from:

- ``daily_bulletin`` — Boletim Diário do Pregão (``arquivos.b3.com.br/bdi``).
- ``search_trading_session`` — Pesquisa por Pregão file downloads.
- ``platforms`` — PUMA trading-system schedules and calendars.
- ``indexes`` — theoretical portfolios and volatility, from the listed-systems proxies.
- ``market_data`` — consolidated trades, price/index reports and the legacy BMF portal.
- ``clearing`` — collateral (garantias) accepted by the clearing house.

A reader is imported from **its own macro-section**, and only from there::

    from filings_b3.daily_bulletin import BdiStocksSummaryReader
    from filings_b3.search_trading_session import InstrumentsFileReader

The package root deliberately exports **no readers** — only ``__version__``. Up to 0.1.x every
reader was *also* re-exported flat from the root; that was dropped in **0.2.0** (issue #163)
because a flat surface does not survive the library's scale: with six macro-sections and ~105
datasets planned, the root would grow into a list of a hundred-odd names, which is precisely what
organising by section exists to prevent. The section path is unambiguous about *where* a dataset
comes from, and it stays a one-line import.

Every reader returns a typed, contract-validated :class:`pandas.DataFrame` carrying provenance
columns, and accepts ``path_raw`` to keep the untouched source artifact for a datalake's bronze
layer. Nothing under ``filings_b3._internal`` is public API.
"""

from importlib.metadata import PackageNotFoundError, version


try:
	__version__ = version("filings-b3")
except PackageNotFoundError:  # pragma: no cover - source tree without an installed dist
	__version__ = "0.0.0"


# Readers are NOT re-exported here — import them from their macro-section (see the module
# docstring). Keeping this list at one entry is the point of issue #163, not an oversight.
__all__ = ["__version__"]
