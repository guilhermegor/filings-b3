# #69–#77 — per-sub-block instruments readers

Branch: `feat/69-77-instruments-sub-block-readers`. Closes #69, #70, #71, #72, #73, #74, #76, #77.
**#75 is NOT in scope** — see "Scope correction" below.

## Checklist

- [x] `_base_instruments_file_reader.py` — section-local base shared by all 9 IN-file readers
- [x] `xml_reader` seam: `str_row_filter` (project one sub-block) + `@attr` path segment
- [x] 8 per-type readers + 8 contracts, generated from B3's authoritative taxonomy
- [x] Consolidated `InstrumentsFileReader` refactored onto the shared base (52 columns unchanged)
- [x] Public API (section + root `__all__`), boundary-gate snapshots, contracts aggregators
- [x] Docs: 8 pt-BR API pages + section index + `mkdocs.yml` nav + README section
- [x] Unit tests: seam (filter/attribute) + family invariants; full suite green
- [ ] Live reconcile against the real `IN260729.zip` — running, see "Validation"
- [ ] `mkdocs --strict` + full static gates before PR

## Scope correction — #75 is a different file

`b3_instruments_file_indicators` (#75) is **BVBG.029.02**, not a sub-block of the BVBG.028.02
instruments file. In stpstone it subclasses the search-trading-session base directly rather than
`B3InstrumentsFile`, and has no `tag_parent`. It therefore does **not** belong to this family and
stays open as its own dataset issue. The family is 8 readers, not 9.

## Why one base instead of nine readers

The nine `b3_instruments_file_*` modules in stpstone are the **same download** (`IN{yymmdd}.zip`)
read nine ways: each `<Instrm>` record nests its type-specific fields under exactly one of 20
`<InstrmInf>` sub-blocks. So the lifecycle lives once in `_base_instruments_file_reader` and each
reader declares only its projection (sub-block + field map + contract). The already-shipped
consolidated reader (#68) was refactored onto the same base, deleting its duplicated
`build_url` / `_locate_xml` / `read` / dtype-derivation.

Two projections, deliberately different:

| Reader | Columns | Pinned to |
|---|---|---|
| `InstrumentsFileReader` | 52, spans every type | B3's published UP2DATA layout (drift oracle) |
| `InstrumentsFile<Type>Reader` | common block + that block's complete field list | B3's BVBG.028 taxonomy |

The consolidated reader keeps `dict_common_paths = {}` **on purpose**: the contract-drift oracle
compares its mapped set against B3's declared 52-column layout, so inheriting extra common
columns would read as drift.

## Where the columns came from (never stpstone)

Per `contracts/CLAUDE.md`, contracts derive from B3's published layout and are confirmed live.

- **Spec** — the `BVBG.028 - Taxonomia` sheet of B3's `BVBG.028 para UP2DATA.xlsx` (450 field
  rows): the full tag tree with cardinality and XSD type. The hierarchical `INDEX` column
  reconstructs each field's exact XML path (a block anchor is written `4.0`, so a prefix `4`
  resolves through `4.0`).
- **Observation** — a real `IN260729.zip` (183,164 records), streamed with `iterparse`.
- **Result** — every field observed live was already in the taxonomy
  (`observed_not_in_spec = 0` across all 20 blocks), so the taxonomy is complete and
  authoritative. The readers map the taxonomy's full leaf set per block.

The UP2DATA sheets *other* than `InstrumentsConsolidatedFile` describe separate UP2DATA **files**
(`EquityInstrumentFile`, `OptionInstrumentFile`, …), **not** the IN file's sub-blocks — which is
why the taxonomy sheet, not those, is the source for this family.

## Three real bugs the reconciliation exposed

1. **Currency was being silently dropped.** ISO-20022 carries an amount's currency as a `Ccy`
   **attribute** of the amount element, and the `xml_reader` seam could only read element *text*.
   Every monetary column therefore lost its unit. Fixed in the seam (`@name` path segment), and
   each affected amount now has a companion `<COL>_CCY` column. Observed on 100% of records for
   `OptnOnEqtsInf/ExrcPric`, `EqtyInf/{MktCptlstn,RghtsIssePric,LastPric,FrstPric}`,
   `OptnOnSpotAndFutrsInf/ExrcPric`, `ADRInf/Ppsn`.
2. **stpstone's ADR module reads the wrong block** — `B3InstrumentsFileADR.transform_data` passes
   `tag_parent="FxdIncmInf"` (fixed income) while mapping ADR fields. Copy-paste bug in the seed;
   this migration uses `ADRInf`, confirmed live (31 records).
3. **Contracts over-required nested optional fields** — caught by the first live run, which is
   exactly why it exists. The taxonomy marks `UndrlygInstrmId/OthrId/Id` as `[1..1]`, but its
   *container* `UndrlygInstrmId` is `[0..1]` (and `TrgtInstrmId` is `[0..*]`): the leaf is
   mandatory only *given* the container. Requiring it made 3 readers demand a column that is
   legitimately null for any instrument with no underlying/target — `EqtyInf`,
   `OptnOnEqtsInf`, `OptnOnSpotAndFutrsInf`. Required is now computed by walking the whole
   ancestor chain, dropping `EqtyInf` 15→9, `ExrcEqtsInf` 7→4, `OptnOnEqts` 21→18,
   `OptnOnSpotAndFutrs` 21→18 required columns.

**Known limitation (deliberate):** `TrgtInstrmId` is `[0..*]` — a record may carry several target
instruments and the reader keeps the **first**, matching how the consolidated reader treats the
strategy legs. No observed record in `IN260729` has more than one; revisit if one appears.

## Naming decisions

- Canonical column = `pascal_to_upper_snake` of the BVBG tag, matching `daily_bulletin`.
- Where the bare leaf collides, the name is qualified by its parent: a block's own
  `UndrlygInstrmId` / `TrgtInstrmId` / `OptnExrcInstrmId` references repeat the record's own
  ISO-20022 identification shape (`OthrId/Id`, `OthrId/Tp/Prtry`, `PlcOfListg/MktIdrCd`). The
  boilerplate wrappers are dropped so the column names the thing identified
  (`UNDRLYG_INSTRM_ID`, `UNDRLYG_INSTRM_ID_TP`, `UNDRLYG_INSTRM_ID_MKT_IDR_CD`).
- Where both the consolidated reader and a per-type reader publish the same tag, the per-type
  reader **adopts the consolidated reader's name** (`SctyCtgy` → `SCTY_CTGY_NM`, from UP2DATA's
  `Abreviação`). One field must not have two names across readers of one file — consumers join
  these frames.
- Generic record-level leaves are parent-qualified: `OTHR_ID`, `OTHR_ID_TP`, `INSTRM_DESC`
  (a bare `DESC` is a reserved word in most SQL engines).

## Validation

- Full suite green before the live run (237 passed, +44 new family tests, +5 new seam tests).
- Live reconcile: each reader run against the real `IN260729.zip` through its own configuration,
  asserting row counts against an independent sub-block census and that no contract-required
  column is null. Expected counts: `OptnOnEqtsInf` 133,875 · `EqtyInf` 14,479 · `ExrcEqtsInf`
  14,477 · `OptnOnSpotAndFutrsInf` 8,289 · `EqtyFwdInf` 676 · `FxdIncmInf` 424 · `ADRInf` 31 ·
  `BTCInf` 7.

## Open / follow-ups

- **The consolidated reader still drops the `Ccy` attribute** on its 5 decimal columns. Not fixed
  here: its column set is pinned to B3's 52-column UP2DATA layout by the drift oracle, so adding
  currency columns is a separate, deliberate decision. **File an issue.**
- `read_xml` still parses the whole tree (~4 GB resident for the 660 MB file) — a per-type read
  costs the same as the consolidated one even when it keeps 31 rows. Carried from #143; the
  upgrade path is an `iterparse` stream keyed on the row tag.
- The drift oracle covers **only** the consolidated reader. Extending it to the per-type readers
  means diffing against the taxonomy sheet rather than the UP2DATA layout sheet.
- 12 sub-blocks of the 20 have no reader yet (`FutrCtrctsInf`, `StrtgyInf`, `DrvsOptnExrcInf`,
  `NtlBdInf`, `IntlBdInf`, `FxdIncmNonTrdblInf`, `OTCInf`, `CshInf`, `FICInf`, and the three gold
  blocks) — no open issue requests them; the base makes each a ~40-line declaration if wanted.
