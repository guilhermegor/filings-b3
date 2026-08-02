"""Data contract — instruments file, ``FxdIncmInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``FxdIncmInf``** — renda fixa.

Columns are derived from B3's authoritative ``BVBG.028 para UP2DATA`` **taxonomy** sheet — the full
tag tree with each field's cardinality and XSD type — and cross-checked against a real
``IN260729.zip``: the block declares **13** fields, of which **13** carry a value in that session
(the rest are ``[0..1]`` fields B3 did not populate that day). Every field observed live was
present in the taxonomy, so the taxonomy is complete and authoritative here. Names follow the
library convention — ``pascal_to_upper_snake`` of the tag abbreviation.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are mandatory **all the way up** the tag tree and were
confirmed live. A ``[1..1]`` leaf inside an optional container — ``UndrlygInstrmId`` is
``[0..1]``, ``TrgtInstrmId`` is ``[0..*]`` — is mandatory only *given* that container, so it is
mapped but not required; an instrument with no underlying instrument is not a contract breach.
Optional fields flow through as typed columns, so a session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_FXD_INCM = FileContract(
	"Pesquisa por Pregão Instruments File — FxdIncmInf",
	"instruments_file_fxd_incm",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"ALLCN_RND_LOT",
		"DAYS_TO_STTLM",
		"PMT_TP",
		"PRIC_FCTR",
		"SCTY_CTGY_NM",
		"TCKR_SYMB",
		"TRADG_CCY",
		"UNDRLYG_INSTRM_ID",
		"UNDRLYG_INSTRM_ID_TP",
		"UNDRLYG_INSTRM_ID_MKT_IDR_CD",
	),
	(),
)
