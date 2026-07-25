# Second BDI reader — issue #4 (`b3_bdi_btb_lending_open_positions`)

Issue: #4. First migration on top of the shipped foundation (#3, #40), built deliberately as
the **reference layout** the remaining 36 daily-bulletin readers (#5–#42) copy.

## Done

- [x] **`BdiBtbLendingOpenPositionsReader`** — `daily_bulletin/btb_lending_open_positions.py`.
      Four declarations over `_BaseBdiReader` (`BTBLendingOpenPosition`, single-page); no
      implementation, the section base supplies the lifecycle.
- [x] **Contract verified against ground truth, not stpstone.** Fetched B3's official *Posição
      em Aberto* glossary PDF **and** a live `BTBLendingOpenPosition` response. The live API
      returns **10** columns; stpstone's module dropped **two** — `RptDt` (hidden report date,
      `hideColumn: true`) and `DtRef` (the visible session date). Both are now carried and typed.
      - `RPT_DT`/`DT_REF` → `list_date_cols` (ISO timestamps → `datetime.date`).
      - `AVG_PRIC`/`BALANCE` → `list_decimal_cols` (money, exact `Decimal`, source scale
        preserved — no quantisation at ingestion, unlike stpstone which rounded to 4dp/2dp).
      - Contract pins the **full** 10-column header in source order with `bool_full_column=True`
        (a B3-*added* column then surfaces as drift; a *removed* one already fails via
        `apply_dtypes`).
- [x] `contracts/daily_bulletin/btb_lending_open_positions.py`; re-exported through the section
      aggregator and `contracts/__init__.py`.
- [x] Re-exported from `daily_bulletin/__init__.py` and the package root; `_PUBLIC_SURFACE`
      widened deliberately in `tests/unit/test_api_boundary.py` (gate 1 working as designed).
- [x] `tests/unit/test_btb_lending_open_positions.py` — 8 tests; the fixture mirrors the **live**
      10-column payload (real PascalCase codes), and the exact-Decimal assertions are the ones a
      `float64` column cannot pass.

### Refactors made while this was the template (so #5+ inherit them)

- [x] **Contracts mirror `src/filings_b3/`.** Restructured into section subpackages
      (`contracts/daily_bulletin/…`); dropped the redundant `bdi_` filename prefix (moved the
      existing `stocks_summary` contract too). Widened the TID251 ruff glob to
      `contracts/**/*.py` so the subfolder keeps the `FileContract`-construction exemption.
- [x] **`_BaseBdiReader.read` is now an orchestrator**, not a 90-line method: `_paginate` (the
      page loop), `_finalize` (assemble → validate → type → stamp, once), `_read_page` (the
      single-page atomic unit) returning a `_Page` value object, and `_is_echoed_page` (the
      echo-detection predicate). Behaviour identical — base + both readers' tests pass unchanged.
- [x] **`_upper_snake` promoted** to `utils/text.pascal_to_upper_snake` (public) — a pure,
      domain-agnostic string transform belongs with the text utils, not buried in a reader.
      Covered in `tests/unit/test_text.py` (acronym / idempotent / digit-boundary cases added).
- [x] **`contracts/CLAUDE.md`** — records the authoritative B3 layout sources per section (BDI
      glossary; Pesquisa por Pregão layouts) and the reconcile-against-a-live-response workflow,
      so every future reader derives columns from B3, never from stpstone.

## Open

- [ ] **Re-verify #40 (`stocks_summary`) against the live API + glossary.** It has the same two
      latent issues this fixed: its columns came from stpstone (likely also missing
      `RptDt`/`DtRef`), and it uses a subset contract (`COL_ORDER` typed-but-not-required → a raw
      `KeyError` instead of a clean `ContractError` if B3 drops it). Same live-fetch pass.
- [ ] `docs/architecture.md` + the four-gates section in `docs/contributing.md` (carried over).
- [ ] Remaining 35 BDI datasets (#5–#42), then the other five sections.

## Notes

- Endpoint `limitDate` is `D-21`: the live API serves only a recent window, so a verification
  fetch must pick a date inside it (the glossary/layout gives the columns regardless).
- Release pending on merge: the reader is a shipped-artifact change → `/release-py` (minor).
