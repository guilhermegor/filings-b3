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
- **Instrumentos por tipo** — oito _readers_ que leem o **mesmo** `IN{aammdd}.zip` e projetam **um**
  bloco `InstrmInf` cada, com a lista **completa** de campos que a B3 declara para aquele tipo:
  [Ações](instruments_file_eqty.md) · [Opções sobre ações](instruments_file_optn_on_eqts.md) ·
  [Opções sobre disponível e futuros](instruments_file_optn_on_spot_and_futures.md) ·
  [Exercício de opções sobre ações](instruments_file_exrc_eqts.md) ·
  [Termo de ações](instruments_file_eqty_fwd.md) · [Renda fixa](instruments_file_fxd_incm.md) ·
  [ADRs](instruments_file_adr.md) · [BTC](instruments_file_btc.md).
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
que **não** cabe nessa forma — a família `instruments_file`, que é **XML aninhado** — usa a base
`_base_instruments_file_reader`, que implementa o _port_ `IngestionReader` diretamente,
reaproveitando os mesmos _seams_ internos (download com _retry_, retenção do artefato bruto,
proveniência), mas achatando o XML pelo _seam_ `xml_reader` em vez de ler uma tabela.

### Um download, nove _readers_

O `IN{aammdd}.zip` traz **um** XML em que cada registro `<Instrm>` aninha os seus campos
específicos sob **exatamente um** de 20 blocos `<InstrmInf>`. Daí duas formas de ler o mesmo
arquivo:

| Quero… | _Reader_ | Resultado |
|--------|----------|-----------|
| todos os tipos, layout publicado pela B3 | `InstrumentsFileReader` | 52 colunas, uma linha por instrumento de **qualquer** tipo |
| um tipo, com todos os campos dele | `InstrumentsFile<Tipo>Reader` | só os registros daquele bloco, com a lista **completa** de campos do tipo |

Os _readers_ por tipo herdam ainda as colunas de nível de registro comuns a todo instrumento
(data de referência, identificação e atributos comuns), que vivem **fora** do bloco — é o que
mantém os _frames_ por tipo comparáveis entre si.

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
