"""Data contract — instruments file, ``FutrCtrctsInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``FutrCtrctsInf``** — contratos futuros.

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.5``), which gives each field's tag, cardinality and XSD type, cross-checked against the
``BVBG.028 para UP2DATA`` taxonomy sheet and a real ``IN260729.zip``: the block declares **31**
fields, of which **30** carry a value in that session. The one absent field, ``PureGoldWght``, is
declared ``[0..1]`` — gold futures simply were not registered that day — so it is mapped but never
required. Names follow the library convention (``pascal_to_upper_snake`` of the tag abbreviation),
adopting the consolidated reader's name wherever both publish the same tag.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's 650 rows live. A ``[1..1]`` leaf inside an optional container is
mandatory only *given* that container — ``AsstSttlmInd`` (269/650) and ``UndrlygInstrmId``
(647/650) are both optional here — so those leaves are mapped but not required. Optional fields
flow through as typed columns, so a session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_FUTR_CTRCTS = FileContract(
	"Pesquisa por Pregão Instruments File — FutrCtrctsInf",
	"instruments_file_futr_ctrcts",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"CLNR_DAYS",
		"DLVRY_TP_NM",
		"PMT_TP",
		"TCKR_SYMB",
		"TRADG_CCY",
		"TRADG_END_DT",
		"TRADG_START_DT",
		"VAL_TP_NM",
		"WDRWL_DAYS",
		"WRKG_DAYS",
		"XPRTN_CD",
		"XPRTN_DT",
	),
	(),
)
