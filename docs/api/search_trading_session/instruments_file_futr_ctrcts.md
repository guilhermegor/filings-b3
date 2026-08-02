# **Contratos futuros — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`FutrCtrctsInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os **contratos futuros** da sessão.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileFutrCtrctsReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da
família, mantém apenas os registros que carregam o bloco `FutrCtrctsInf` e mapeia a lista
**completa** de campos desse bloco — **31** campos próprios, mais as colunas comuns a todo
instrumento (data de referência, identificação e atributos comuns), totalizando **44** colunas de
origem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **650** registros, com **30** dos 31 campos
preenchidos. O único ausente, `PURE_GOLD_WGHT`, é declarado `[0..1]` — não houve futuro de ouro
registrado naquele pregão — e por isso é mapeado mas nunca exigido.

O layout vem do **Catálogo de Mensagens — Cadastro de Instrumento v2.6** da B3 (âncora de bloco
`4.5`), que declara _tag_, cardinalidade e tipo XSD de cada campo, conferido contra a aba
`BVBG.028 - Taxonomia` e contra um arquivo `IN` real. Os nomes seguem a convenção da biblioteca:
`pascal_to_upper_snake` da abreviação do _tag_, adotando o nome do _reader_ consolidado onde os
dois publicam o mesmo _tag_.

O contrato exige `ASST`, `ASST_DESC`, `CLNR_DAYS`, `DLVRY_TP_NM`, `MKT_IDR_CD`, `MKT_NM`,
`OTHR_ID`, `PMT_TP`, `RPT_DT`, `SGMT_NM`, `TCKR_SYMB`, `TRADG_CCY`, `TRADG_END_DT`,
`TRADG_START_DT`, `VAL_TP_NM`, `WDRWL_DAYS`, `WRKG_DAYS`, `XPRTN_CD`, `XPRTN_DT` — os campos
`[1..1]` em **toda** a cadeia de ancestrais e confirmados ao vivo. Os contêineres opcionais do
bloco (`AsstSttlmInd`, presente em 269 registros; `UndrlygInstrmId`, em 647) têm suas folhas
mapeadas sem serem obrigatórias: uma folha `[1..1]` só é obrigatória **dado** o seu contêiner.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | `DLVRY_NTCE_END_DT`, `DLVRY_NTCE_START_DT`, `RPT_DT`, `TRADG_END_DT`, `TRADG_START_DT`, `XPRTN_DT` |
| `decimal.Decimal` exato | `ASST_QTN_QTY`, `CTRCT_MLTPLR`, `PURE_GOLD_WGHT` |

As demais colunas preservam o texto exato da fonte.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileFutrCtrctsReader

df = InstrumentsFileFutrCtrctsReader(date(2026, 7, 29)).read()
print(df.head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileFutrCtrctsReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
