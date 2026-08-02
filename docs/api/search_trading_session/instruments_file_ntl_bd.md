# **Títulos públicos nacionais — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`NtlBdInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os **títulos públicos nacionais**
da sessão.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileNtlBdReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da
família, mantém apenas os registros que carregam o bloco `NtlBdInf` e mapeia a lista **completa**
de campos desse bloco — **12** campos declarados, publicados em **14** colunas próprias (duas
delas são a moeda dos valores monetários), mais as colunas comuns a todo instrumento, totalizando
**27** colunas de origem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **373** registros, com os **12** campos
preenchidos.

!!! warning "O catálogo v2.6 está defasado para este bloco"
    Datado de **24/10/2017**, o catálogo declara apenas **9** campos; um `IN260729.zip` real traz
    **4** a mais em 100% dos registros — `BRZLN_FDRL_GOVNT_BD_TP_CD`, `GOVNT_BD_REPO_GNL_IND`,
    `GOVNT_BD_REPO_SPCFC_IND` e `SCTY_LNDG_GOVNT_BD_IND` (o catálogo traz só uma linha de
    contêiner truncada, `BrzlnFdrlGovntBd`). A aba `BVBG.028 - Taxonomia` lista os 12. Eles são
    **mapeados** — descartar um campo que a fonte envia é perda silenciosa de dado — mas o contrato
    **não os exige**, já que nenhum documento vigente declara a cardinalidade deles. Reavaliar
    quando a B3 publicar um catálogo posterior à v2.6.

Os valores monetários carregam a moeda em uma **companheira** `<COL>_CCY`, lida do **atributo**
`Ccy` do próprio valor — no ISO-20022 a unidade é atributo, não elemento, e uma leitura só de
texto perderia a moeda de todo preço.

O contrato exige `ASST`, `ASST_DESC`, `ISSE_DT`, `MKT_IDR_CD`, `MKT_NM`, `MTRTY_DT`, `OTHR_ID`,
`RPT_DT`, `SCTY_CTGY_NM`, `SGMT_NM` — os campos `[1..1]` em **toda** a cadeia de ancestrais e
confirmados ao vivo.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `BASE_DT`, `ISSE_DT`, `MTRTY_DT`, `RPT_DT` |
| `decimal.Decimal` exato | `BASE_DT_PRIC`, `MTRTY_VAL` |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileNtlBdReader

df = InstrumentsFileNtlBdReader(date(2026, 7, 29)).read()
print(df[["TCKR_SYMB", "SELIC_CD", "MTRTY_DT", "MTRTY_VAL", "MTRTY_VAL_CCY"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileNtlBdReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
