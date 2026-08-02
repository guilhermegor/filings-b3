"""Data contract — instruments file, ``DrvsOptnExrcInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``DrvsOptnExrcInf``** — exercício de opções sobre
derivativos.

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.7``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: the block declares **14** fields, all **14** populated across its 8,289 rows in
that session. Names follow the library convention (``pascal_to_upper_snake`` of the tag
abbreviation), adopting the consolidated reader's name wherever both publish the same tag.

⚠️ The catalog PDF renders the reference tag clipped to ``DerivOptnExrcInst`` — its columns cut
long tags. The real file spells it ``DerivOptnExrcInstrmId``; the declared ``[1..1]`` chain
(``4.7.7`` through ``4.7.7.2.1``) applies to it unchanged.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. ``AsstSttlmInd`` is an optional container (4,489 of
8,289 rows), so its ``[1..1]`` leaves are mandatory only *given* the container and are mapped but
not required. Optional fields flow through as typed columns, so a session in which B3 omits one
still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_DRVS_OPTN_EXRC = FileContract(
	"Pesquisa por Pregão Instruments File — DrvsOptnExrcInf",
	"instruments_file_drvs_optn_exrc",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"CLNR_DAYS",
		"DERIV_OPTN_EXRC_INSTRM_ID",
		"DERIV_OPTN_EXRC_INSTRM_ID_TP",
		"DERIV_OPTN_EXRC_INSTRM_ID_MKT_IDR_CD",
		"SCTY_CTGY_NM",
		"TCKR_SYMB",
		"WDRWL_DAYS",
		"WRKG_DAYS",
	),
	(),
)
