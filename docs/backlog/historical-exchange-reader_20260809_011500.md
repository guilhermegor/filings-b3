# #185 — reader do histórico de taxas de câmbio (Res. BCB 120)

Ledger da branch `feat/185-historical-exchange-reader`.

## A premissa da issue estava errada

A issue nomeava `EconomicIndicators` como a tabela da Resolução BCB 120. **Não é.** Essa é uma
tabela ampla: 441 linhas, **300 indicadores distintos**, cobrindo Moedas (149), Commodities (145),
Índices (124), Treasury, Inflação, Juros e Swap. Câmbio é uma fatia dela.

A tabela certa é **`HistoricalExchange`** — "Histórico de taxas de câmbio (Resolução BCB nº 120)",
classificação "Indicadores e informativos", `limitDate: PDC_ANO-5` (cinco anos completos + o ano
corrente, **não** D-21).

Descoberta ao seguir a regra de confirmar o documento de layout **antes** de escrever. Se eu
tivesse implementado direto sobre a premissa da issue, o reader estaria correto, consistente,
testado — e lendo a tabela errada.

## O índice autoritativo (achado aqui, registrado na #186)

`GET https://arquivos.b3.com.br/bdi/table/classifications` → as **69 tabelas** do BDI em 14
classificações. Três armadilhas medidas:

- A rota de **índice é GET**; a de **dados é POST**. Invertidas.
- `/table/all` existe mas devolve `{}`.
- Nome de tabela inexistente devolve **200 com tabela vazia**, nunca 404.

## Contrato — confirmado com o dono do repositório

**Glossário Dados Públicos — `EconomicIndicatorPriceFile`, 28/04/2023 (v2)**:
<https://www.b3.com.br/data/files/75/F3/42/23/A59C781064456178AC094EA8/EconomicIndicatorPriceFile%20_1_.pdf>

O irmão `Glossario_Indicadores_economicos.pdf` (30/11/2023) descreve a **outra** tabela
(`EconomicIndicators`) e só traz rótulos em português, sem códigos de campo — não serve aqui.

### Defeito 1 — nomes de campo trocados na API

| Glossário | API devolve | Valor | Coluna publicada |
|---|---|---|---|
| `Asst` | `TckrSymb` | `DOL` | **`ASST`** |
| `TckrSymb` | `Symb` | `RTDOLD2` | **`TCKR_SYMB`** |

Decisão do dono: seguir a **semântica do glossário**. Motivo — a regra do #165 (um campo, um nome
de coluna): a família de instrumentos já usa `TCKR_SYMB` para o ticker do **instrumento**, então
seguir a API faria a mesma coluna significar **ativo** aqui, e um `JOIN` entre as duas leituras
casaria `DOL` contra tickers de instrumento **sem erro nenhum**.

Implementado como `dict_field_renames` na base — opcional, vazio por padrão, aplicado aos nomes
PascalCase **antes** da conversão para `UPPER_SNAKE_CASE`. Renomear é passivo (quebra o rastro
mecânico coluna → payload), então a docstring exige justificativa contra o glossário.

### Defeito 2 — nomes de campo com espaço, achado só ao vivo

A API manda `"Symb "` e `"PricVal "` **com espaço no fim** — e só nesta tabela; `DailyAverageStocks`
e `EconomicIndicators` vêm limpas. De novo: **por tabela, não por formato**.

O sintoma é traiçoeiro: a coluna **imprime** como `PRIC_VAL`, mas só `df["PRIC_VAL "]` a alcança.
Na prática o `read()` estourou `ContractError: Required column missing: 'TCKR_SYMB'` — que foi o
controle negativo do conserto, observado de verdade antes dele existir.

Corrigido na base com `.strip()` no nome do campo, servindo todos os readers da seção.

## O que foi feito

- [x] `_base_bdi_reader`: `dict_field_renames` opcional + `.strip()` no nome do campo.
- [x] `contracts/daily_bulletin/historical_exchange.py` — `BDI_HISTORICAL_EXCHANGE`, citando o
      glossário e documentando a troca de nomes com a evidência medida.
- [x] `daily_bulletin/historical_exchange.py` — `BdiHistoricalExchangeReader`.
- [x] API pública (seção), agregadores de contratos, snapshot do _boundary gate_.
- [x] 5 testes de unidade, com _fixture_ copiado da resposta real **incluindo as duas
      irregularidades** (nomes trocados e com espaço). Um _fixture_ "arrumado" testaria uma fonte
      que a B3 não serve. Suíte: 391 verdes.
- [x] **Reconciliação ao vivo**: 2026-08-07 → 3 linhas, `ASST=DOL`, `TCKR_SYMB` ∈ {RTDOLD1,
      RTDOLD2, RTDOLCL}, `PRIC_VAL` `Decimal` exato, zero colunas nulas.
- [x] **Janela histórica provada**: leituras em 2022-03-15, 2024-06-10 e 2026-08-07, todas com
      dados. As escalas variam entre pregões (`5.16` vs `5.162`), preservadas exatamente — a
      prova prática de por que `PRIC_VAL` não pode ser `float`.
- [x] Página em `docs/api/daily_bulletin/` + `nav:` + índice da seção + `README.md`.

## Aberto

- **#186** ganhou o índice autoritativo, mas o cruzamento automático **não fecha**: o backlog é
  indexado por nomes `b3_*` da stpstone e a B3 por nomes próprios, então `DailyAverageStocks`
  aparece como "sem cobertura" mesmo já implementada. O escopo real é construir o mapa
  `tabela B3 → issue/reader` à mão uma vez. Comentado lá.
- Só `DOL` aparece nesta tabela nos pregões conferidos. Se a B3 publicar outras moedas, o reader
  já as traz — nada a mudar.
- #174, #136, #159–#161.
