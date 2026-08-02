"""Data contract — instruments file, ``StrtgyInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``StrtgyInf``** — estratégias (operações estruturadas).

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.8``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: the block declares **23** fields, all **23** populated across its 1,065 rows in
that session. Names follow the library convention (``pascal_to_upper_snake`` of the tag
abbreviation), adopting the consolidated reader's name wherever both publish the same tag —
notably ``SD_TP_CD1``/``SD_TP_CD2`` for the two legs.

**The legs repeat, so they are published per leg.** ``StrtgyLegList`` is ``[1..*]``: 1,012 of the
1,065 records carry **two** legs and 53 carry one. A single un-indexed path would silently keep
leg 1 and drop leg 2, so the reader maps ``StrtgyLegList[1]`` and ``StrtgyLegList[2]`` separately
and this contract requires only **leg 1** — leg 2 is legitimately absent on 53 records. This is the
same defect class as #149, where the leg columns were null on 100% of records because ``SdTpCd``
was mapped as a *child* of ``LegId``; the catalog PDF (``4.8.17.1``–``4.8.17.3``) independently
**confirms** that ``SdTpCd`` and ``UndrlygInstrmId`` are **siblings** of ``LegId``, as shipped.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. ``AsstSttlmInd`` is an optional container present on
just 3 records, so its ``[1..1]`` leaves are mapped but not required. Optional fields flow through
as typed columns, so a session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_STRTGY = FileContract(
	"Pesquisa por Pregão Instruments File — StrtgyInf",
	"instruments_file_strtgy",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"LEG_ID1",
		"SD_TP_CD1",
		"UNDRLYG_INSTRM_ID1",
		"UNDRLYG_INSTRM_ID_TP1",
		"UNDRLYG_INSTRM_ID_MKT_IDR_CD1",
		"SCTY_CTGY_NM",
		"TCKR_SYMB",
		"TRADG_END_DT",
		"TRADG_START_DT",
		"VAL_TP_NM",
	),
	(),
)
