"""Data contract — instruments file, ``FICInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``FICInf``** — fundos de investimento (FIC).

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.16``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: **3** fields, all **3** populated across the block's 2 rows in that session.

⚠️ The block carried only **2** rows in the reconciled session. That is enough to confirm the
mapping resolves, but too few to treat "populated on every row" as strong evidence of
requiredness; the cardinalities below come from the catalog, not from the sample.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. Optional fields flow through as typed columns, so a
session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_FIC = FileContract(
	"Pesquisa por Pregão Instruments File — FICInf",
	"instruments_file_fic",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"FND_NM",
		"SCTY_CTGY_NM",
	),
	(),
)
