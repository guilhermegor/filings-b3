# #139 — metadata snapshot + contract-drift detector

Branch: `feat/139-metadata-drift-detector` (also carries the #68 naming reconcile, its prerequisite).

## Checklist

- [x] `InstrumentsLayoutMetaReader` (layout snapshot reader) + `INSTRUMENTS_LAYOUT_META` contract
- [x] `bin/check_contract_drift.py` — layout-aware symmetric oracle + issue upsert (replaced stub)
- [x] `.github/workflows/contract-drift.yaml` — weekly, non-blocking
- [x] Public API + boundary gate + section docs + nav
- [x] Unit tests (oracle + meta reader); full suite 218 passed; all static gates clean
- [x] #68 naming reconcile (prerequisite, commit 97bb7b2)
- [ ] Live reconcile of `_ROW_TAG` against a real `IN.zip` (carried from #68) — before release
- [ ] Extend to sibling UP2DATA file types (#69–#77) as those readers land

## What shipped

The filings-cvm META + contract-drift pattern, adapted to B3 (whose authoritative metadata is a
downloadable **layout spreadsheet**, not a CKAN META endpoint).

- **`InstrumentsLayoutMetaReader`** (`search_trading_session/instruments_layout_meta.py`) — public
  reader that downloads B3's authoritative `BVBG.028 para UP2DATA.xlsx`, parses the
  `InstrumentsConsolidatedFile` sheet (header on row 1, below the sheet title → `int_header_row=1`)
  into a typed **layout snapshot**: one row per field with `COLUMN_ORDER`, `FIELD_NAME`,
  `FIELD_ABBREVIATION`, `CANONICAL_COLUMN` (`pascal_to_upper_snake` of the tag abbreviation),
  `CARDINALITY`, `DATA_TYPE`, `BVBG_PATH` + provenance (incl. `content_hash`). The datalake snapshot
  for marketdata-fm. Reuses the tabular seam (XLSX is tabular). Contract `INSTRUMENTS_LAYOUT_META`.
- **`bin/check_contract_drift.py`** — REPLACED the dead scaffold stub (it imported `from config
  import contracts` / a `contract_oracles.yaml` that never existed under the `filings_b3._internal`
  layout, wired into nothing — see git `8b41881 first commit`). The new one is layout-aware:
  symmetric `layout_drift(mapped, layout)` oracle comparing the reader's mapped column set against
  B3's declared layout, opening/updating ONE tracking issue (label `contract-drift` + hidden
  marker). Always exits 0 (non-blocking). Fetch tolerates a B3 outage (skip, not drift).
- **`.github/workflows/contract-drift.yaml`** — weekly (Mon 05:23 UTC) + `workflow_dispatch`,
  non-blocking, `issues: write`, `concurrency` guard. Mirrors cvm's; kept out of the PR/release path
  (conftest blocks the network so it can't run at test time).

## Validation

- **mapped=52, layout=52, 0 drift** against the real XLSX — proves the #68 reader mapping is complete
  and correct vs B3's authoritative layout, and the oracle reports no drift on a match.
- Unit tests: `test_check_contract_drift.py` (pure oracle, both directions, mapped-set derivation),
  `test_instruments_layout_meta.py` (synthetic XLSX, canonical names, provenance, blank-row drop).
- Full suite **218 passed**; ruff/format/mypy/check_typing clean; docs gate 0; `mkdocs --strict`
  clean; codespell clean.

## Prerequisite included: #68 naming reconcile (commit 97bb7b2)

The library convention (daily_bulletin) names columns `pascal_to_upper_snake` of the BVBG tag
abbreviation (`TckrSymb`→`TCKR_SYMB`, `CFICd`→`CFICD`). #68 had diverged (full field name,
`TICKER_SYMBOL`). Reconciled the 52 instruments columns to the canonical convention — required so the
drift oracle can normalize the XLSX `Abreviação` to the same names.

## Open / notes

- Only the **BVBG.028 instruments** asset is gated. The UP2DATA XLSX covers 29 file variants across
  ~11 sheets (Equity/Future/Option/Gold/Swap/Debenture/…); extend `_META_MEMBERS`-style wiring as
  those readers land (#69–#77).
- `contract-drift` label is auto-created by the first issue POST (GitHub creates missing labels).
- Still open from #68: the **live reconcile** of `_ROW_TAG="InstrmRcrd"` + the single-XML-member
  assumption against a real `IN.zip` (the 52-column *mapping* is now proven; the row tag is not).
- Release 0.1.4 (feat) is due but **held** until the #68 row-tag live reconcile.

## Lesson (generalizable)
The metadata-snapshot reader + symmetric drift oracle + weekly non-blocking issue-upsert workflow is
a BlueprintX candidate (cvm + b3 both have it now). Capture on merge.
