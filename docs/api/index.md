# **Referência da API**

A interface pública, agrupada pelas **macro-seções** do próprio código — cada seção é uma pasta com
uma visão geral (`index.md`) e **uma página por _reader_** (`Descrição` + `Exemplos`).

> **Veja também:** [Uso](../usage.md) · [Exemplos](../examples.md)

## Macro-seções

| Seção | Import público | Estado |
|-------|----------------|--------|
| [Boletim Diário do Pregão (BDI)](daily_bulletin/index.md) | `filings_b3.daily_bulletin` | **2 _readers_** |
| [Pesquisa por Pregão](search_trading_session/index.md) | `filings_b3.search_trading_session` | **1 _reader_** |
| Plataformas (PUMA) | `filings_b3.platforms` | _planejada_ |
| Índices | `filings_b3.indexes` | _planejada_ |
| Dados de mercado | `filings_b3.market_data` | _planejada_ |
| _Clearing_ (garantias) | `filings_b3.clearing` | _planejada_ |

Cada _reader_ é importável **apenas pela sua seção** — `from filings_b3.daily_bulletin import …`.
A raiz `filings_b3` exporta só `__version__`; o subpacote `_internal` é privado.

!!! warning "Mudança na 0.2.0"
    Até a 0.1.x cada _reader_ era **também** reexportado de forma plana na raiz. Isso foi removido:
    com seis macro-seções e ~105 datasets previstos, a raiz viraria uma lista de mais de cem nomes,
    exatamente o que a organização por seção existe para evitar.

## Fazendo esta seção crescer

Isto é um **diretório, não uma página única**, de propósito. Uma referência de API cresce a cada
unidade publicada, então um único `api.md` vira a maior página do repositório; dividi-la depois é
trivial, mas **apodrece todos os links profundos publicados** — e permanentemente, uma vez que a
documentação versionada esteja no ar, porque `/<version>/api/#anchor` existe para sempre. O prêmio
por começar como diretório é um arquivo extra e um nível de navegação, pago uma única vez.

A convenção concreta desta seção: **uma pasta por macro-seção** (`daily_bulletin/`, …), com um
`index.md` de visão geral (o catálogo de _readers_ + a prosa compartilhada) e **uma página por
_reader_** (`Descrição` + `Exemplos`). Uma seção só nasce no disco com o seu primeiro _reader_.

Ao adicionar páginas:

- **Agrupe pela própria divisão de alto nível do código-base — nunca invente uma taxonomia
  paralela** (por exemplo, uma página por módulo público, espelhando a própria divisão do pacote).
  Quem conhece o pacote consegue adivinhar a URL, e a documentação não pode divergir de uma
  estrutura que ela espelha.
- **A profundidade acompanha a quantidade, não o gosto.** O eixo real escolhe as seções; só o
  volume decide se uma seção precisa de um segundo nível.
- A prosa compartilhada por um grupo mora uma única vez na página daquele grupo, não repetida por
  item.
- **Registre toda nova página no `nav:` do `mkdocs.yml` no mesmo commit.** O MkDocs constrói uma
  página não registrada mesmo assim — ela apenas some da navegação, que é como uma página some
  silenciosamente (e é o que o gate `check_docs_sections.py` existe para pegar).
