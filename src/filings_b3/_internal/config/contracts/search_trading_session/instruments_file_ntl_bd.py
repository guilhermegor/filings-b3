"""Data contract — instruments file, ``NtlBdInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``NtlBdInf``** — títulos públicos nacionais.

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.14``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: **12** fields, all **12** populated across the block's 373 rows in that session.
Two of them are ISO-20022 amounts, so each carries a ``<COL>_CCY`` companion read from the value's
``Ccy`` **attribute** — 14 columns from 12 fields.

⚠️ **The catalog is dated 24/10/2017 and is stale for this block.** It declares 9 fields; the live
file carries 4 more — ``BrzlnFdrlGovntBdTpCd``, ``GovntBdRepoGnlInd``, ``GovntBdRepoSpcfcInd`` and
``SctyLndgGovntBdInd`` (the catalog has only a clipped ``BrzlnFdrlGovntBd`` container row). The
taxonomy sheet does list all 12. They are mapped — dropping a field the source sends is silent data
loss — but **not required**, since no current document declares their cardinality. Re-derive their
requiredness when B3 publishes a catalog newer than v2.6.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. Optional fields flow through as typed columns, so a
session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_NTL_BD = FileContract(
	"Pesquisa por Pregão Instruments File — NtlBdInf",
	"instruments_file_ntl_bd",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"ISSE_DT",
		"MTRTY_DT",
		"SCTY_CTGY_NM",
	),
	(),
)
