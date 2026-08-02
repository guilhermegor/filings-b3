"""Data contract — instruments file, ``IntlBdInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``IntlBdInf``** — títulos internacionais.

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.15``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: **9** fields, all **9** populated across the block's 374 rows in that session.
``IssePric`` is an ISO-20022 amount, so it carries an ``ISSE_PRIC_CCY`` companion read from the
value's ``Ccy`` **attribute** — 10 columns from 9 fields.

Note the block's two distinct currency notions, deliberately kept apart: ``CCY`` (tag ``Ccy``) is
the bond's own denomination, while ``ISSE_PRIC_CCY`` is the unit of the issue price. They agree on
most rows but are different fields, and collapsing them would be a guess.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. Optional fields flow through as typed columns, so a
session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_INTL_BD = FileContract(
	"Pesquisa por Pregão Instruments File — IntlBdInf",
	"instruments_file_intl_bd",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"ISSE_DT",
		"ISSE_PRIC",
		"SCTY_CTGY_NM",
		"TP",
	),
	(),
)
