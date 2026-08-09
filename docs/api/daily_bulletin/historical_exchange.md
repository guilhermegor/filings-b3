# **Histórico de taxas de câmbio (Resolução BCB nº 120) — BDI**

Leitura das **taxas de câmbio oficiais determinadas pelo Banco Central** (tabela
`HistoricalExchange` da B3), publicadas no Boletim Diário do Pregão sob a Resolução BCB nº 120.
São as taxas que a própria B3 usa para precificar contratos futuros e de opções referenciados em
moeda.

> **Veja também:** [Visão geral da seção BDI](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Uso](../../usage.md) para instalação e o conceito geral.

---

## Descrição

`BdiHistoricalExchangeReader` baixa a tabela do pregão, valida o **contrato** de colunas, aplica os
**tipos declarados** — nunca a inferência do pandas — e devolve um `DataFrame` com uma linha por
instrumento financeiro da sessão.

Diferente dos demais _datasets_ da seção, este é **histórico**: o serviço declara
`limitDate: PDC_ANO-5`, ou seja, os **últimos cinco anos completos mais o ano corrente**. Dá para
caminhar anos para trás um pregão por vez, em vez de ficar preso a uma janela recente.

| Coluna | Tipo | Observação |
|--------|------|-----------|
| `RPT_DT` | `date` | Pregão a que a taxa se refere. |
| `ASST` | `str` | Mercadoria/ativo associado (`DOL`, `BGI`, `OZ1`, …). |
| `TCKR_SYMB` | `str` | Instrumento financeiro (`RTDOLD1`, `RTDOLD2`, `RTDOLCL`, …). |
| `ECNC_IND_DESC` | `str` | Descrição do indicador econômico. |
| `PRIC_VAL` | `Decimal` | Valor da taxa, exato, na escala publicada pela fonte. |

### ⚠️ Os nomes de campo da API estão trocados — o _reader_ desfaz

Medido em resposta real: a API publica o **ativo** sob o campo `TckrSymb` e o **instrumento** sob
`Symb` — o inverso do glossário oficial (`EconomicIndicatorPriceFile`, 28/04/2023).

| Glossário | API devolve | Valor | Coluna publicada |
|---|---|---|---|
| `Asst` | `TckrSymb` | `DOL` | **`ASST`** |
| `TckrSymb` | `Symb` | `RTDOLD2` | **`TCKR_SYMB`** |

O _reader_ restaura a semântica do glossário. Seguir o nome da API faria `TCKR_SYMB` significar
**ativo** aqui, enquanto significa **instrumento** em todos os _readers_ de
`search_trading_session` — e um `JOIN` entre as duas leituras casaria `DOL` contra _tickers_ de
instrumento **sem erro nenhum**, apenas devolvendo nada.

---

## Exemplos

### Ler as taxas de um pregão

```python
from datetime import date
from filings_b3.daily_bulletin import BdiHistoricalExchangeReader

df = BdiHistoricalExchangeReader(date(2026, 8, 7)).read()
print(df[["RPT_DT", "ASST", "TCKR_SYMB", "PRIC_VAL"]])
```

```text
      RPT_DT ASST TCKR_SYMB PRIC_VAL
  2026-08-07  DOL   RTDOLD2   5.0819
  2026-08-07  DOL   RTDOLD1   5.0808
  2026-08-07  DOL   RTDOLCL   5.0832
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data, então não existe um padrão "mais
recente".

### Montar uma série histórica

A janela de cinco anos é o que distingue este _dataset_; basta iterar os pregões desejados:

```python
from datetime import date, timedelta

import pandas as pd

from filings_b3.daily_bulletin import BdiHistoricalExchangeReader

date_start, date_end = date(2026, 8, 3), date(2026, 8, 7)
list_frames = []
date_cursor = date_start
while date_cursor <= date_end:
    df_day = BdiHistoricalExchangeReader(date_cursor).read()
    if not df_day.empty:
        list_frames.append(df_day)
    date_cursor += timedelta(days=1)

df_serie = pd.concat(list_frames, ignore_index=True)
df_ptax = df_serie[df_serie["TCKR_SYMB"] == "RTDOLD1"]
```

Um dia sem pregão devolve um _frame_ vazio — o `if` acima é o que evita concatená-lo.

### A escala da taxa é preservada exatamente

`PRIC_VAL` é um `Decimal` na escala que a B3 publicou, e ela **varia entre pregões** para o mesmo
instrumento:

```python
# medido ao vivo em RTDOLD1: 5.16 em 2022-03-15, 5.3516 em 2024-06-10
assert str(df["PRIC_VAL"].iloc[0]) == "5.0819"  # escala preservada, sem arredondar
```

Um `float64` não representa nenhum desses valores exatamente, e o erro entra em todo contrato
precificado a partir da taxa.

### Manter o artefato bruto (camada _bronze_)

```python
from datetime import date
from pathlib import Path

from filings_b3.daily_bulletin import BdiHistoricalExchangeReader

df = BdiHistoricalExchangeReader(
    date(2026, 8, 7), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```
