# **Referência da API**

A interface pública, agrupada pela própria divisão de alto nível do código.

> **Veja também:** [Uso](../usage.md)

## Páginas

| Grupo | Conteúdo |
|-------|----------|
| [Referência](reference.md) | A superfície pública disponível desde o primeiro dia |

## Fazendo esta seção crescer

Isto é um **diretório, não uma página única**, de propósito. Uma referência de API cresce a cada
unidade publicada, então um único `api.md` vira a maior página do repositório; dividi-la depois é
trivial, mas **apodrece todos os links profundos publicados** — e permanentemente, uma vez que a
documentação versionada esteja no ar, porque `/<version>/api/#anchor` existe para sempre. O prêmio
por começar como diretório é um arquivo extra e um nível de navegação, pago uma única vez.

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
