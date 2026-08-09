# **Boletim Diário do Pregão (BDI)**

A seção `filings_b3.daily_bulletin` lê os conjuntos de dados do **Boletim Diário do Pregão** da B3,
servidos a partir de `arquivos.b3.com.br/bdi`. Cada conjunto é uma tabela JSON paginada; um _reader_
transforma um pregão em um `pandas.DataFrame` tipado, validado por contrato e com proveniência.

O serviço é uma **API de POST**: a consulta inteira viaja no caminho da URL e o corpo é um objeto
JSON vazio (`{}`). Um `GET` na mesma URL devolve **405 Method Not Allowed** — com ou sem _cookies_
e cabeçalhos de navegador, então é o método, não bloqueio de robô. Os _readers_ desta seção já
fazem isso; quem chama não precisa saber.

Duas irregularidades do formato que os _readers_ absorvem:

- **Linhas mais largas que o cabeçalho.** A `DailyAverageStocks` declara 4 colunas e envia 5
  posições por linha, a quinta sempre nula, enquanto a `EconomicIndicators` bate exato. Como o
  payload é posicional, o excedente não tem nome: ele é descartado **apenas** quando está vazio.
  Um valor de verdade sem coluna correspondente faz o _reader_ falhar alto, porque descartá-lo em
  silêncio é exatamente como uma coluna da fonte deixa de chegar sem nada ficar vermelho.
- **Janela de disponibilidade.** A resposta declara um `limitDate` por tabela (`"D-21"` na
  `EconomicIndicators`, por exemplo): o serviço só devolve os últimos dias. Um pedido fora da
  janela não é erro de código.

> **Veja também:** [Visão geral da API](../index.md) · [Uso](../../usage.md) · [Exemplos](../../examples.md)

---

## Padrões implementados

- **[Posições em aberto de empréstimo de ativos](btb_lending_open_positions.md)** —
  `BdiBtbLendingOpenPositionsReader`: o retrato de fim de pregão do empréstimo de ativos (banco de
  títulos, "BTB"; tabela `BTBLendingOpenPosition`). Uma linha por instrumento ainda em aberto, com a
  quantidade emprestada, o preço médio de empréstimo e o saldo financeiro. **Contrato de coluna
  completa** (as 10 colunas da fonte, em ordem), verificado contra uma resposta ao vivo e o glossário
  oficial da B3.
- **[Resumo diário do mercado à vista de ações](stocks_summary.md)** — `BdiStocksSummaryReader`: o
  resumo por pregão do mercado à vista (tabela `DailyAverageStocks`). Uma linha por instrumento com a
  quantidade de negócios e o volume financeiro negociado do dia.

Cada padrão ganha a sua própria página, com **Descrição** e **Exemplos**. Ao migrar um novo dataset
BDI (#5–#42), acrescente uma página nesta pasta e registre-a no `nav:` do `mkdocs.yml` no mesmo
commit.

---

## Forma de um leitor

Todo _reader_ desta seção tem a mesma forma — construído sobre a base `_base_bdi_reader` (privada):

```python
Reader(date_ref: datetime.date, path_raw: pathlib.Path | None = None) -> Reader
Reader.read() -> pandas.DataFrame
```

| Parâmetro | Tipo | Significado |
|-----------|------|-------------|
| `date_ref` | `datetime.date` | Pregão a ler. **Obrigatório, sem padrão** — o endpoint do BDI é endereçado por data, então não existe um "mais recente". Precisa do dia útil anterior? Calcule-o e passe explicitamente. |
| `path_raw` | `pathlib.Path`, opcional | Diretório onde **manter** cada página JSON bruta baixada (a camada _bronze_ de um _datalake_). `None` (padrão) usa um diretório temporário removido ao final. |

`read()` retorna um `DataFrame` cujas colunas são as da própria fonte, em _UPPER_SNAKE_CASE_
(`TckrSymb` → `TCKR_SYMB`), tipadas explicitamente — nunca a inferência do pandas.

---

## Colunas de proveniência

Todo `DataFrame` devolvido carrega, **ao lado** das colunas de origem, seis colunas de
**proveniência**, para que a camada _bronze_ de um _datalake_ seja autodescritiva e rastreável:

| Coluna | Conteúdo |
|--------|----------|
| `url` | URL exata de onde o dado foi baixado. |
| `updated_at` | _Timestamp_ de coleta (quando esta leitura buscou o dado), **UTC, tz-aware**. |
| `source_key` | Identificador do dataset (do contrato) — distingue _readers_ que compartilham a mesma `url`. |
| `package_version` | Versão do pacote que produziu a linha (para re-ingestão após correção de bug). |
| `ingestion_run_id` | UUID gerado uma vez por `read()`, comum a todas as linhas daquela leitura. |
| `content_hash` | `sha256` dos bytes do artefato baixado — detecta se a fonte mudou desde a última coleta. |

A proveniência é anexada **depois** da validação de contrato — ela não faz parte do artefato de
origem, então não precisa satisfazer o contrato da fonte. `updated_at` permanece _tz-aware_: um
destino SQL que precise de _naive_ normaliza no carregamento do _warehouse_, nunca aqui.

---

## Artefato bruto — `path_raw`

- **`None` (padrão)** — cada página é baixada num diretório temporário, lida e **descartada** na
  saída. Nada persiste; a leitura devolve apenas o `DataFrame`.
- **Um caminho** — cada página JSON **bruta e intacta** é gravada ali e **mantida**, _antes_ de
  qualquer parsing. O diretório é criado junto com os pais.

Guardar o artefato bruto é o que torna a camada _bronze_ autoritativa: quando a B3 muda o contrato
dos dados e a transformação quebra, os **bytes exatos** que causaram a falha continuam reproduzíveis
em disco, em vez de perdidos num novo _download_ de uma fonte já alterada.

---

## Validação por contrato

Cada _reader_ declara um `FileContract` (privado, em `_internal/config/contracts/daily_bulletin/`)
que fixa as colunas obrigatórias. Uma fonte que viola o contrato levanta `ContractError` — uma
coluna obrigatória ausente falha de forma **barulhenta**, em vez de silenciosa. Colunas monetárias
são `decimal.Decimal` exato, nunca `float` binário.
