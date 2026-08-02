# **Exercício de opções sobre derivativos — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`DrvsOptnExrcInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os instrumentos de **exercício de
opções sobre derivativos** da sessão.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileDrvsOptnExrcReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da
família, mantém apenas os registros que carregam o bloco `DrvsOptnExrcInf` e mapeia a lista
**completa** de campos desse bloco — **14** campos próprios, mais as colunas comuns a todo
instrumento (data de referência, identificação e atributos comuns), totalizando **27** colunas de
origem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **8.289** registros, com os **14** campos
preenchidos.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.7`), que declara _tag_, cardinalidade e tipo XSD de cada campo, conferido contra a aba
`BVBG.028 - Taxonomia` e contra um arquivo `IN` real.

!!! note "O catálogo corta o nome do _tag_ de referência"
    O PDF do catálogo renderiza `DerivOptnExrcInst` — suas colunas truncam _tags_ longos. O arquivo
    real escreve `DerivOptnExrcInstrmId`, que é o caminho que resolve; a cardinalidade `[1..1]`
    declarada (`4.7.7` a `4.7.7.2.1`) vale sem alteração.

O contrato exige `ASST`, `ASST_DESC`, `CLNR_DAYS`, `DERIV_OPTN_EXRC_INSTRM_ID`,
`DERIV_OPTN_EXRC_INSTRM_ID_MKT_IDR_CD`, `DERIV_OPTN_EXRC_INSTRM_ID_TP`, `MKT_IDR_CD`, `MKT_NM`,
`OTHR_ID`, `RPT_DT`, `SCTY_CTGY_NM`, `SGMT_NM`, `TCKR_SYMB`, `WDRWL_DAYS`, `WRKG_DAYS` — os campos
`[1..1]` em **toda** a cadeia de ancestrais e confirmados ao vivo. `AsstSttlmInd` é um contêiner
opcional (4.489 dos 8.289 registros), então suas folhas são mapeadas sem serem obrigatórias.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `RPT_DT` |
| `decimal.Decimal` exato | — |

As demais colunas preservam o texto exato da fonte — `STTLM_IND_MLTPLR` é uma contagem inteira de
unidades de liquidação, não um multiplicador decimal.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileDrvsOptnExrcReader

df = InstrumentsFileDrvsOptnExrcReader(date(2026, 7, 29)).read()
print(df.head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileDrvsOptnExrcReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
