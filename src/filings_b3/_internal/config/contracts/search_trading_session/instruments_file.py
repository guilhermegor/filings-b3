"""Data contract — Pesquisa por Pregão consolidated instruments file (BVBG.028.02).

B3's ``IN{yymmdd}.zip`` from ``www.b3.com.br/pesquisapregao/download`` holds one ISO-20022
``InstrumentReport`` (BVBG.028.02) XML: the day's registered instruments, one record per
instrument, across every market (equities, futures, options, gold, strategies, fixed income).

Column layout is derived from B3's **authoritative** ``BVBG.028 para UP2DATA`` field mapping
(sheet ``InstrumentsConsolidatedFile``, 52 fields), which is B3's own canonical flattening of the
nested XML — each flat column maps to a BVBG.028 XML path, with type-specific alternatives (a
ticker lives under ``EqtyInf`` for an equity, ``FutrCtrctsInf`` for a future, …). Column names
follow the library convention — ``pascal_to_upper_snake`` of the BVBG.028 **tag abbreviation** (the
UP2DATA ``Abreviação``): ``TckrSymb`` → ``TCKR_SYMB``, ``CFICd`` → ``CFICD`` — matching
``daily_bulletin`` (never the full field name ``TickerSymbol``).

This is a **subset** contract (``bool_full_column=False``): it requires only the columns present on
**every** instrument regardless of type — the identity/classification block (``RptParams`` +
``FinInstrmAttrCmon`` + ``FinInstrmId``, all ``[1..1]``). The many type-specific ``[0..1]`` /
per-block fields flow through as typed columns but are not required, since an equity record has no
``XPRTN_DT`` and a future has no ``CRPN_NM``.

⚠️ **Pending live reconcile (issue #68).** The column set and XML paths come from the UP2DATA
layout; they have **not** yet been confirmed against a real ``IN`` file (the dev clock is
future-dated, so B3 currently serves an empty ZIP for reachable days). Before the reader merges,
capture one genuine ``IN{yymmdd}.zip`` as a fixture and reconcile the flattened header + the exact
UP2DATA column casing against this contract.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


# Required = the identity/classification columns present on every instrument record regardless of
# its market sub-block. No CNPJ column: instruments key on ticker/ISIN, not legal entities.
INSTRUMENTS_FILE = FileContract(
	"Pesquisa por Pregão Instruments File",
	"instruments_file",
	(
		"RPT_DT",
		"TCKR_SYMB",
		"ASST",
		"ASST_DESC",
		"SGMT_NM",
		"MKT_NM",
		"ISIN",
	),
	(),
)
