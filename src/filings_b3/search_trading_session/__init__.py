"""Pesquisa por Pregão — B3's per-trading-session file downloads.

Source: ``www.b3.com.br/pesquisapregao/download?filelist=<CODE>{yymmdd}.zip``. At 42 datasets
this is the library's largest macro-section, and every member is a genuine **file** download
(mostly ZIPs holding one or more tabular members), which is why it carries a section-local
Template-Method base (``_base_pregao_reader``) built around download → locate member → read.

Includes the ``IN`` instruments file and its eight variants, ``PR`` (price report), ``IR``
(index report), and the derivatives/equities/fee/FX families.

Every concrete reader is public from this section path — ``from
filings_b3.search_trading_session import InstrumentsFileReader``, the organised form — and
re-exported flat from the package root (``from filings_b3 import InstrumentsFileReader``) as a
backward-compatible convenience.
"""

__all__: list[str] = []
