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

## The authoritative sources — B3's own layouts, never stpstone

`stpstone` is the *migration seed*, not the spec. It has been observed to **drop columns** the
real source sends (e.g. `btb_lending_open_positions` lost the two leading date columns
`RptDt`/`DtRef`). So a contract is derived from **B3's published layout**, then confirmed against
a **live response** — never copied from the stpstone module's column list.

| Section | B3 layout source |
|---------|------------------|
| `daily_bulletin` (BDI) | **Glossário — Dados Públicos**: one PDF per dataset. <https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/boletim-diario/dados-publicos-de-produtos-listados-e-de-balcao/glossario/> |
| `search_trading_session` (Pesquisa por Pregão) | **Layout dos arquivos**. <https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/layout-dos-arquivos/> |

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
