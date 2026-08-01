# **Arquivo de instrumentos (BVBG.028.02) — Pesquisa por Pregão**

Leitura do **arquivo de instrumentos** do pregão (`IN{aammdd}.zip`), um XML ISO-20022
`InstrumentReport` (BVBG.028.02) que identifica todos os instrumentos registrados na B3 para a
sessão, publicado em `www.b3.com.br/pesquisapregao/download`.

> **Veja também:** [Visão geral da seção](index.md) para a forma do _reader_, proveniência e
> `path_raw` · [Uso](../../usage.md) para instalação e o conceito geral.

---

## Descrição

`InstrumentsFileReader` baixa o `IN{aammdd}.zip`, extrai o seu único membro XML, **achata** cada
registro de instrumento em uma linha e devolve um `DataFrame` tipado, validado por contrato e com
proveniência. O arquivo consolida **todos os mercados** — ações, futuros, opções, ouro, estratégias
e renda fixa — e cada tipo carrega os seus campos sob um bloco XML diferente (o _ticker_ de uma ação
vive em `EqtyInf`, o de um futuro em `FutrCtrctsInf`, e assim por diante); cada coluna resolve o
**primeiro** desses caminhos alternativos que existir no registro.

O layout de colunas vem do mapeamento autoritativo da B3 **`BVBG.028 para UP2DATA`**
(planilha `InstrumentsConsolidatedFile`, 52 campos) — a própria B3 achata o XML aninhado nele. O
contrato exige apenas as colunas presentes em **todo** instrumento (o bloco de identificação:
`RPT_DT`, `TCKR_SYMB`, `ASST`, `ASST_DESC`, `SGMT_NM`, `MKT_NM`,
`ISIN`); os muitos campos específicos de tipo fluem como colunas tipadas, nulas quando não se
aplicam ao instrumento da linha.

Colunas de data (`XPRTN_DT`, `TRADG_START_DT`, …) são `datetime.date`; colunas de
valor/quantidade (`CTRCT_MLTPLR`, `EXRC_PRIC`, `MKT_CPTLSTN`, …) são
`decimal.Decimal` exato. As demais preservam o texto exato da fonte.

### Pernas de estratégia

Uma estratégia (operação estruturada) tem **duas pernas**, cada uma com a sua direção e o seu ativo
objeto: `SD_TP_CD1`/`UNDRLYG_TCKR_SYMB1` e `SD_TP_CD2`/`UNDRLYG_TCKR_SYMB2`. No arquivo real, as
pernas **diferem** — tipicamente `BUYI` num vencimento e `SELL` noutro.

As duas colunas de ativo objeto são resolvidas por **_self-join_** dentro do próprio arquivo: no XML
a perna referencia o outro instrumento apenas por um identificador proprietário
(`200001037989`), enquanto o _ticker_ que o layout UP2DATA promete vive no **registro daquele outro
instrumento**. O _reader_ faz essa tradução, então a coluna entrega `DDIF38`, não o número. Uma
referência a um instrumento ausente do arquivo fica nula, nunca com o valor da perna anterior.

Só registros de estratégia preenchem estas quatro colunas; nos demais instrumentos elas são
legitimamente nulas.

---

## Exemplos

### Ler os instrumentos de um pregão

```python
from datetime import date
from filings_b3.search_trading_session import InstrumentsFileReader

df = InstrumentsFileReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "ASST", "MKT_NM", "ISIN"]].head())
```

`date_ref` é **obrigatório** — o endpoint é endereçado por data. Precisa do dia útil anterior?
Calcule-o e passe explicitamente.

### Filtrar por mercado

Uma única leitura traz todos os mercados; filtre pela coluna de classificação:

```python
futuros = df[df["MKT_NM"] == "FUTURE"]
print(futuros[["TCKR_SYMB", "XPRTN_DT", "CTRCT_MLTPLR"]].head())
```

### Manter o artefato bruto (camada _bronze_)

```python
from pathlib import Path

df = InstrumentsFileReader(
    date(2025, 1, 2), path_raw=Path("/data/bronze/b3")
).read()

print(df[["source_key", "content_hash", "updated_at"]].iloc[0])
```
