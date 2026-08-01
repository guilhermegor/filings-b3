"""Pesquisa por Pregão — B3's per-trading-session file downloads.

Source: ``www.b3.com.br/pesquisapregao/download?filelist=<CODE>{yymmdd}.zip``. At 42 datasets
this is the library's largest macro-section, and every member is a genuine **file** download
(mostly ZIPs holding one or more tabular members), which is why it carries a section-local
Template-Method base (``_base_pregao_reader``) built around download → locate member → read.

Includes the ``IN`` instruments file and its eight variants, ``PR`` (price report), ``IR``
(index report), and the derivatives/equities/fee/FX families.

**The instruments family is one download, nine readers.** ``IN{yymmdd}.zip`` holds a single
BVBG.028.02 XML in which every ``<Instrm>`` record nests its type-specific fields under exactly
one of 20 ``<InstrmInf>`` sub-blocks. :class:`InstrumentsFileReader` flattens every record on
B3's published 52-column UP2DATA layout; each ``InstrumentsFile<Type>Reader`` keeps the records
of one sub-block and maps that block's **complete** field list — more columns, one instrument
type. They share ``_base_instruments_file_reader`` and therefore one lifecycle.

Every concrete reader is public from **this section path, and only from here** — ``from
filings_b3.search_trading_session import InstrumentsFileReader``. The package root exports no
readers (issue #163, 0.2.0).
"""

from filings_b3.search_trading_session.instruments_file import InstrumentsFileReader
from filings_b3.search_trading_session.instruments_file_adr import InstrumentsFileAdrReader
from filings_b3.search_trading_session.instruments_file_btc import InstrumentsFileBtcReader
from filings_b3.search_trading_session.instruments_file_eqty import InstrumentsFileEqtyReader
from filings_b3.search_trading_session.instruments_file_eqty_fwd import (
	InstrumentsFileEqtyFwdReader,
)
from filings_b3.search_trading_session.instruments_file_exrc_eqts import (
	InstrumentsFileExrcEqtsReader,
)
from filings_b3.search_trading_session.instruments_file_fxd_incm import (
	InstrumentsFileFxdIncmReader,
)
from filings_b3.search_trading_session.instruments_file_optn_on_eqts import (
	InstrumentsFileOptnOnEqtsReader,
)
from filings_b3.search_trading_session.instruments_file_optn_on_spot_and_futures import (
	InstrumentsFileOptnOnSpotAndFuturesReader,
)
from filings_b3.search_trading_session.instruments_layout_meta import InstrumentsLayoutMetaReader


__all__ = [
	"InstrumentsFileAdrReader",
	"InstrumentsFileBtcReader",
	"InstrumentsFileEqtyFwdReader",
	"InstrumentsFileEqtyReader",
	"InstrumentsFileExrcEqtsReader",
	"InstrumentsFileFxdIncmReader",
	"InstrumentsFileOptnOnEqtsReader",
	"InstrumentsFileOptnOnSpotAndFuturesReader",
	"InstrumentsFileReader",
	"InstrumentsLayoutMetaReader",
]
