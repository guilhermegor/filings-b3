# Public layout + family architecture — decision record

Settles the layout question left open in `slim-ingestion-base_20260722_173356.md`. Blocks epic
#2 (105 dataset issues, #4–#108): every child copies whatever the first adapter establishes.

Evidence base: the 105 `b3_*.py` modules in
`stpstone/ingestion/countries/br/exchange/`, grouped by their **actual source URL** (not by
name), plus the `filings-cvm` layout as the mature sibling.

## 1. Macro-sections — derived from B3's own site taxonomy

Grouping is by source host + path, so it is evidence, not taste. All 105 datasets land, none
is orphaned.

| Macro-section | Source (host + path) | Count |
|---|---|---|
| `daily_bulletin` | `arquivos.b3.com.br/bdi/…` — Boletim Diário do Pregão | **39** |
| `search_trading_session` | `www.b3.com.br/pesquisapregao/download?filelist=…` | **42** |
| `platforms` | `www.b3.com.br/{pt_br,en_us}/solucoes/plataformas/puma-trading-system/…` | **13** |
| `market_data` | `sistemaswebb3-listados…/*Proxy/`, `arquivos.b3.com.br/api/`, `www.b3.com.br/pt_br/market-data-e-indices/`, `www2.bmf.com.br` | **8** |
| `clearing` | garantias / collateral accepted by the clearing house | **3** |
| | **total** | **105** ✅ |

Detail per section:

- **`daily_bulletin` (39)** — every `b3_bdi_*` issue, #4–#42. Sub-families visible in the names
  (`btb`, `derivatives`, `equities`, `fixed_income`, `indexes`, `securities`, `stocks`,
  `operations`, `clearing_adr_custody`). One host exception: `b3_bdi_stocks_trade_by_trade`
  serves from `drp.b3.com.br/rapinegocios/tickercsv/` — it is still the BDI trade-by-trade
  file, so it stays here; the differing host is a reader detail, not a section boundary.
- **`search_trading_session` (42)** — the 34 modules hitting `pesquisapregao` directly, plus
  the 8 `b3_instruments_file_*` variants, which in stpstone subclass `B3InstrumentsFile` and
  therefore inherit the same `?filelist=IN{}.zip` endpoint. Includes `b3_price_report` (`PR`),
  `b3_index_report` (`IR`), `b3_instruments_file` (`IN`).
- **`platforms` (13)** — the 12 `b3_trading_hours_*` datasets plus
  `b3_options_settlement_calendar`, all under
  `/solucoes/plataformas/puma-trading-system/para-participantes-e-traders/…`. This confirms
  the "platforms" intuition against B3's own URL structure — the section is literally
  *soluções → plataformas*. Note both `pt_br` and `en_us` variants appear; the reader picks
  the locale, the section does not split on it.
- **`market_data` (8)** — `b3_theor_portf_{ibov,ibra,ibrx50}` (`indexProxy`),
  `b3_historical_sigma` (`securitiesVolatilityProxy`), `b3_consolidated_trades{,_after_mkt}`
  (`arquivos.b3.com.br/api/download/requestname`), `b3_futures_closing_adj`
  (`www2.bmf.com.br` legacy portal), and
  `b3_updates_search_by_trading_session_update_time_series`
  (`/pt_br/market-data-e-indices/servicos-de-dados/`). ⚠️ That last one is *named* after the
  trading-session search but is served from **market-data**; grouping by URL catches what
  grouping by name would have mis-filed.
- **`clearing` (3)** — `b3_warranties_{br_sovereign_bonds,international_securities,
  stocks_units_etfs}`. These are the collateral (garantias) accepted by the clearing house.
  In stpstone they scrape HTML (`HtmlHandler`), so they are the section that will need the
  `scraping` extra — a good reason to keep them isolated behind their own section.

### Layout

```
src/filings_b3/
	__init__.py               # flat re-export of every public reader + explicit __all__
	daily_bulletin/
	search_trading_session/
	platforms/
	market_data/
	clearing/
	_internal/…               # unchanged, private
```

Rationale for keeping the macro-section as the top level rather than `ingestion/<section>/`:
this library has **one** macro-direction (there is nothing to submit to B3), and the root
`CLAUDE.md` bans a redundant package-name subfolder. `filings_cvm` needs `ingestion/` +
`submission/` because it genuinely has both; copying that split here would add a folder with
one child forever.

Consumers still write `from filings_b3 import BdiStocksSummaryReader` — the nesting organises
the source tree, never the import, exactly as `filings-cvm` does with its ~190 readers.

## 2. Divergence 1 — thin port vs fat Template-Method base

Asked for explicitly: pros and cons, not a verdict handed down.

**Keeping the fat base** (current `Reader`: `fetch → locate → read → stamp` inside `ports/`)

- ✅ 105 near-identical datasets. A concrete reader collapses to ~10 lines (URL, contract,
  dtypes) — roughly 1 000 lines total instead of ~4 000.
- ✅ A lifecycle bug (provenance, retry, raw-artifact handling) is fixed **once** for all 105.
- ✅ `__init_subclass__` enforces the three required attributes at import time; consistency is
  mechanical rather than reviewed.
- ❌ Template Method is inheritance. Every genuine variation needs a new hook, and B3's
  sources are heterogeneous (multi-member ZIPs, scraped HTML, JSON APIs, a legacy BMF portal).
  Hooks proliferate and the base accretes conditionals.
- ❌ Readers vary in **construction**, not just in URL (`date_ref` vs none vs a regime
  parameter). A rigid base fights that; `filings-cvm` hit exactly this at ~190 readers and
  chose composition.
- ❌ Cuts against "composition over inheritance" and "inheritance chains deeper than 2 levels"
  in the standing `common.md` rules.

**Recommendation — the two-tier shape `filings-cvm` actually converged on**, which is neither
extreme:

1. Keep the **port thin**: one abstract `read() -> pd.DataFrame`. It is the family-wide
   contract every sibling package shares, and it makes no claim about *how* the read happens.
2. Ship a **section-local Template-Method base** where the homogeneity is real — e.g.
   `daily_bulletin/_base_bdi_reader.py` for the 39 BDI files that truly do share one
   lifecycle, `search_trading_session/_base_pregao_reader.py` for the 42 `?filelist=` ones.

That is precisely `filings-cvm`'s structure (`_internal/config/ports/ingestion_reader.py` as
the contract + `ingestion/_base_meta_reader.py` as a section-local base beside the readers
that share it). The fat base survives where it pays for itself, the port stays reusable across
`filings-anbima-*` / `filings-rfb` / `pricefynance`, and the `clearing` scrapers are not forced
through a lifecycle built for CSV downloads.

Concretely: the current `Reader` body moves down into `daily_bulletin/_base_bdi_reader.py`
(and a sibling for the pregão family), and `ports/` keeps only the abstract `read()`.

## 3. Divergence 2 — `path_raw` is MANDATORY, family-wide

Confirmed as a hard architectural requirement, not a nicety: bedrock-fm needs a **datalake**
of raw artifacts (bronze) and a **datawarehouse** of treated data (silver/gold), on S3-compatible
object storage (open-source **rustfs** under consideration).

`filings-cvm` already has the exact seam — `_internal/utils/raw_workspace.py`, a context
manager whose docstring already names the bronze layer, S3, and rustfs by name:

- `path_raw=None` → a `TemporaryDirectory`, destroyed on exit (interactive consumer).
- `path_raw=<path>` → the directory is created (parents included) and **kept**, holding the
  downloaded artifact and everything extracted from it.
- It deliberately yields a plain `Path` and is *not* a storage abstraction; syncing that
  directory to object storage is the caller's concern. If an `s3://` URL is ever passed
  directly, the upgrade lands in that one function and **no reader changes**.

Action: port `raw_workspace.py` verbatim into filings-b3, and make
`path_raw: Path | None = None` the constructor convention on every reader. filings-b3's
current `Reader` uses a bare `TemporaryDirectory`, so the raw bytes are unrecoverable today.

→ **BlueprintX lesson**: every ingestion package scaffolded from `lib-minimal` ships
`raw_workspace` + the `path_raw` constructor convention. Non-negotiable: without it, a contract
break is unreproducible, because re-fetching returns an already-changed source.

## 4. Divergence 3 — naming: adopt the filings-cvm standard verbatim

| Concern | filings-cvm (standard) | filings-b3 (current) | Action |
|---|---|---|---|
| Port file | `_internal/config/ports/ingestion_reader.py` | `ports/reader.py` | rename |
| Port class | `IngestionReader` | `Reader` | rename |
| Port method | `read()` | `run()` | rename |
| Reader suffix | `<Domain>Reader` (`CdaReader`) | — | adopt |
| Docs | `docs/<section>/<dataset>.md` | — | adopt |

→ **BlueprintX lesson**: pin these names in the template so they are not re-invented per
package.

## 5. RetryPolicy — port it, and backport to python-common

filings-cvm's retry is an evolved **package**; filings-b3 still has the older single-module
decorator.

| | filings-cvm | filings-b3 |
|---|---|---|
| Shape | `_internal/utils/retry/` package | `_internal/utils/retry.py` |
| Modules | `policy.py`, `backoff.py`, `log_emitter.py`, `_schedule.py` | one file |
| `RetryPolicy` | frozen dataclass, validated in `__post_init__`, `metaclass=TypeChecker` | **absent** |
| Imperative form | `call_with_backoff` | **absent** (decorator only) |
| Public promotion | exported in `filings_cvm.__all__` | n/a |

`RetryPolicy` bundles five loose knobs (`int_max_attempts`, `float_base_wait_s`,
`float_factor`, `str_strategy`, `float_max_wait_s`, `tuple_exceptions`) into one value object a
reader builds once and forwards to the download seam, instead of threading them through every
call. It deliberately excludes the per-attempt socket timeout, which stays with
`download_file`. Per-reader tunability matters here: B3's portal throttles under load exactly
as CVM's does.

Agreed: wire it into filings-b3, and ship it in the BlueprintX **python-common** scaffold so
every tier gets it, not just `lib-minimal`. Note it is a *promotion* case for the boundary
harness — cvm exports `RetryPolicy` publicly while its implementation stays in `_internal`,
which is the pattern gate 1 was corrected to allow.

## 6. Where the boundary harness gets documented

filings-cvm publishes `docs/contributing.md` plus `docs/<section>/<dataset>.md` per dataset.
For the four gates:

- **`docs/architecture.md`** (new published page, registered in `mkdocs.yml` `nav:`) — the
  public/`_internal` contract, the macro-sections, and what consumers may rely on. This is
  consumer-facing: it tells them which imports are stable.
- **`docs/contributing.md`** — a short "the four gates" section explaining what fails CI and
  how to update the snapshot deliberately, linking to `architecture.md`. Contributor-facing.

Not a dedicated `docs/api_boundary.md`: the boundary is not a separate subject from the
architecture, and a page consumers will not read is a page that rots.

## SETTLED (2026-07-22)

1. **Section names: English.** `daily_bulletin`, `search_trading_session`, `platforms`,
   `indexes`, `market_data`, `clearing` — consistent with the rest of the codebase and the
   issue titles.
2. **Two-tier port.** Thin `IngestionReader` (abstract `read()` only) in
   `_internal/config/ports/`; the fat fetch → locate → read → stamp lifecycle moves down to a
   section-local `_base_*_reader.py` beside the readers that share it. Heterogeneous readers
   (the `clearing` scrapers) implement `read()` directly against the port.
3. **`market_data` splits into `indexes` + `market_data`.** The index/volatility products come
   from `sistemaswebb3-listados` proxy endpoints and share a shape; the trade/price files do
   not. Six sections total.

### Final section table

| Section | Source | Datasets |
|---|---|---|
| `daily_bulletin` | `arquivos.b3.com.br/bdi/…` | 39 |
| `search_trading_session` | `www.b3.com.br/pesquisapregao/?filelist=` | 42 |
| `platforms` | `/solucoes/plataformas/puma-trading-system/…` | 13 |
| `indexes` | `sistemaswebb3-listados…/{indexProxy,securitiesVolatilityProxy}/` | 4 |
| `market_data` | `arquivos…/api/`, `/pt_br/market-data-e-indices/`, `www2.bmf.com.br` | 4 |
| `clearing` | garantias (HTML-scraped → `scraping` extra) | 3 |
| | **total** | **105** ✅ |

- `indexes` (4): `b3_theor_portf_{ibov,ibra,ibrx50}`, `b3_historical_sigma`.
- `market_data` (4): `b3_consolidated_trades`, `b3_consolidated_trades_after_mkt`,
  `b3_futures_closing_adj` (legacy `www2.bmf.com.br` — expected to break independently),
  `b3_updates_search_by_trading_session_update_time_series`.

## Implementation order

1. [x] Port `_internal/utils/raw_workspace.py` from filings-cvm (+ 5 tests); `path_raw` adopted.
2. [x] Grow `_internal/utils/retry.py` into the `retry/` package with `RetryPolicy` +
   `call_with_backoff` (+ 18 ported tests — we previously had **zero** retry coverage). All three
   existing importers (`logs_emitter`, `http_downloader`, `ports`) were unaffected: they import
   `from …utils.retry import …`, which the package `__init__` still satisfies.
3. [x] Rename + thin the port: `ports/reader.py::Reader.run()` →
   `ports/ingestion_reader.py::IngestionReader.read()` (~230 lines → ~20).
4. [x] Move the fat lifecycle to `daily_bulletin/_base_bdi_reader.py`, now with `path_raw` +
   `cls_retry_policy`; test renamed to `test_base_bdi_reader.py`.
5. [x] `_url_filename` promoted to `_internal/utils/http_downloader.url_filename` — all six
   sections need it, and a copy per section is the DRY violation waiting to diverge.
6. [x] Deleted `ports/example_port.py` — the config leaf doc says the reference goes once a real
   port exists, and `IngestionReader` is that port.
7. [ ] First real adapter (issue #3's acceptance criterion) under `daily_bulletin/`, publishing
   the first non-`__version__` name and thereby exercising gate 1's snapshot.
8. [ ] `docs/architecture.md` + the gates section in `docs/contributing.md`.
9. [ ] Create the remaining five section packages as their first readers land — do **not**
   pre-create empty ones.

Status: **119 tests pass**, ruff clean.

## CORRECTION (2026-07-22) — BDI is a JSON API, not a file-download family

The first attempt put the **file-download** lifecycle (download → locate ZIP member → read by
extension) in `daily_bulletin/_base_bdi_reader.py`. Checking the actual transport proved that
wrong: **38 of the 39** BDI datasets are served by one paginated JSON API

```
https://arquivos.b3.com.br/bdi/table/<Endpoint>/<start>/<end>/<page>/<pageSize>
{"table": {"columns": [{"name": "TckrSymb"}, …], "values": [[…]]}}   # [] ⇒ past the last page
```

so there is no filename in the path, no extension for `read_table` to dispatch on, and the rows
are **positional arrays** that only acquire meaning zipped against `columns`. Pagination is part
of the lifecycle, not an afterthought.

Resolution — both bases are real, nothing was wasted:

| Base | Serves | Lifecycle |
|---|---|---|
| `daily_bulletin/_base_bdi_reader.py` | 38 BDI datasets | paginate → persist → assemble → validate → type → stamp |
| `search_trading_session/_base_pregao_reader.py` | 42 pregão datasets | download → locate member → read → stamp |

The file-download base simply belonged to the *other* section all along — the `?filelist=…zip`
family really is files. (`b3_bdi_stocks_trade_by_trade`, the 39th, serves CSV from
`drp.b3.com.br` and will implement the port directly.)

Two decisions taken while implementing:

- **Raw JSON pages are downloaded to disk, then parsed from the file** — never parsed from an
  in-memory response. With `path_raw` set, every page survives verbatim, including the original
  PascalCase column names, so a *future* parser version can re-interpret an artifact fetched
  today. A test asserts exactly that, because it is the datalake's whole reason to exist.
- **`date_ref` is required, with no default.** The BDI endpoint is date-addressed. Defaulting to
  "last business day" was rejected: whenever the guess is wrong (holiday, late publication,
  backfill) it silently reads a *different* session, which is far worse than failing at
  construction. It also avoids pulling in `wwdates` before a reader actually needs a calendar.

Open follow-up: provenance hashes **page 1 only**. For a multi-page read that is a partial
fingerprint — fine for identifying the source, insufficient for drift detection across the whole
result set. Revisit when the drift job lands.

## Flagged — `_internal/utils/sidecar_metadata.py` is CVM-branded and unused

The module exports **`cvm_meta_url()`** and documents CVM's `META/meta_<dataset>.txt`
convention — which **B3 does not publish** — and it has **zero importers** here. It is a
BlueprintX generalisation bug: the seam was lifted from filings-cvm into `python-common` with the
origin regulator's naming baked into the API, so every sibling package (`filings-anbima-*`,
`filings-rfb`, `pricefynance`) will inherit it too.

Captured as a lesson (global store + `docs/blueprintx-lessons.md`):
`template-reference-impls-must-be-domain-neutral`, which also corrects
`ingestion-import-sidecar-metadata-when-available` — that lesson's "Scaffold into" step is what
introduced the branded name.

**Recommend deleting the module from filings-b3** (unused, and wrong for this source), and
renaming it `example_meta_url` in the template. Left in place pending confirmation.

## Note — `path_raw` was already a captured lesson, not a new finding

`ingestion-reader-persists-raw-artifact.md` (filings-cvm, 2026-07-08) already specifies the whole
convention, names bedrock-fm's medallion warehouse, and even names **rustfs**. The gap was not
knowledge but **delivery**: the lesson was never backported into the template, so filings-b3
scaffolded without it and its reader used a bare `TemporaryDirectory`. Worth treating as evidence
that a lesson without a template change and a harness check does not actually propagate.
