# **Renda fixa não negociável — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`FxdIncmNonTrdblInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os instrumentos de **renda fixa não
negociável** da sessão — debêntures e afins, cadastrados mas fora do livro de ofertas.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileFxdIncmNonTrdblReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_
da família, mantém apenas os registros que carregam o bloco `FxdIncmNonTrdblInf` e mapeia a lista
**completa** de campos desse bloco — **46** campos declarados, publicados em **49** colunas
próprias (três delas são a moeda dos valores monetários), mais as colunas comuns a todo
instrumento, totalizando **62** colunas de origem. É o **mais largo** dos 20 sub-blocos.

Na sessão reconciliada (`IN260729`), o bloco trouxe **144** registros, com **39** dos 46 campos
preenchidos. Os sete ausentes — `EARLY_RED_DT`, `PERPTL_DBNR_INITL_PMT`, `PMT_PRDCTY_TP`,
`SPCFCTN_NM` e as três folhas de `TRGT_INSTRM_ID` — são todos `[0..1]` (ou pendem do contêiner
`[0..*]` `TrgtInstrmId`), logo a ausência é não-preenchimento legítimo, não erro de mapeamento.
Ficam mapeados para que um pregão que os traga seja lido.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.20`), conferido contra a aba `BVBG.028 - Taxonomia` e contra um arquivo `IN` real.

!!! note "Um campo mais novo que o catálogo"
    `INTRST_RATE_CRRCTN_TM_BASE` está presente no arquivo real mas **não** no catálogo de 2017
    (cuja linha vizinha é o truncado `IntrstRateCrrctnT`); a aba de taxonomia o lista. É mapeado,
    mas não exigido, já que nenhum documento vigente declara sua cardinalidade.

Os valores monetários carregam a moeda em uma **companheira** `<COL>_CCY`, lida do **atributo**
`Ccy` do próprio valor — no ISO-20022 a unidade é atributo, não elemento.

O contrato exige `ASST`, `ASST_DESC`, `CRPN_NM`, `DSTRBTN_ID`, `EARLY_RED_IND`, `ISSE_CD`,
`ISSE_DT`, `MKT_IDR_CD`, `MKT_NM`, `OTHR_ID`, `RPT_DT`, `SCTY_CTGY_NM`, `SGMT_NM`, `SRS_NB`,
`TCKR_SYMB`, `TRADG_CCY`, `TTL_SRS_ISSE_VAL`, `UNIT_VAL`, `XPRTN_DT` — os campos `[1..1]` em
**toda** a cadeia de ancestrais e confirmados ao vivo. `AsstInd` é um contêiner opcional (13 dos
144 registros), então suas folhas são mapeadas sem serem obrigatórias.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `ASST_REGN_DT`, `BASE_DT`, `EARLY_RED_DT`, `ISSE_DT`, `PERPTL_DBNR_INITL_PMT`, `RPT_DT`, `TRADG_END_DT`, `TRADG_START_DT`, `XPRTN_DT` |
| `decimal.Decimal` exato | `FRST_PRIC`, `INDX_PCTG`, `INTRST_RATE`, `LAST_PRIC`, `MKT_CPTLSTN`, `TTL_SRS_ISSE_VAL`, `UNIT_VAL` |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileFxdIncmNonTrdblReader

df = InstrumentsFileFxdIncmNonTrdblReader(date(2026, 7, 29)).read()
print(df[["TCKR_SYMB", "CRPN_NM", "SRS_NB", "UNIT_VAL", "INTRST_RATE", "XPRTN_DT"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Filtrar debêntures perpétuas

```python
perpetuas = df[df["PERPTL_DBNR_IND"] == "true"]
```

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileFxdIncmNonTrdblReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
