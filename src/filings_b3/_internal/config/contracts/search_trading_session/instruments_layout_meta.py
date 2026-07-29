"""Data contract — B3's ``BVBG.028 para UP2DATA`` layout-metadata spreadsheet.

B3 publishes the authoritative field layout of the BVBG.028 instruments family as an XLSX
(``BVBG.028 para UP2DATA.xlsx``), one sheet per file type. The ``InstrumentsConsolidatedFile``
sheet is the layout of the Pesquisa por Pregão ``IN`` file that
:class:`~filings_b3.search_trading_session.instruments_file.InstrumentsFileReader` reads.

This contract pins the sheet's own **Portuguese header** (the columns a layout row carries: the
field name, its tag abbreviation, cardinality, data type, and BVBG.028 XML path). It is the input
contract for the metadata reader, distinct from ``INSTRUMENTS_FILE`` (which is the *data* contract
the XML must satisfy). The sheet's header sits on the **second row** — the first row is the sheet
title — so the reader passes ``int_header_row=1``.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


# Required = the layout columns the metadata reader depends on, by their exact Portuguese header.
# No CNPJ column: a layout spec keys on field names, not legal entities.
INSTRUMENTS_LAYOUT_META = FileContract(
	"BVBG.028 UP2DATA Instruments Layout",
	"instruments_layout_meta",
	(
		"Coluna",
		"Campo",
		"Abreviação do Campo",
		"Card.",
		"Tipo de Dado",
		"Campo no BVBG.028",
	),
	(),
)
