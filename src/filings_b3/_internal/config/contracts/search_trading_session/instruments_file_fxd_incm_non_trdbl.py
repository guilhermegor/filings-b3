"""Data contract — instruments file, ``FxdIncmNonTrdblInf`` block.

B3's ``IN{yymmdd}.zip`` holds one BVBG.028.02 ``InstrumentReport`` XML whose every ``<Instrm>``
record nests its type-specific fields under exactly one of 20 ``<InstrmInf>`` sub-blocks. This
contract covers the records carrying **``FxdIncmNonTrdblInf``** — renda fixa não negociável.

Columns come from B3's **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (block anchor
``4.20``), cross-checked against the ``BVBG.028 para UP2DATA`` taxonomy sheet and a real
``IN260729.zip``: the block declares **46** fields, of which **39** carry a value across its 144
rows in that session. Three of them are ISO-20022 amounts carrying a ``<COL>_CCY`` companion read
from the value's ``Ccy`` **attribute** — 49 columns from 46 fields. This is the widest of the 20
sub-blocks.

The seven fields absent from the reconciled session — ``EarlyRedDt``, ``PerptlDbnrInitlPmt``,
``PmtPrdctyTp``, ``SpcfctnNm`` and the three ``TrgtInstrmId`` leaves — are all declared ``[0..1]``
(or sit under the ``[0..*]`` ``TrgtInstrmId`` container), so their absence is a legitimate
non-population, not a mapping bug. They are mapped so a session that does carry them reads.

``IntrstRateCrrctnTmBase`` is present in the live file but **not** in the 2017 catalog (whose
neighbouring row is the clipped ``IntrstRateCrrctnT``); the taxonomy sheet lists it. It is mapped
but not required, since no current document declares its cardinality.

This is a **subset** contract (``bool_full_column=False``): it requires the record-level identity
columns plus this block's fields that are ``[1..1]`` **all the way up** the tag tree *and* were
populated on 100% of the block's rows live. ``AsstInd`` is an optional container present on 13 of
144 rows, so its ``[1..1]`` leaves are mapped but not required. Optional fields flow through as
typed columns, so a session in which B3 omits one still reads.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


INSTRUMENTS_FILE_FXD_INCM_NON_TRDBL = FileContract(
	"Pesquisa por Pregão Instruments File — FxdIncmNonTrdblInf",
	"instruments_file_fxd_incm_non_trdbl",
	(
		"RPT_DT",
		"OTHR_ID",
		"MKT_IDR_CD",
		"ASST",
		"ASST_DESC",
		"MKT_NM",
		"SGMT_NM",
		"CRPN_NM",
		"DSTRBTN_ID",
		"EARLY_RED_IND",
		"ISSE_CD",
		"ISSE_DT",
		"SCTY_CTGY_NM",
		"SRS_NB",
		"TCKR_SYMB",
		"TRADG_CCY",
		"TTL_SRS_ISSE_VAL",
		"UNIT_VAL",
		"XPRTN_DT",
	),
	(),
)
