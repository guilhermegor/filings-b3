"""Data contract — BDI exchange-rate history (``HistoricalExchange``).

The official exchange rates set by the Brazilian Central Bank, published in B3's Boletim Diário
do Pregão under **Resolução BCB nº 120**: one row per (session, financial instrument), carrying
the rate B3 uses to price currency-referenced futures and options.

Unlike every other BDI dataset shipped so far, this one is **historical**: the endpoint declares
``limitDate: PDC_ANO-5``, i.e. the last five complete years plus the current one, so a caller can
walk back years rather than only the recent window.

## Authoritative layout

**Glossário Dados Públicos — `EconomicIndicatorPriceFile`, 28/04/2023 (revision 2, Abril/2023)**:
<https://www.b3.com.br/data/files/75/F3/42/23/A59C781064456178AC094EA8/EconomicIndicatorPriceFile%20_1_.pdf>

Confirmed with the repository owner before this contract was written, per the standing rule. The
glossary defines the field **codes** (`RptDt`, `Asst`, `TckrSymb`, `EcncIndDesc`, `PricVal`); the
sibling `Glossario_Indicadores_economicos.pdf` covers the *other* table (`EconomicIndicators`) and
gives Portuguese labels only, so it cannot serve as the code-level contract here.

## ⚠️ The endpoint's field names are SHIFTED against the glossary

Measured on a live response — the API publishes two of the glossary's fields under each other's
names:

| Glossary code | API field | Observed value | Meaning |
|---------------|-----------|----------------|---------|
| ``Asst``      | ``TckrSymb`` | ``DOL``     | the commodity/asset |
| ``TckrSymb``  | ``Symb``     | ``RTDOLD2`` | the financial instrument |

The reader therefore renames them back to the **glossary's** semantics: the asset is published as
``ASST`` and the instrument as ``TCKR_SYMB``. Following the API's naming instead would make
``TCKR_SYMB`` mean *asset* in this section while it means *instrument* in every
``search_trading_session`` reader — violating the one-field-one-column-name rule (#165) and, worse,
letting a consumer join ``DOL`` against instrument tickers with no error at all.

``tuple_required`` lists only what a consumer depends on, so B3 adding a column is not a breaking
change while a removed one still fails loudly.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


# str_name (human label), str_source_key (routes provenance), tuple_required, tuple_cnpj_cols.
# No CNPJ column: this dataset keys on instrument symbols, not legal entities.
BDI_HISTORICAL_EXCHANGE = FileContract(
	"BDI Historical Exchange Rates",
	"bdi_historical_exchange",
	("RPT_DT", "ASST", "TCKR_SYMB", "PRIC_VAL"),
	(),
)
