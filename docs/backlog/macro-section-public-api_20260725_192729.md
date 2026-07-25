# #122 — expose macro-section subpackages as public API

Branch: `feat/122-expose-macro-section-public-api`

## Policy decided

Root **and** section are both public, stable import paths; only `filings_b3._internal` is private.
The **section path is the preferred organised form** (`from filings_b3.daily_bulletin import
BdiStocksSummaryReader`); the flat root re-export (`from filings_b3 import …`) stays as a
backward-compatible convenience. This reverses the prior docstring stance ("the nesting organises
the source tree, never the import").

## Done

- [x] Flipped the policy in three docstrings: `filings_b3/__init__.py`,
      `daily_bulletin/__init__.py`, `search_trading_session/__init__.py`.
- [x] Extended the boundary gate (`tests/unit/test_api_boundary.py`):
  - `_SECTION_SURFACE` frozen snapshot (one entry per public section; `search_trading_session`
    listed with an empty set — public path, no readers yet).
  - `_public_sections()` derives the public sections from the tree (dir + `__init__.py`,
    non-underscore), so a new section can't escape the gate.
  - `test_public_sections_match_the_frozen_snapshot` — a new section is a deliberate diff.
  - `test_public_section_surface_matches_the_frozen_snapshot` — each section's `__all__` is frozen.
  - `test_every_section_export_is_reexported_at_the_root` — the flat root convenience never rots.
- [x] Docs (pt-BR): `docs/api/reference.md` (header + examples + Convenções table), `docs/usage.md`,
      `docs/examples.md`, `README.md` — section import shown as the preferred organised form.
- [x] Verified: full unit suite 196 passed; boundary gate 51 passed; ruff + codespell clean; both
      import paths resolve to identical objects.

## Open / notes

- Only the **2 existing sections** are gated. The issue names 6 macro-sections; the other 4
  (`platforms`, `indexes`, `market_data`, `clearing`) don't exist on disk yet — deliberately NOT
  scaffolded (YAGNI). When each is created, add it to `_SECTION_SURFACE` (the derived-discovery
  test will fail until then, which is the intended forcing function).
- No version bump / release needed for the API surface itself unless the user wants one on merge
  (issue says run `/release-py` on merge; this is additive + backward-compatible → a minor bump).

Completed — kept as a record.
