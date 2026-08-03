# #147 — a moeda dos valores monetários vira coluna própria

Branch: `fix/147-ccy-recovered-by-tradg-ccy` (o nome ficou da primeira abordagem, que foi
**revertida** — ver abaixo). Closes #147.

## Checklist

- [x] Varrer **todos** os atributos descartados, não só `@Ccy`
- [x] `EXRC_PRIC_CCY` e `MKT_CPTLSTN_CCY` no reader consolidado
- [x] Oráculo de deriva passa a excluir colunas derivadas de atributo (por forma do caminho)
- [x] Testes: presença pareada + forma ISO-4217 + regra do oráculo — *should-fail* nos dois
- [x] Auditar os 18 readers já entregues à procura da mesma lacuna
- [x] Regra permanente em `_internal/config/contracts/CLAUDE.md` + lição no store BlueprintX
- [x] Docs da página do reader consolidado
- [ ] `/release` ao mergear (é `fix:` → PATCH; agora **muda o artefato**: 2 colunas novas)

## A reversão, e por que ela importa

Este branch começou fechando #147 **sem** adicionar as colunas, com o argumento de que `TRADG_CCY`
já recuperava a moeda — sustentado por uma reconciliação de **371.656 registros** com **zero**
divergências entre `@Ccy` e `TradgCcy`.

**O argumento estava errado, e a medição é que enganou.** Ela varria uma **lista de tags escolhida
a mão**, que justamente **excluía** as tags onde a invariante falha. Enumerando todos os atributos
do arquivo, o mesmo `IN260729` tem **1.074 valores com `@Ccy` em registros que não têm `TradgCcy`
nenhum**:

| tag | linhas | `@Ccy` | `TradgCcy` |
|---|---|---|---|
| `IssePric` | 374 | **USD 314, EUR 53, MXN 5, XXX 2** | `None` |
| `MtrtyVal` | 373 | BRL | `None` |
| `BaseDtPric` | 327 | BRL | `None` |

Nesses casos a moeda **só** existe no atributo. Lição registrada: *uma correlação medida sobre um
conjunto que você escolheu é evidência sobre a sua escolha, não sobre o dado.* As tags que a gente
esquece de listar são exatamente as que se comportam diferente — é por isso que a gente esqueceu.

## O que entrou

Duas colunas no reader consolidado, cada uma colada ao seu valor:

| valor | moeda | linhas preenchidas (`IN260729`) |
|---|---|---|
| `EXRC_PRIC` | **`EXRC_PRIC_CCY`** | 142.164 (BRL 141.330 · USD 834) |
| `MKT_CPTLSTN` | **`MKT_CPTLSTN_CCY`** | 14.623 (BRL) |

Zero órfãos nos dois sentidos: nenhum valor sem moeda, nenhuma moeda sem valor. O reader passa de
52 para **54** colunas.

`CTRCT_MLTPLR` e `ASST_QTN_QTY` seguem sem companheira: 8.939 e 8.986 ocorrências, **todas** sem
`@Ccy` — são multiplicador e quantidade, não dinheiro.

## O oráculo de deriva

`mapped_columns()` passa a **excluir** colunas derivadas de atributo, e a exclusão é derivada da
**forma do caminho** (`"/@" in path`), não de uma lista de nomes — então a próxima coluna de
atributo é tratada sozinha, sem editar a função.

Motivo: o layout UP2DATA enumera **campos** achatados e não tem como declarar um atributo XML.
Contá-las reportaria deriva no instante em que o reader passa a ler **mais** da fonte do que o
layout achatado consegue expressar — o oráculo puniria a leitura mais completa. O conjunto
comparado segue sendo **52**, idêntico ao de antes.

## Auditoria das entregas passadas (o pedido explícito do usuário)

Varredura dos 18 readers contra o arquivo real, nos dois pregões (`IN260729` e `IN260731`),
comparando "folhas mapeadas como valor" × "duplas (folha, atributo) mapeadas":

- **17 readers por sub-bloco: limpos.** Já traziam todos os atributos (`ADRInf` 1, `EqtyInf` 4,
  `FxdIncmNonTrdblInf` 3, `NtlBdInf` 2, `IntlBdInf` 1, `OptnOnEqtsInf` 1,
  `OptnOnSpotAndFutrsInf` 1).
- **1 com lacuna: o consolidado** — `ExrcPric/@Ccy` (142.164) e `MktCptlstn/@Ccy` (14.623).
  Corrigido aqui.
- **Fora da família de instrumentos não há readers XML.** `grep -rl read_xml src/` retorna só o
  seam e a família de instrumentos; `daily_bulletin` lê CSV/JSON, onde atributo não existe.

**Nenhuma issue nova foi necessária** — a única lacuna era esta, e ela está fechada neste PR.

## O modo de falha que os testes cobrem

O quase-acerto perigoso é o caminho do atributo cair no **texto** do elemento: a coluna enche com
`27.35` em vez de `BRL` e **continua parecendo preenchida**. Por isso um dos testes afirma a
**forma** do valor (ISO-4217, 3 letras), não só não-nulo. Exercitado: trocando o caminho para o
texto, o teste falha; restaurado, passa.

## Aberto

- Nada pendente nesta família. Se um pregão futuro trouxer um valor monetário novo no consolidado,
  a regra do `contracts/CLAUDE.md` manda mapear o atributo junto.
