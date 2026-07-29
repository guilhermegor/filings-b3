# **Pesquisa por Pregão**

A seção `filings_b3.search_trading_session` lê os arquivos por pregão da B3, baixados de
`www.b3.com.br/pesquisapregao/download?filelist=…`. Cada dataset é um **arquivo** (em geral um ZIP,
às vezes contendo XML ou vários membros tabulares); um _reader_ transforma um pregão em um
`pandas.DataFrame` tipado, validado por contrato e com proveniência.

> **Veja também:** [Visão geral da API](../index.md) · [Uso](../../usage.md) · [Exemplos](../../examples.md)

---

## Padrões implementados

- **[Arquivo de instrumentos (BVBG.028.02)](instruments_file.md)** — `InstrumentsFileReader`: lê o
  `IN{aammdd}.zip` do pregão (um XML ISO-20022 `InstrumentReport`) e devolve uma linha por
  instrumento registrado — ações, futuros, opções, ouro, estratégias e renda fixa — achatando os
  blocos específicos de cada tipo num único _frame_. Inaugura esta seção e é a base da família de 9
  variantes de instrumentos.
- **[Metadados de layout (BVBG.028 UP2DATA)](instruments_layout_meta.md)** —
  `InstrumentsLayoutMetaReader`: baixa a planilha autoritativa de layout da B3 e devolve um _snapshot_
  tipado dos campos declarados (para o _datalake_ e para o job semanal de deriva de contrato).

Cada padrão ganha a sua própria página, com **Descrição** e **Exemplos**. Ao migrar um novo dataset
desta seção, acrescente uma página nesta pasta e registre-a no `nav:` do `mkdocs.yml` no mesmo
commit.

---

## Duas formas de _reader_ nesta seção

A maioria dos datasets desta seção são downloads **tabulares** (CSV/ZIP) e compartilham a base
_Template-Method_ `_base_pregao_reader` (download → localizar membro → ler → carimbar). Uma fonte
que **não** cabe nessa forma — o `instruments_file`, que é **XML aninhado** — implementa o _port_
`IngestionReader` diretamente, reaproveitando os mesmos _seams_ internos (download com _retry_,
retenção do artefato bruto, proveniência), mas achatando o XML pelo _seam_ `xml_reader` em vez de
ler uma tabela.

Todo _reader_ tem a mesma forma pública:

```python
Reader(date_ref: datetime.date, path_raw: pathlib.Path | None = None) -> Reader
Reader.read() -> pandas.DataFrame
```

| Parâmetro | Tipo | Significado |
|-----------|------|-------------|
| `date_ref` | `datetime.date` | Pregão a ler. **Obrigatório** — o endpoint é endereçado por data. |
| `path_raw` | `pathlib.Path`, opcional | Diretório onde **manter** o artefato bruto baixado (camada _bronze_ do _datalake_). `None` (padrão) usa um diretório temporário removido ao final. |

---

## Colunas de proveniência

Todo `DataFrame` devolvido carrega, **ao lado** das colunas de origem, seis colunas de
**proveniência** — `url`, `updated_at` (UTC, tz-aware), `source_key`, `package_version`,
`ingestion_run_id`, `content_hash` — anexadas **depois** da validação de contrato, para que a camada
_bronze_ seja autodescritiva e rastreável.

---

## Artefato bruto — `path_raw`

- **`None` (padrão)** — o artefato é baixado num diretório temporário, lido e **descartado**.
- **Um caminho** — o artefato **bruto e intacto** (`.zip`) é gravado ali e **mantido**, _antes_ de
  qualquer _parsing_ — os bytes exatos que uma quebra de contrato produziria ficam reproduzíveis.

---

## Validação por contrato

Cada _reader_ declara um `FileContract` (privado, em
`_internal/config/contracts/search_trading_session/`) que fixa as colunas obrigatórias. Uma fonte
que viola o contrato levanta `ContractError`. Colunas monetárias e quantidades são `decimal.Decimal`
exato, nunca `float` binário.
