# #149 — colunas de pernas de estratégia sempre nulas

Branch: `fix/149-strategy-leg-columns`. Closes #149. Desbloqueia #152 (`StrtgyInf`).

## Checklist

- [x] `xml_reader`: segmento indexado `Tag[n]` (n-ésima repetição de um irmão, 1-based)
- [x] `xml_reader`: `dict_joins` — _self-join_ dentro do documento
- [x] `instruments_file`: caminhos corrigidos + as duas colunas de ativo objeto via _join_
- [x] `check_contract_drift.mapped_columns()` passa a contar as colunas de _join_
- [x] Testes de unidade (3 novos no _seam_ + 1 de regressão no consolidado)
- [x] Reconciliação ao vivo contra o `IN260729.zip` real
- [x] Docs da página do _reader_ consolidado
- [ ] `/release` ao mergear (é `fix:` → PATCH)

## O defeito

Quatro colunas — `SD_TP_CD1`, `SD_TP_CD2`, `UNDRLYG_TCKR_SYMB1`, `UNDRLYG_TCKR_SYMB2` — vinham
**nulas em 100%** dos 1.065 registros de estratégia, em todas as versões publicadas até a 0.1.5.

Causa: os caminhos tratavam `SdTpCd`/`UndrlygInstrmId` como **filhos** de `LegId`. No arquivo real
`LegId` é uma **folha** (o número da perna) e os campos são **irmãos** dele, dentro de
`StrtgyLegList`. O caminho nunca resolvia.

Segundo defeito, encoberto pelo primeiro: pernas 1 e 2 apontavam para o **mesmo** caminho, então
mesmo corrigido o `_resolve_text` (primeiro acerto vence) daria à perna 2 a cópia da perna 1.

## ⚠️ A planilha publicada pela B3 está ERRADA aqui

Este é o ponto que mais importa para o próximo _reader_. A aba `InstrumentsConsolidatedFile`
declara, nas colunas 31–34:

```
<InstrmInf> - <StrtgyInf> - <StrtgyLegList> - <LegId> - <SdTpCd>
```

— exatamente o caminho que não resolve. O _reader_ **copiou a planilha fielmente**; não foi erro de
transcrição. A mesma planilha dá às pernas 1 e 2 caminhos **idênticos**, distinguindo-as apenas na
prosa da coluna `Observações` ("direção da perna 1" / "da perna 2").

**Ressalva de fonte:** a correção usa o **arquivo real** como autoridade contra a planilha. O
**catálogo BVBG.028 em PDF (v2.6)**, que o projeto também registra como fonte autoritativa, **não
foi consultado** — não tenho o link e o usuário pediu para seguir. Se o PDF descrever a estrutura
real (irmãos), ele confirma esta correção; se descrever a da planilha, vale reabrir. A estrutura em
si é inequívoca nos 1.065 registros.

## O que foi ao seam (genérico, não específico da B3)

- **`Tag[n]`** — n-ésima repetição de um irmão, 1-based (convenção XPath). XML regulatório repete o
  container em vez de numerá-lo (pernas de estratégia, cupons de um título), então sem isto um
  bloco repetido é inalcançável além da primeira ocorrência.
- **`dict_joins`** — `coluna -> (fk no registro, pk em qualquer registro, valor a trazer)`. Um
  registro que referencia outro carrega só um id opaco, enquanto o valor útil vive no registro
  referenciado. A tabela de _lookup_ é montada a partir de **todos** os registros, inclusive os que
  o `str_row_filter` descarta — então uma leitura por tipo ainda resolve referências para tipos que
  ela exclui. O _join_ acontece **antes** da validação de contrato e da tipagem.

## Por que _self-join_ e não o id cru

Decisão do usuário. O nome da coluna (`UNDRLYG_TCKR_SYMB`) e o layout da B3 prometem um **ticker**;
o XML só tem o id proprietário (`200001037989`). A planilha inclusive anota que "UP2DATA envia o
nome do ativo-objeto da perna, ao invés do código do instrumento".

Renomear para `UNDRLYG_INSTRM_ID` seria mais simples, mas essas colunas são **fixadas pelo oráculo
de deriva** contra o layout da B3 — renomear seria reportado como deriva. E os ids **resolvem**:
**378 de 378** ids distintos de perna aparecem como o `FinInstrmId/OthrId/Id` de algum registro do
mesmo arquivo.

Custo: o `mapped_columns()` do oráculo passou a somar `_DICT_PATHS | _DICT_JOINS`, senão as duas
colunas de _join_ seriam reportadas como deriva contra um layout que as declara.

## Validação ao vivo (`IN260729.zip`, 183.164 registros)

| | antes | depois |
|---|---|---|
| `SD_TP_CD1` preenchido | 0 | **1.065** |
| `SD_TP_CD2` preenchido | 0 | **1.012** |
| `UNDRLYG_TCKR_SYMB1` preenchido | 0 | **1.065** |
| `UNDRLYG_TCKR_SYMB2` preenchido | 0 | **1.012** |

- **1.012** registros com 2 pernas, **53** com 1 perna — bate com o censo independente.
- **Zero** registros com as duas pernas idênticas (seria o defeito de colapso). Dois registros têm o
  mesmo **lado** nas duas pernas (`WDDQ26Q26`: BUYI `DDIQ26` + BUYI `WDOQ26`) mas ativos objeto
  **diferentes** — _spread_ legítimo, não colapso.
- Registros de 1 perna têm a perna 2 **nula**, sem resíduo da perna 1.
- **Zero** ativos objeto ainda como id numérico cru — todos viraram _ticker_ (`DI1F35`, `DI1F30`).
- Total de colunas segue **52**, agora 50 por caminho + 2 por _join_.

Suíte completa: **297 passed**. `ruff`, `mypy src` limpos.

## Aberto

- #147 (moeda do _reader_ consolidado) segue aberto — não tocado aqui.
- #152 (`StrtgyInf` por tipo) fica desbloqueado: pode usar `Tag[n]` e `dict_joins`.
- Vale avaliar se a reconciliação ao vivo deve passar a **falhar** (não só imprimir) em coluna
  inteiramente nula não justificada — foi como este defeito apareceu, por acaso.
