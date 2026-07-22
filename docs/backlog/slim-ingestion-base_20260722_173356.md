# Slim ingestion base + dep rewiring (foundation)

Issue: #3 — blocks the whole epic #2 (B3 dataset migration, ~40 open child issues #64–#108).
Branch: `feat/3-slim-ingestion-base`. Depends on #109 (import-package rename), already merged.

## What this branch delivers

The minimal ingestion seam that replaces `stpstone/ingestion/abc/ingestion_abc.py` and unties
the dependency hell: a Template-Method port owning **fetch → locate → read → stamp**, over the
existing `_internal` seams only (stdlib `urllib` + `tabular_reader` + `dtypes` + `provenance`).
No `stpstone`, no headless browser, no PDF engine at import time.

## Done

- [x] `_internal/utils/` seams in place and tested: `http_downloader` (stdlib `urllib`, SSRF
      guard, retry), `retry` (`LogEmitter` DI), `tabular_reader` (`FileContract` +
      `ContractError`), `dtypes`, `provenance` (`stamp_provenance` / `hash_artifact` /
      `resolve_package_version`), `zip_extractor`, `br_identifiers`, `typing/`.
- [x] Ingestion port authored as `_internal/config/ports/reader.py` — class `Reader`,
      `metaclass=ABCTypeCheckerMeta`, `__init_subclass__` guard on the three required class
      attributes (`str_source_key`, `cls_contract`, `dict_dtypes`), abstract `build_url()`,
      overridable `locate_table()` (identity by default, ZIP sources override).
- [x] **Placement decision**: the base lives under `_internal/config/ports/`, *not* at
      `src/filings_b3/_base_reader.py`. Rationale: the path itself must tell a consumer the
      seam is private — `_internal` is the marker the whole family (`filings-anbima-*`,
      `filings-rfb`, `pricefynance`) will share. Consequence, applied: the class dropped its
      `_` prefix (`_BaseB3Reader` → `Reader`) because `_internal` already carries the privacy
      signal, and `ports/` names the class after its file (`example_port.py` → `ExamplePort`).
- [x] `run()` **returns** a typed DataFrame — no DB insertion (deliberate departure from the
      monorepo's `cls_db` / `insert_table_db` base; a library has no runtime database).
- [x] `download_file` imported **inside** `run()`, so importing the package never triggers
      network setup.
- [x] `Reader` re-exported from `_internal/config/ports/__init__.py`.
- [x] `tests/unit/test_reader.py` (renamed from `test_base_reader.py` to mirror the module):
      8 offline tests — typed/contract-validated frame, provenance stamping, `ContractError`
      on a missing required column, `locate_table` identity, `__init_subclass__` guard,
      `_url_filename` derivation. `download_file` patched at its own module boundary.
- [x] Full unit suite green (52 passed), `ruff check` clean on `src/` + `tests/`.

## Open — in scope for #3

- [ ] **Delete `_internal/config/ports/example_port.py`** and its `__init__` re-export. The
      config leaf doc says the reference port goes once a real port exists — `Reader` is that
      port. Also drop the `ExamplePort` paragraphs from
      `src/filings_b3/_internal/config/CLAUDE.md`, replacing them with `Reader` as the worked
      example.
- [ ] **Decide and pin the public API surface.** `filings_b3.__all__` is still only
      `["__version__"]`. Concrete readers are the public product; `_internal` never is. Needs a
      decision on the public module layout (flat `src/filings_b3/<dataset>.py` per CLAUDE.md,
      or one aggregate module) *before* the first migration issue lands, because every child
      issue of #2 copies whatever shape the first one sets.
- [ ] Backport the boundary harness (below, now **done** here) into the BlueprintX
      `lib-minimal` template so every sibling package inherits it at scaffold time.
- [ ] **Proof-of-concept adapter**: one real B3 CSV/ZIP dataset end-to-end on `Reader`, with
      its own `FileContract` in `_internal/config/contracts/`. Pick the simplest child of #2
      (a direct-CSV source, no scraping). This is issue #3's acceptance criterion.
- [ ] **Acceptance test**: `import filings_b3` pulls neither `playwright`/`selenium` nor
      `fitz`/`pdfplumber` — assert on `sys.modules` after a clean import, not on prose.
- [ ] **Poetry extras** `pdf` (`fitz` / `pdfplumber`) and `scraping` (`playwright` /
      `selenium`), lazily imported only where needed. *Deferrable*: no module needs them yet,
      and 61 of the 105 source modules that will need `scraping` arrive with epic #2. Adding
      empty extras now is speculative — add each extra in the PR of the first module that
      imports it, and keep this box as the reminder that the `Reader` port must never grow a
      top-level import of either.
- [ ] **`wwdates` rewiring**: `stpstone.utils.calendars.calendar_br` / `calendar_abc` →
      `wwdates`. Only once a reader actually needs a business-calendar date; declare it in
      `pyproject.toml` in that same PR.
- [ ] **Docs**: `docs/usage.md` + `README.md` — what the public API is, that `_internal` is
      off-limits, the optional extras, and a worked example of the PoC reader.
- [ ] Merge the PR, then run `/release-py`.

## Harness — internal vs public (DONE, `tests/unit/test_api_boundary.py`)

The boundary is enforced by **gates**, not by a paragraph in a `CLAUDE.md`. A prose rule is a
probabilistic guard: it holds when whoever is editing happens to read it. 41 tests, all offline.

1. **Public-surface snapshot** — `__all__` equals a frozen set declared in the test, every
   exported name resolves, and none is underscore-private. Widening the API is a deliberate
   one-line diff.
2. **Import-direction gate** — AST walk over `_internal/**`: no import of the package's public
   layer, and no relative imports (enough leading dots escape the private tree).
3. **Published-docs gate** — no page MkDocs actually builds may show `<pkg>._internal`.
   `exclude_docs` is **parsed from `mkdocs.yml`**, not duplicated, so `docs/backlog/` stays
   exempt and a newly excluded folder cannot break the gate.
4. **Heavy-import gate** — `import <pkg>` in a **subprocess** must pull no
   `playwright`/`selenium`/`fitz`/`pdfplumber`. Subprocess is deliberate: an in-process
   `sys.modules` check passes merely because the package is not installed, and would rot the
   day `scraping` lands in the dev env.

Everything is **derived** (package name from `src/`, module list, published-docs set), so the
file ports to a sibling package with no edit; the only hand-maintained value is the snapshot,
which is hand-maintained *on purpose*. Each gate carries a non-empty-discovery meta-test so it
can never pass vacuously.

**Verified red-capable.** Each gate was mutation-tested (export added / upward import added /
`_internal` line added to a published doc / heavy-module list pointed at a module that *is*
imported); all four went red, then green after restore. A gate that cannot fail is not a gate.

### Correction from the filings-cvm recon

The originally proposed gate 1 was *"no exported name resolves into `_internal`"*. **That is
wrong**, and `filings-cvm` proves it: its `__all__` exports `RetryPolicy`, imported from
`filings_cvm._internal.utils.retry`. Promoting an internal type to public API via a deliberate
re-export in `__init__.py` is a *feature* — it keeps one implementation while giving it a public
name. The forbidden thing is the **consumer-facing import path**, which is what gate 3 guards.
The snapshot's job is only to make each promotion deliberate.

### Still to do for the family

Backport all four into BlueprintX `lib-minimal` as `tests/unit/test_api_boundary.py`,
parameterised by `<project_name>`, plus a ruff `TID251` `banned-api` entry for
`<pkg>._internal`. Template artifact, not per-project judgement — otherwise each new
`filings-*` package is a fresh coin-flip.

## Recon: how filings-cvm (the mature sibling) is laid out

Read on 2026-07-22 to settle the public-layout question. `filings-cvm` has ~190 public readers
across ~40 merged dataset issues, so its shape is evidence, not opinion.

```
src/filings_cvm/
	__init__.py          # flat re-export of ~190 names + explicit __all__ (incl. RetryPolicy)
	ingestion/           # macro-section 1 (leitura)
		_base_meta_reader.py         # section-local private base, NOT in _internal
		<portal_root>/<group>/<dataset>/<reader>.py
	submission/          # macro-section 2 (envio) — informe_diario.py, perfil_mensal.py
	_internal/
		config/ports/    # ingestion_reader.py, submission_writer.py
		config/contracts/<source>.py
		utils/
```

Findings that bear on filings-b3:

- **Two-level public layout**: `<pkg>/<macro-section>/<taxonomy…>/<reader>.py`, then flat-
  re-exported at the package root. A consumer writes `from filings_cvm import CdaReader`; the
  nesting organises the source, never the import.
- **The port is THIN.** `IngestionReader` is ~20 lines: one abstract `read() -> DataFrame`,
  `metaclass=ABCTypeCheckerMeta`, no lifecycle. Each concrete reader composes `download_file`
  + `read_table` + `stamp_provenance` + `raw_workspace` itself.
  ⚠️ **filings-b3's `Reader` diverges**: it is a ~230-line Template-Method base with the whole
  fetch → locate → read → stamp lifecycle inside `ports/`. Decide deliberately before the first
  adapter lands — see the open question below.
- **A section-local shared base lives in the public tree, `_`-prefixed**
  (`ingestion/_base_meta_reader.py`), *not* in `_internal`. So there are two tiers: the
  cross-section **port** under `_internal/config/ports/`, and an intermediate base beside the
  readers that share it.
- **Constructor convention `path_raw: Path | None = None`** — documented in the cvm port as
  "the convention every reader in this library *and every sibling ingestion package* follows".
  filings-b3's `Reader` has no `path_raw`; it uses a bare `TemporaryDirectory`. Adopting it
  would let a contract failure be replayed against the exact bytes that broke it, instead of
  re-fetching an already-changed source. **Recommend adopting** — it is the family convention
  and this library will hit the same class of failure.
- **Naming divergence**: cvm's port file/class is `ingestion_reader.py` / `IngestionReader`;
  filings-b3's is `reader.py` / `Reader`. Only one should survive into the template.
- **No API-boundary test exists in filings-cvm either** — the harness above is genuinely new
  work, and cvm is the first place it should be backported after the template.
- Gate culture to respect: cvm puts gates needing git/network in `bin/check_*.py` + a unit test
  (`check_contract_drift`, `check_portal_completeness`, `check_backlog_ledger`). Our four gates
  are pure and offline, so a single test file is the right shape — no `bin/` script needed.

## Open question — the public layout (blocks epic #2)

filings-b3 has **one** macro-section (ingestion only; there is nothing to submit to B3), so
cvm's `ingestion/` + `submission/` split does not transfer directly. The root `CLAUDE.md` rule
"no redundant package-name subfolder" argues against `filings_b3/ingestion/`. That leaves the
B3 dataset taxonomy (`trading_hours/`, `warranties/`, `theor_portf/`, …, visible in issues
#64–#108) as the organising axis, flat-re-exported at the root exactly as cvm does.

Consequence to settle before the first adapter: with one macro-section, `_internal/config/ports/`
holds a port with a single family of adapters — which the config leaf doc itself calls
over-abstraction. Either accept the port for family consistency (every sibling package carries
the same seam) or collapse it into a section-local `_base_reader.py`.

## Notes / decisions to revisit

- `Reader` is generic-free, unlike `ExamplePort[T]`: every adapter returns `pd.DataFrame`, so
  a type parameter with one inhabitant would be over-abstraction. Revisit only if a non-pandas
  return ever appears.
- The class name `Reader` is deliberately *not* B3-specific: the sibling packages
  (`filings-anbima-pub`, `filings-anbima-data`, `filings-rfb`, `pricefynance`) should carry the
  same `_internal/config/ports/reader.py::Reader` seam, so the scaffold can ship it verbatim.
