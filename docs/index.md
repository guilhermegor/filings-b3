# **Filings B3**

<img src="assets/b3-logo.png" alt="Filings B3" class="hero-logo">

Biblioteca Python simples e eficiente para acessar os conjuntos de dados públicos da B3 (a bolsa
brasileira). Cada _reader_ transforma um pregão em um `pandas.DataFrame` tipado, validado por
contrato e com proveniência — valores monetários como `Decimal` exato, nunca um `float` com perda.

---

## Conteúdo

| Seção | Descrição |
|-------|-----------|
| [Uso](usage.md) | Instalação, importação e as garantias de cada _reader_ |
| [Exemplos](examples.md) | Receitas prontas, orientadas a tarefas |
| [Referência da API](api/index.md) | Cada _reader_ e símbolo público |

---

## Início rápido

```bash
pip install filings-b3
```

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
```

---

Parte da família `filings-*`. Gerado a partir do template **lib-minimal** via
[BlueprintX](https://github.com/guilhermegor/BlueprintX).
