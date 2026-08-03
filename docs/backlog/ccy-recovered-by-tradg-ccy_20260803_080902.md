# #147 — a moeda dos valores já é recuperável por `TRADG_CCY`

Branch: `fix/147-ccy-recovered-by-tradg-ccy`. Closes #147.

## Checklist

- [x] Medir se `@Ccy` diverge de `TradgCcy` em arquivos reais
- [x] Teste de regressão que trava a invariante (com *should-fail* nos dois sentidos)
- [x] Documentar a invariante na página do reader consolidado
- [ ] Sem `/release` ao mergear — nenhuma mudança de comportamento no artefato

## A premissa da issue não se sustenta

#147 pedia colunas `<COL>_CCY` para cinco colunas decimais do reader consolidado, partindo de que
a moeda estava sendo descartada. Duas coisas derrubam isso:

1. **O reader já mapeia `TRADG_CCY`** (`instruments_file.py:82`, `InstrmInf/*/TradgCcy`). A moeda
   nunca esteve perdida.
2. **`@Ccy` nunca diverge de `TradgCcy`.** Medido nos arquivos reais, varrendo o XML cru:

   | arquivo | registros | linhas com `@Ccy != TradgCcy` |
   |---|---|---|
   | `IN260729` | 183.164 | **0** |
   | `IN260731` | 188.492 | **0** |

   Total **371.656** registros, incluindo todos os casos em USD (`ExrcPric` USD 834+796,
   `Ppsn` USD 31+31). Cobre `ExrcPric`, `MktCptlstn`, `RghtsIssePric`, `LastPric`, `FrstPric`,
   `Ppsn`.

Além disso, **duas das cinco colunas pedidas nunca carregam `@Ccy`**: `CtrctMltplr` e `AsstQtnQty`
aparecem 8.939 e 8.986 vezes, **sempre sem o atributo** — são multiplicador e quantidade, não
dinheiro. Criar `CTRCT_MLTPLR_CCY` e `ASST_QTN_QTY_CCY` produziria colunas nulas para sempre.

Decisão do usuário: fechar sem adicionar colunas, deixando um **gate** no lugar da memória.

## O que entrou

Só um teste e um trecho de documentação. Zero mudança em `_DICT_PATHS`, zero coluna nova, zero
impacto no `check_contract_drift` (o conjunto de 52 colunas segue idêntico) — que era exatamente
a preocupação registrada na issue sobre mexer no contrato público.

`test_tradg_ccy_recovers_the_currency_of_every_monetary_value` afirma que nenhuma linha com
`EXRC_PRIC`/`MKT_CPTLSTN` preenchido fica sem `TRADG_CCY`. Exercitado nos dois sentidos: apontando
`TRADG_CCY` para uma tag inexistente o teste **falha**; restaurado, os 6 testes passam. Sem isso
seria só mais um teste verde que não examina nada.

## Ressalva de verificação

A reconciliação dos 371.656 registros foi feita **sobre o XML cru** (`iterparse` direto nos dois
`IN*.zip`), não através de uma execução completa do reader — o reader baixa da rede e a fixture de
50 registros não contém linhas com esses decimais preenchidos. O XML cru é a mesma fonte de onde os
caminhos do reader leem, então a invariante medida é a que importa; mas o número **não** vem de uma
execução ponta-a-ponta.

## Aberto

- Os readers **por sub-bloco** seguem com as colunas `<COL>_CCY` (projetam o atributo direto). As
  duas visões são consistentes; o consolidado só não duplica. Nada a fazer.
- Se um pregão futuro trouxer `@Ccy` divergente de `TradgCcy`, o teste falha — e aí a decisão de
  #147 deve ser reaberta com o dado novo em mãos.
