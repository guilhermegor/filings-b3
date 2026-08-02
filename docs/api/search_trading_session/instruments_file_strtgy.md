# **Estratégias (operações estruturadas) — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`StrtgyInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra as **estratégias** — operações
estruturadas montadas a partir de duas pernas.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileStrtgyReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da
família, mantém apenas os registros que carregam o bloco `StrtgyInf` e mapeia a lista **completa**
de campos desse bloco — **23** campos declarados, publicados em **28** colunas próprias (as pernas
repetem) mais **2** colunas resolvidas por auto-junção, totalizando **43** colunas de origem com as
colunas comuns a todo instrumento.

Na sessão reconciliada (`IN260729`), o bloco trouxe **1.065** registros, com os **23** campos
preenchidos.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.8`), conferido contra a aba `BVBG.028 - Taxonomia` e contra um arquivo `IN` real.

### As pernas repetem — e por isso são publicadas por perna

`StrtgyLegList` é `[1..*]`: na sessão reconciliada **1.012** dos 1.065 registros trazem **duas**
pernas e **53** trazem uma. Um caminho sem índice manteria silenciosamente a perna 1 e descartaria
a perna 2, então cada campo de perna é mapeado duas vezes — `StrtgyLegList[1]` e
`StrtgyLegList[2]` — com o sufixo `1`/`2` do _reader_ consolidado. O contrato exige **apenas a
perna 1**: uma estratégia de perna única é válida.

!!! warning "Regressão de #149"
    Na versão original, as colunas de perna do _reader_ consolidado vinham nulas em **100%** dos
    registros porque `SdTpCd` fora mapeado como **filho** de `LegId`. O catálogo v2.6
    (`4.8.17.1`–`4.8.17.3`) confirma de forma independente que `SdTpCd` e `UndrlygInstrmId` são
    **irmãos** de `LegId`, exatamente como corrigido.

Cada perna publica o subjacente **duas vezes**: `UNDRLYG_INSTRM_ID{n}` é o identificador
proprietário bruto que o documento declara, e `UNDRLYG_TCKR_SYMB{n}` é esse identificador
resolvido para o _ticker_ do instrumento referenciado por **auto-junção** no próprio documento —
as mesmas colunas do _reader_ consolidado, de modo que os dois não possam discordar.

O contrato exige `ASST`, `ASST_DESC`, `LEG_ID1`, `MKT_IDR_CD`, `MKT_NM`, `OTHR_ID`, `RPT_DT`,
`SCTY_CTGY_NM`, `SD_TP_CD1`, `SGMT_NM`, `TCKR_SYMB`, `TRADG_END_DT`, `TRADG_START_DT`,
`UNDRLYG_INSTRM_ID1`, `UNDRLYG_INSTRM_ID_MKT_IDR_CD1`, `UNDRLYG_INSTRM_ID_TP1`, `VAL_TP_NM`.
`AsstSttlmInd` é um contêiner opcional (3 registros), então suas folhas são mapeadas sem serem
obrigatórias.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `RPT_DT`, `TRADG_END_DT`, `TRADG_START_DT`, `XPRTN_DT` |
| `decimal.Decimal` exato | — |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileStrtgyReader

df = InstrumentsFileStrtgyReader(date(2026, 7, 29)).read()
print(df[["TCKR_SYMB", "SD_TP_CD1", "UNDRLYG_TCKR_SYMB1", "SD_TP_CD2", "UNDRLYG_TCKR_SYMB2"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Separar as estratégias de perna única

```python
uma_perna = df[df["SD_TP_CD2"].isna()]
duas_pernas = df[df["SD_TP_CD2"].notna()]
```

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileStrtgyReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
