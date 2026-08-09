"""BDI exchange-rate history — the Resolução BCB nº 120 official rates reader.

Reads B3's ``HistoricalExchange`` table from the Boletim Diário do Pregão: the official exchange
rates set by the Brazilian Central Bank, one row per (session, financial instrument). These are
the rates B3 itself uses to price currency-referenced futures and options, which is why they sit
under a regulatory resolution rather than in a general market feed.

Everything but the declarations below is inherited from
:class:`~filings_b3.daily_bulletin._base_bdi_reader._BaseBdiReader` — the fetch, the raw-page
retention, the positional-values → named-columns mapping, contract enforcement, dtype coercion
and provenance stamping.

Unlike the section's other datasets this one is **historical**: the endpoint serves the last five
complete years plus the current one (it declares ``limitDate: PDC_ANO-5``), so a caller can walk
back years one session at a time instead of being confined to a recent window.

Usage::

    from datetime import date
    from filings_b3.daily_bulletin import BdiHistoricalExchangeReader

    df = BdiHistoricalExchangeReader(date(2026, 8, 7)).read()

Keep the raw artifact for a datalake's bronze layer by passing ``path_raw``::

    df = BdiHistoricalExchangeReader(date(2026, 8, 7), path_raw=Path("/data/bronze/b3")).read()
"""

from __future__ import annotations

from filings_b3._internal.config.contracts import BDI_HISTORICAL_EXCHANGE
from filings_b3.daily_bulletin._base_bdi_reader import _BaseBdiReader


class BdiHistoricalExchangeReader(_BaseBdiReader):
	"""Reader for the BDI exchange-rate history (``HistoricalExchange``, Resolução BCB nº 120).

	Single-page: a session's rates arrive in one response, so the inherited ``int_max_pages = 1``
	default applies and is not overridden here.

	Attributes
	----------
	str_source_key : str
		Provenance source key for this dataset.
	str_endpoint : str
		B3's table name under ``arquivos.b3.com.br/bdi/table``.
	cls_contract : FileContract
		The columns a consumer may rely on.
	dict_field_renames : dict of {str: str}
		Restores the glossary's semantics where the endpoint publishes two fields under each
		other's names — the API's ``TckrSymb`` holds the *asset* (``DOL``) and its ``Symb`` holds
		the *instrument* (``RTDOLD2``), the reverse of the glossary. Publishing the API's naming
		would make ``TCKR_SYMB`` mean *asset* here while it means *instrument* in every
		``search_trading_session`` reader, so a consumer joining the two on that column would
		match an asset code against instrument tickers and get silence, not an error. See the
		contract module for the measured evidence.
	dict_dtypes : dict of {str: str}
		Explicit column types — never pandas' inference — covering **every** column the source
		sends, not only the contract's required ones.
	list_date_cols : tuple of str
		``RPT_DT`` is the trading session the rate belongs to.
	list_decimal_cols : tuple of str
		``PRIC_VAL`` is an exchange rate: it multiplies notionals, so its fractional part is the
		whole point. Kept as an exact :class:`decimal.Decimal` at the source's own scale — a
		``float64`` cannot hold ``5.0808`` exactly, and the error propagates into every contract
		priced off it.
	"""

	str_source_key = "bdi_historical_exchange"
	str_endpoint = "HistoricalExchange"
	cls_contract = BDI_HISTORICAL_EXCHANGE
	# Keyed by the API's own field names, applied before the UPPER_SNAKE_CASE conversion.
	dict_field_renames = {  # noqa: RUF012 - declarative class-level config, like dict_dtypes
		"TckrSymb": "Asst",
		"Symb": "TckrSymb",
	}
	dict_dtypes = {  # noqa: RUF012 - declarative class-level config, matching the base's contract
		"ASST": "str",
		"TCKR_SYMB": "str",
		"ECNC_IND_DESC": "str",
	}
	list_date_cols = ("RPT_DT",)
	list_decimal_cols = ("PRIC_VAL",)
