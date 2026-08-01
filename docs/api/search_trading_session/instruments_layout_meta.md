# **Metadados de layout de instrumentos (BVBG.028 UP2DATA)**

Leitura dos **metadados de layout** da família BVBG.028: a planilha autoritativa
`BVBG.028 para UP2DATA.xlsx` que a B3 publica, com um _sheet_ por tipo de arquivo e uma linha por
campo (nome, abreviação da _tag_, cardinalidade, tipo de dado, caminho XML no BVBG.028).

> **Veja também:** [Visão geral da seção](index.md) · [Arquivo de instrumentos](instruments_file.md)
> (o _reader_ de dados que este layout descreve) · [Uso](../../usage.md).

---

## Descrição

`InstrumentsLayoutMetaReader` baixa a planilha UP2DATA e parseia o _sheet_
`InstrumentsConsolidatedFile` (o layout do arquivo `IN` da Pesquisa por Pregão) em um **snapshot
tipado**: uma linha por campo declarado, já com o **nome de coluna canônico** derivado do mesmo jeito
que os _readers_ de dados derivam os seus — `pascal_to_upper_snake` da abreviação da _tag_ BVBG.028
(`TckrSymb` → `TCKR_SYMB`, `CFICd` → `CFICD`).

Colunas do _snapshot_: `COLUMN_ORDER` (`Int64`), `FIELD_NAME`, `FIELD_ABBREVIATION`,
`CANONICAL_COLUMN`, `CARDINALITY`, `DATA_TYPE`, `BVBG_PATH`, mais as seis colunas de proveniência
(incluindo `content_hash` da planilha bruta).

Como a fonte é uma planilha, o _reader_ reaproveita o _seam_ tabular (`read_table`, com o cabeçalho
na **segunda linha** — a primeira é o título do _sheet_), não o _seam_ XML. É um _snapshot_ atual,
então não recebe `date_ref`.

### Dois usos

- **Snapshot para _datalake_** — um registro versionável do layout que a B3 publica, com proveniência
  e `content_hash`, para que o _datalake_ consumidor guarde o histórico de como a especificação
  mudou ao longo do tempo.
- **Oráculo de deriva de contrato** — o job semanal `bin/check_contract_drift.py` lê o conjunto
  `CANONICAL_COLUMN` e o compara com o que o [_reader_ de instrumentos](instruments_file.md) mapeia.

---

## Exemplos

### Baixar o snapshot de layout

```python
from filings_b3.search_trading_session import InstrumentsLayoutMetaReader

df = InstrumentsLayoutMetaReader().read()
print(df[["COLUMN_ORDER", "FIELD_NAME", "CANONICAL_COLUMN", "BVBG_PATH"]].head())
```

### Manter a planilha bruta (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsLayoutMetaReader(path_raw=Path("/data/bronze/b3/meta")).read()
print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```

---

## Deriva de layout (job semanal)

A B3 pode mudar o layout **depois** de embarcarmos o _reader_. Nenhum _check_ de PR consegue pegar
isso — só um job que rebaixa o layout publicado. O `contract-drift.yaml` (semanal, `workflow_dispatch`)
roda `bin/check_contract_drift.py`, que:

1. baixa o layout via este _reader_ e extrai o conjunto de `CANONICAL_COLUMN`;
2. compara — **nos dois sentidos** — com o conjunto de colunas que o _reader_ de instrumentos mapeia;
3. **abre ou atualiza uma única issue** (label `contract-drift`) quando há divergência.

Os dois sentidos são sinais reais: uma coluna mapeada que **sumiu** do layout → o _reader_ passa a
produzir uma coluna silenciosamente nula; uma coluna do layout que o _reader_ **não mapeia** → a B3
adicionou um campo que deveríamos passar a ler. O job **nunca reprova o CI** — uma queda da B3 e uma
deriva real não podem virar o mesmo _check_ vermelho.
