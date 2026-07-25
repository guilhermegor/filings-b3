# **Posições em aberto de empréstimo de ativos — BDI**

Leitura do retrato de fim de pregão do **empréstimo de ativos** (banco de títulos, "BTB"; tabela
`BTBLendingOpenPosition` da B3), publicado no Boletim Diário do Pregão.

> **Veja também:** [Visão geral da seção BDI](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Uso](../../usage.md) para instalação e o conceito geral.

---

## Descrição

`BdiBtbLendingOpenPositionsReader` baixa a tabela paginada do pregão, valida o **contrato** de
colunas, aplica os **tipos declarados** — nunca a inferência do pandas — e devolve um `DataFrame`
com uma linha por instrumento ainda em aberto: a quantidade emprestada, o preço médio de empréstimo
e o saldo financeiro da posição.

É um **contrato de coluna completa**: as 10 colunas da fonte são fixadas em ordem
(`bool_full_column=True`), então tanto uma coluna **ausente** quanto uma coluna **acrescentada** pela
B3 viram `ContractError` (deriva de contrato), em vez de passar despercebidas. Os nomes foram
confirmados contra uma resposta **ao vivo** e o glossário oficial _Posição em Aberto_ (v1,
05/09/2023) — não copiados do `stpstone`, que havia perdido as duas colunas de data à esquerda.

| Coluna | Tipo | Observação |
|--------|------|-----------|
| `RPT_DT` | `date` | Data do relatório (oculta na UI da B3, mas enviada no _payload_). |
| `DT_REF` | `date` | Data do pregão de referência. |
| `TCKR_SYMB` | `str` | _Ticker_ do instrumento. |
| `ISIN` | `str` | Código ISIN. |
| `COMPANY` | `str` | Nome da empresa/emissor. |
| `TYPE` | `str` | Tipo do papel. |
| `MARKET` | `str` | Mercado. |
| `STOCK_BALANCE` | `Int64` | Quantidade de ações em aberto (emprestada). |
| `AVG_PRIC` | `Decimal` | Preço médio de empréstimo, exato. |
| `BALANCE` | `Decimal` | Saldo financeiro da posição, exato (BRL). |

---

## Exemplos

### Ler um pregão

```python
from datetime import date
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "ISIN", "STOCK_BALANCE", "BALANCE"]].head())
```

`date_ref` é **obrigatório** — o endpoint do BDI é endereçado por data, então não existe um padrão
"mais recente". Precisa do dia útil anterior? Calcule-o e passe explicitamente.

### Maiores posições por saldo financeiro

`BALANCE` é um `Decimal` exato (em BRL) — seguro para ordenar e somar sem perda de _float_:

```python
top = df.sort_values("BALANCE", ascending=False).head(10)
print(top[["TCKR_SYMB", "ISIN", "STOCK_BALANCE", "BALANCE"]])
```

### Somar sem perda de _float_

```python
from decimal import Decimal

total = sum(df["BALANCE"])
assert isinstance(total, Decimal)  # nunca um float64 com perda
print(f"Saldo total das posições em aberto: R$ {total}")
```

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = BdiBtbLendingOpenPositionsReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()

# A proveniência viaja junto com os dados — nenhum repositório de metadados separado é necessário.
print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```
