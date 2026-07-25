# #132 — reorganize docs into section-mirroring per-reader pages

Branch: `docs/132-section-mirroring-docs`

## Decision

Adopt the filings-cvm docs pattern: the docs tree mirrors the code's macro-sections. Chosen layout
(user): **per-reader pages under `api/`** (honors b3's own `api/index.md` manifesto), one folder per
section, each section with an overview `index.md` + one page per reader.

## Done

- [x] `docs/api/daily_bulletin/index.md` — BDI section overview: reader catalog + shared prose
      (reader shape, 6 provenance columns, `path_raw` bronze layer, contract validation). No
      retry-policy prose (b3 readers don't expose it — that's cvm-only).
- [x] `docs/api/daily_bulletin/btb_lending_open_positions.md` — Descrição (full 10-col contract) +
      Exemplos. Columns from the contract + reader dtypes.
- [x] `docs/api/daily_bulletin/stocks_summary.md` — Descrição (3-col subset contract) + Exemplos.
- [x] `docs/api/index.md` — rewrote the single-row table into a 6-section map (`daily_bulletin`
      linked; other 5 listed as _planejada_, no dead links) + concrete convention line.
- [x] `mkdocs.yml` — nested `Referência da API` nav group; removed `api/reference.md` line.
- [x] Deleted `docs/api/reference.md` (content split into the two reader pages).
- [x] Fixed links to the deleted page: `docs/usage.md` (→ `api/index.md`), `README.md` (2 reader
      URLs → new per-reader page URLs).

## Verification (run before PR)

- [ ] `poetry run python bin/check_docs_sections.py` → exit 0
- [ ] `poetry run mkdocs build --strict` → no warnings (broken links / unregistered pages)
- [ ] `poetry run pytest tests/unit/test_api_boundary.py -q` → published-docs gate green
- [ ] codespell on changed docs (pt-BR vocab)

## Notes

- Only `daily_bulletin/` created; the other 5 sections are born with their first reader (YAGNI).
- Docs-only → no wheel diff → `s:release` correctly reports no release on merge.
