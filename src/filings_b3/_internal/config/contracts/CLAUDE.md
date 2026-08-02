# CLAUDE.md — `_internal/config/contracts/`

Where each `FileContract`'s columns come from. The general rules (one contract per file, subset
vs full-column, TID251) live in the parent `config/CLAUDE.md`; this leaf answers the one
question that keeps recurring during migration: **what is the authoritative column spec, and how
do I confirm it?**

## Contracts mirror the package tree

Contracts are grouped into section subpackages that mirror `src/filings_b3/` one-for-one:

| Reader | Contract |
|--------|----------|
| `daily_bulletin/<dataset>.py` | `contracts/daily_bulletin/<dataset>.py` |
| `search_trading_session/<dataset>.py` | `contracts/search_trading_session/<dataset>.py` |

The section folder already names the macro-section, so the filename drops the redundant source
prefix — `daily_bulletin/stocks_summary.py`, **not** `bdi_stocks_summary.py`.

## ⛔ FIRST: confirm the layout source WITH THE USER, before writing the file

**Standing user rule (2026-08-01), non-negotiable:** *"always when starting the implementation of a
new file, check with me the layout that must be used as a data contract file, so we can stay in
tune that the correct one is being applied."*

So, **before** creating a new reader or contract — not at review time, not at PR time:

1. State the exact document you intend to treat as the data contract: **file / sheet / URL**, plus
   its **version** where it has one (the catalog PDF is versioned; the XLSX is not).
2. **Ask the user to confirm it is the right one, and wait.** Treat it as blocking. Choosing the
   wrong source silently poisons every column, and a green test suite will never reveal it — the
   reader is perfectly consistent with the wrong spec.
3. This applies **per new file, including a generated batch**. A batch is many new files at once,
   not an exemption from the check.

**When the published layout and a real artifact disagree, stop and surface it.** Do not let the
artifact quietly overrule B3's document: report the conflict, check *every* authoritative source
this file lists (the XLSX **and** the catalog PDF), and get the user's call.

That case is real, not hypothetical — see the `SdTpCd` example under "Reconcile the layout" below.

## The authoritative sources — B3's own layouts, never stpstone

`stpstone` is the *migration seed*, not the spec. It has been observed to **drop columns** the
real source sends (e.g. `btb_lending_open_positions` lost the two leading date columns
`RptDt`/`DtRef`). So a contract is derived from **B3's published layout**, then confirmed against
a **live response** — never copied from the stpstone module's column list.

| Section | B3 layout source |
|---------|------------------|
| `daily_bulletin` (BDI) | **Glossário — Dados Públicos**: one PDF per dataset. <https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/boletim-diario/dados-publicos-de-produtos-listados-e-de-balcao/glossario/> |
| `search_trading_session` (Pesquisa por Pregão) | **Layout dos arquivos**. <https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/layout-dos-arquivos/> |

### The contract-document hub — start here

The user curates every public-data contract PDF from this one page; go here first rather than
guessing a filename:

<https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/boletim-diario/dados-publicos-de-produtos-listados-e-de-balcao/>

Direct artifacts already pulled from it for the instruments family (both verified 2026-08-02):

| Document | URL | Standing |
|---|---|---|
| **Catálogo de Mensagens — Cadastro de Instrumento, v2.6** (BVBG.028.02, 101 pp) | [`b3.com.br/data/files/0B/A1/CA/73/…-Versao-2.6.pdf`](https://www.b3.com.br/data/files/0B/A1/CA/73/86072710547B5127AC094EA8/Catalogo-de-Mensagens-Cadastro-de-Instrumento-Versao-2.6.pdf) | authoritative on **structure + cardinality** |
| **Glossário — InstrumentsConsolidatedFile 2024** | [`b3.com.br/data/files/52/74/1E/14/…ConsolidatedFile%202024.pdf`](https://www.b3.com.br/data/files/52/74/1E/14/4BA6D8103152D4C8AC094EA8/Glossario%20InstrumentsConsolidatedFile%202024.pdf) | the consolidated reader's 52 columns |

⚠️ The catalog's old `bvmfnet.com.br` host is **dead** — use the `b3.com.br/data/files/` URL above.
⚠️ The catalog is dated **24/10/2017**. It gives every sub-block's field table with INDEX,
tag, cardinality and XSD type — but it is **stale on field lists** (it omits four `NtlBdInf`
fields that a live `IN` file carries) and its PDF columns **clip long tags**
(`DerivOptnExrcInstrmId` → `DerivOptnExrcInst`). Rule of thumb: **the document wins on shape,
the live artifact wins on presence.**

### ⛔ A doc that indicts SHIPPED code becomes its own issue — always

**Standing user rule (2026-08-02), mandatory.** When reading an authoritative document reveals
that **already-released** code is wrong — wrong path, duplicated or inconsistent column name,
missing field, stale field list — **open a `/issue` for it**, separate from whatever work
surfaced it. Never fold the fix silently into the current PR; never leave it as a checkpoint note.

This package is a published data contract. A defect left undocumented ships again on the next
release, and (as #149 proved) can survive several releases with a fully green suite — a subset
contract validates column *presence*, never *population* or *correctness*.

1. Finish reading the document, then **scope the blast radius across every sibling reader** — the
   same mistake usually repeats, so fix the class, not the one instance the doc happened to expose.
2. One issue per distinct defect, citing the document (file/sheet/URL + version) and the evidence
   (declared path/name vs observed).
3. Reference the new issues in the current PR body as follow-ups — never as `Closes`.

Download the matching PDF/layout and read it (it gives column order, PT/EN labels, and
semantics). Match the dataset by its **friendly name**, not a guessed filename — the glossary
lists e.g. "Empréstimos de Ativos - Posição em Aberto (BDI)" for `btb_lending_open_positions`.

## Reconcile the layout against a live response before trusting it

The glossary gives *descriptive* EN labels; the JSON API returns terse PascalCase field **codes**
(`TckrSymb`, `VlmTradedDay`) that the reader maps to `UPPER_SNAKE_CASE`. The layout confirms
*which* columns exist and their order; the live response confirms the exact field codes and value
shapes. Pull one page and read `table.columns[].name`:

```bash
curl -s -X POST \
  "https://arquivos.b3.com.br/bdi/table/<Endpoint>/<YYYY-MM-DD>/<YYYY-MM-DD>/1/3" \
  -H "Content-Type: application/json" -d '{}' | jq '.table.columns[].name'
```

Note the endpoint's `limitDate` (e.g. `D-21`): data exists only for a recent window, so pick a
date inside it. Some columns are hidden in the UI (`hideColumn: true`) but still ship in the
payload — carry and type them anyway (the reader must type **every** column the source sends).

Record in the contract's module docstring that the columns were verified this way, with the
glossary version date — so the next reader trusts the pattern instead of re-deriving it.

### A published layout can itself be WRONG — the artifact is the tiebreaker, the user is the judge

For `search_trading_session`, the authoritative sources are **two**, and they can disagree with each
other and with reality:

| Source | What it is |
|---|---|
| `BVBG.028 para UP2DATA.xlsx` | sheet `InstrumentsConsolidatedFile` = the IN file's 52-column flat layout; sheet `BVBG.028 - Taxonomia` = the full 450-row tag tree (cardinality + XSD type). URL pinned in `search_trading_session/instruments_layout_meta.py`. |
| BVBG.028 **catalog PDF** (v2.6) | B3's prose specification of the same message. |

Measured case (issue #149): the XLSX declares the strategy-leg path as
`<InstrmInf> - <StrtgyInf> - <StrtgyLegList> - <LegId> - <SdTpCd>`, and the reader copied it
faithfully — but in a **real** `IN` file `SdTpCd` is a **sibling** of `LegId`, not its child. The
path therefore never resolved and all four leg columns shipped `None` on 100% of 1,065 strategy
records, through several releases, with nothing red. The same sheet also gives legs 1 and 2
**identical** paths, distinguishing them only in the `Observações` prose.

Two lessons: a subset contract validates **column presence, never population**, so an all-null
column is a *suspected mapping bug* until justified — print them in every live reconcile and give
each a written verdict. And when the layout loses to the artifact, that is exactly the moment to
**ask the user** rather than to quietly follow the bytes.
