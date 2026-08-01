# **ADRs — arquivo de instrumentos (BVBG.028.02)**

Leitura do bloco **`ADRInf`** do arquivo de instrumentos do pregão (`IN{aammdd}.zip`),
publicado em `www.b3.com.br/pesquisapregao/download`. Registra os **ADRs** (_American Depositary Receipts_) registrados para a sessão, com o seu CUSIP, o nível do programa e a proporção em relação ao ativo subjacente.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Arquivo consolidado](instruments_file.md) para a visão de todos os tipos.

---

## Descrição

`InstrumentsFileAdrReader` baixa o **mesmo** `IN{aammdd}.zip` que os demais _readers_ da família, mantém apenas
os registros que carregam o bloco `ADRInf` e mapeia a lista **completa** de campos desse
bloco — **9** campos próprios, mais as colunas comuns a todo instrumento (data de
referência, identificação e atributos comuns), totalizando **22** colunas de origem.

Na sessão reconciliada (`IN260729`), o bloco trouxe **31** registros.

O layout vem da **taxonomia** autoritativa da B3 (`BVBG.028 para UP2DATA`, aba
`BVBG.028 - Taxonomia`) — a árvore completa de _tags_ com cardinalidade e tipo XSD — conferida
contra um arquivo `IN` real. Os nomes seguem a convenção da biblioteca:
`pascal_to_upper_snake` da abreviação do _tag_.

O contrato exige `ASST`, `ASST_DESC`, `CUSIP`, `MKT_IDR_CD`, `MKT_NM`, `OTHR_ID`, `PPSN`, `RPT_DT`, `SCTY_CTGY_NM`, `SGMT_NM`, `TCKR_SYMB`, `TRADG_CCY`. Os campos `[0..1]` do bloco fluem como colunas tipadas sem serem
obrigatórios, de modo que um pregão em que a B3 não preencha um campo opcional ainda é lido.

| Tipagem | Colunas |
|---------|---------|
| `datetime.date` | — |
| `decimal.Decimal` exato | `PPSN` |

As demais colunas preservam o texto exato da fonte.

Colunas monetárias carregam a sua **moeda** numa coluna companheira (`PPSN_CCY`, `TRADG_CCY`): no ISO-20022 a moeda de um valor é um *atributo* do elemento, e sem ela o número perderia a unidade.

---

## Exemplos

### Ler o bloco de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileAdrReader

df = InstrumentsFileAdrReader(date(2026, 7, 29)).read()
print(df.head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data.

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileAdrReader(
    date(2026, 7, 29), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

### Consolidado ou por tipo?

Uma leitura consolidada ([`InstrumentsFileReader`](instruments_file.md)) traz **todos** os tipos
sob o layout de 52 colunas publicado pela B3. Este _reader_ traz **um** tipo com **todos** os
campos que a B3 declara para ele — mais colunas, um tipo só. Os dois leem o mesmo download.
