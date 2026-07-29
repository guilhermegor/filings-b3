# #143 — InstrumentsFileReader live reconcile against a real IN file

Branch: `fix/143-instruments-live-reconcile`. Unblocks release 0.1.4.

## Source

The user provided a genuine `IN260729.zip` (16.7 MB zip → one 663 MB BVBG.028.02 XML,
**183,164 instrument records**). Reconciled the reader — built against the UP2DATA layout — against
the real file.

## Corrections found (exactly why live-verify is mandatory)

- **Row tag was WRONG.** `_ROW_TAG = "InstrmRcrd"` (a guess) → the real element is **`<Instrm>`**.
  The reader would have returned **zero rows** against real data. Fixed.
- **RptParams is per-record**, not file-level: each `<Instrm>` carries its own
  `RptParams/RptDtAndTm/Dt`. Moved `RPT_DT` from `_DICT_SCALARS` (broadcast) to a per-record path in
  `_DICT_PATHS`; `_DICT_SCALARS` is now empty.
- **17 sub-block types, not 7.** The UP2DATA `InstrumentsConsolidatedFile` sheet enumerates 7
  (`EqtyInf`, `FutrCtrctsInf`, …); the real IN file has **17** under `<InstrmInf>` — also `ExrcEqtsInf`,
  `EqtyFwdInf`, `FxdIncmInf`, `DrvsOptnExrcInf`, `IntlBdInf`, `NtlBdInf`, `CshInf`, `OTCInf`,
  `FICInf`, `ADRInf`, `BTCInf`. My 7-alternative paths silently null-ed ticker/ISIN/dates for the
  other 10 types.
- **Namespace differs** (`urn:bvmf.052.01.xsd`, not `bvmf.100.02`) — harmless, the seam matches by
  **local name** (this validated that design choice).

## Fix: `*` wildcard in the xml_reader seam

Rather than enumerate 17 sub-blocks per column, added a **single-level `*` wildcard** to
`read_xml`'s path resolver (`_resolve_text`, now recursive): `InstrmInf/*/<tag>` matches whichever
sub-block a record carries. Each record has exactly one sub-block, so first-match is unambiguous.
Collapsed `_DICT_PATHS` from ~130 lines of alternatives to 52 single-path entries, and it
**auto-covers any sub-block type B3 adds later** (the drift job #139 still catches new *fields*).

## Verified against real data (pinned fixture)

`tests/fixtures/instruments_IN_sample.zip` — a 50-record slice of the real file, trimmed to cover
all 17 sub-block types (`scratchpad/build_fixture.py`). The reader on it:

- **50 rows** (row tag correct); `RPT_DT` 50/50 = `2026-07-29` (per-record date works);
  `ASST/ASST_DESC/SGMT_NM/MKT_NM` 50/50 (common block).
- `TCKR_SYMB` 36/50, `ISIN` 39/50 — the nulls are **legitimate**: the 5 sub-blocks without a
  `TckrSymb` (Csh/FIC/IntlBd/NtlBd/OTC) and 4 without ISIN (BTC/Csh/FIC/OTC). Cross-checked against
  the full-file grammar; the wildcard resolves the field for **every** type that carries it.
- Decimal columns stay exact.

## Checklist

- [x] `_ROW_TAG` → `Instrm`; `RPT_DT` per-record path; `_DICT_SCALARS` emptied
- [x] `*` wildcard in `read_xml` (+ unit test); `_DICT_PATHS` collapsed to 52 wildcard paths
- [x] Pinned real-data zip fixture + rewrote `test_instruments_file.py` against it
- [x] Reader docstring updated (verified note + memory ponytail); pending-reconcile ⚠ removed
- [x] Full suite 221 passed; ruff/format/mypy/typing/codespell clean; `mkdocs --strict` clean
- [x] Drift job #139 still valid (52 mapped columns unchanged — only paths changed)
- [ ] On merge: run `/release-py` to publish **0.1.4** (finally unblocked)

## Follow-ups (not blocking)

- **Memory**: `read_xml` loads the whole tree (~4 GB resident for the 660 MB file). Fine for a
  workstation + the weekly job; a `ponytail:` comment marks the iterparse-streaming upgrade path if
  a memory-constrained consumer needs it.
- **Richer coverage**: the 10 extra sub-block types carry fields beyond the UP2DATA 52 (e.g.
  `FxdIncmNonTrdblInf` has `IntrstRate`/`RskRatg`; `IntlBdInf` has `CUSIP`/`IssrCtry`). The reader
  keeps the 52 consolidated columns (what the drift job validates); a fuller per-type reader is a
  separate future scope.
