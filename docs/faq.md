# **Perguntas frequentes (FAQ)**

Respostas às dúvidas comuns sobre usar e desenvolver esta biblioteca. Adicione entradas
específicas do projeto conforme surgirem nas _issues_.

> **Veja também:** [Uso](usage.md) · [Exemplos](examples.md) · [Contribuindo](contributing.md).

---

## Como instalo?

```bash
pip install filings-b3
```

## Como adiciono ou atualizo uma dependência?

Use o Poetry para que o _lock file_ continue sendo a fonte de verdade:

```bash
poetry add <package>               # dependência de runtime
poetry add --group dev <package>   # ferramenta só de desenvolvimento
```

Todo pacote que o código importa deve ser uma dependência **direta** — nunca dependa dele chegar
transitivamente por meio de outro pacote.

## Quais versões do Python são suportadas?

Veja a restrição `python = "..."` no `pyproject.toml`; a CI roda a matriz de testes contra cada
uma.

## Como a versão é determinada?

A versão é a **tag do git** (via poetry-dynamic-versioning); o `pyproject.toml` guarda um
_placeholder_ `0.0.0`. Faça um release pelo workflow de release — veja
[Contribuindo](contributing.md).
