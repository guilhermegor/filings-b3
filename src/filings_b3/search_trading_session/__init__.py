"""Pesquisa por Pregão — B3's per-trading-session file downloads.

Source: ``www.b3.com.br/pesquisapregao/download?filelist=<CODE>{yymmdd}.zip``. At 42 datasets
this is the library's largest macro-section, and every member is a genuine **file** download
(mostly ZIPs holding one or more tabular members), which is why it carries a section-local
Template-Method base (``_base_pregao_reader``) built around download → locate member → read.

Includes the ``IN`` instruments file and its eight variants, ``PR`` (price report), ``IR``
(index report), and the derivatives/equities/fee/FX families.

Every concrete reader is re-exported here, and again from the package root, so consumers write
``from filings_b3 import InstrumentsFileReader`` — the nesting organises the source tree, never
the import.
"""

__all__: list[str] = []
