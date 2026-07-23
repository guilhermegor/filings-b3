"""filings-b3 — typed access to B3 (Brazil's exchange) public datasets.

Six macro-sections organise every dataset, each named after the B3 source it reads from:

- ``daily_bulletin`` — Boletim Diário do Pregão (``arquivos.b3.com.br/bdi``).
- ``search_trading_session`` — Pesquisa por Pregão file downloads.
- ``platforms`` — PUMA trading-system schedules and calendars.
- ``indexes`` — theoretical portfolios and volatility, from the listed-systems proxies.
- ``market_data`` — consolidated trades, price/index reports and the legacy BMF portal.
- ``clearing`` — collateral (garantias) accepted by the clearing house.

Readers are re-exported here, so a consumer writes ``from filings_b3 import
BdiStocksSummaryReader``: the package layout organises the source tree, never the import.

Every reader returns a typed, contract-validated :class:`pandas.DataFrame` carrying provenance
columns, and accepts ``path_raw`` to keep the untouched source artifact for a datalake's bronze
layer. Nothing under ``filings_b3._internal`` is public API.
"""

from importlib.metadata import PackageNotFoundError, version

from filings_b3.daily_bulletin import BdiStocksSummaryReader


try:
	__version__ = version("filings-b3")
except PackageNotFoundError:  # pragma: no cover - source tree without an installed dist
	__version__ = "0.0.0"


__all__ = ["BdiStocksSummaryReader", "__version__"]
