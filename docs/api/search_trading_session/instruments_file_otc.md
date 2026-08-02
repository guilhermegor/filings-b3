# **Balcão (OTC) — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`OTCInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os instrumentos de **balcão
(OTC)** da sessão.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileOtcReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da família,
mantém apenas os registros que carregam o bloco `OTCInf` e mapeia a lista **completa** de campos
desse bloco — **3** campos próprios, mais as colunas comuns a todo instrumento (data de
referência, identificação e atributos comuns), totalizando **16** colunas de origem.

Este é o bloco **mais estreito** da família: a substância de um instrumento de balcão vive nas
colunas comuns de nível de registro (identificação, ativo, mercado, segmento), que o _reader_
herda — o quadro é bem mais largo do que os três campos próprios sugerem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **6** registros, com os **3** campos
preenchidos.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.11`), conferido contra a aba `BVBG.028 - Taxonomia` e contra um arquivo `IN` real.

!!! warning "Amostra pequena"
    O bloco trouxe apenas **6** registros na sessão reconciliada. É o bastante para confirmar que
    o mapeamento resolve, mas pouco para tratar "preenchido em todas as linhas" como evidência
    forte de obrigatoriedade — as cardinalidades vêm do catálogo, não da amostra.

O contrato exige `ASST`, `ASST_DESC`, `CTRCT_TP`, `MKT_IDR_CD`, `MKT_NM`, `OTHR_ID`, `RPT_DT`,
`SGMT_NM`, `TRAD_ORGN_CD`.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `RPT_DT` |
| `decimal.Decimal` exato | — |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileOtcReader

df = InstrumentsFileOtcReader(date(2026, 7, 29)).read()
print(df[["OTHR_ID", "ASST", "CTRCT_TP", "TRAD_ORGN_CD", "FNGB_IND"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileOtcReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
