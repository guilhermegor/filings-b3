# **Títulos internacionais — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`IntlBdInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os **títulos internacionais** da
sessão.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileIntlBdReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da
família, mantém apenas os registros que carregam o bloco `IntlBdInf` e mapeia a lista **completa**
de campos desse bloco — **9** campos declarados, publicados em **10** colunas próprias (uma delas
é a moeda do preço de emissão), mais as colunas comuns a todo instrumento, totalizando **23**
colunas de origem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **374** registros, com os **9** campos
preenchidos.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.15`), conferido contra a aba `BVBG.028 - Taxonomia` e contra um arquivo `IN` real.

!!! note "Duas noções de moeda, mantidas separadas de propósito"
    `CCY` (_tag_ `Ccy`) é a **denominação do título**; `ISSE_PRIC_CCY` é a **unidade do preço de
    emissão**, lida do atributo `Ccy` do valor. Elas coincidem na maioria das linhas, mas são
    campos diferentes — colapsá-las seria um palpite.

O contrato exige `ASST`, `ASST_DESC`, `ISSE_DT`, `ISSE_PRIC`, `MKT_IDR_CD`, `MKT_NM`, `OTHR_ID`,
`RPT_DT`, `SCTY_CTGY_NM`, `SGMT_NM`, `TP` — os campos `[1..1]` em **toda** a cadeia de ancestrais
e confirmados ao vivo.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `ISSE_DT`, `MTRTY_DT`, `RPT_DT` |
| `decimal.Decimal` exato | `ISSE_PRIC` |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileIntlBdReader

df = InstrumentsFileIntlBdReader(date(2026, 7, 29)).read()
print(df[["TCKR_SYMB", "ISIN", "CUSIP", "ISSR_CTRY", "ISSE_PRIC", "ISSE_PRIC_CCY"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileIntlBdReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
