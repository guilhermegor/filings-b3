# Ledger — readers dos sub-blocos #150–#158 (arquivo de instrumentos)

Branch: `feat/150-158-instruments-sub-block-readers`
Issues: #150 #151 #152 #153 #154 #155 #156 #157 #158
Iniciado: 2026-08-02

## Fonte de contrato confirmada com o usuário (regra bloqueante)

O usuário confirmou, **antes** de qualquer arquivo ser escrito, a opção "catálogo PDF como
autoridade", e forneceu o _hub_ onde coleciona os PDFs de contrato:

<https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/boletim-diario/dados-publicos-de-produtos-listados-e-de-balcao/>

| Documento | Papel |
|---|---|
| **Catálogo de Mensagens — Cadastro de Instrumento v2.6** (101 pp, 24/10/2017) | autoridade em **estrutura e cardinalidade** (âncoras `4.5`–`4.20`) |
| Aba `BVBG.028 - Taxonomia` do `BVBG.028 para UP2DATA.xlsx` | lista de campos vigente |
| `IN260729.zip` real (183.164 registros) | árbitro de **presença** |
| Glossário `InstrumentsConsolidatedFile 2024` | as 52 colunas do _reader_ consolidado |

⚠️ O _host_ `bvmfnet.com.br` do catálogo está **morto**; usar a URL `b3.com.br/data/files/`.
Ambas as URLs vivas estão registradas em `_internal/config/contracts/CLAUDE.md`.

## O que o catálogo mudou em relação à planilha

- **Confirmou** a correção de #149: `SdTpCd` e `UndrlygInstrmId` são **irmãos** de `LegId`
  (`4.8.17.1`–`4.8.17.3`). O aviso "reabrir se o PDF discordar" está **encerrado** — o PDF concorda.
- **Está defasado** em `NtlBdInf`: declara 9 campos, o arquivo real traz 12. Os 4 extras são
  mapeados mas **não exigidos** (nenhum documento vigente declara a cardinalidade deles).
- **Trunca _tags_ longos** nas colunas do PDF: `DerivOptnExrcInstrmId` → `DerivOptnExrcInst`,
  `IntrstRateCrrctnTmBase` → `IntrstRateCrrctnT`. A cardinalidade declarada continua valendo.

Regra derivada, agora em `contracts/CLAUDE.md`: **o documento vence na forma, o artefato vence na
presença.**

## Feito

- [x] 9 contratos em `_internal/config/contracts/search_trading_session/`
- [x] 9 _readers_ em `search_trading_session/`, sobre `_base_instruments_file_reader`
- [x] Agregadores: `contracts/search_trading_session/__init__.py`, `contracts/__init__.py`,
      `search_trading_session/__init__.py` (+ _docstring_ da seção: 9 → 18 _readers_)
- [x] `_SECTION_SURFACE` do _boundary gate_ atualizado (o gate pegou a mudança de superfície)
- [x] Testes: os 9 acrescentados à tupla parametrizada; 2 testes novos (pernas de estratégia
      por perna; companheiras de moeda). `test_every_mapped_column_is_explicitly_typed` e
      `test_contract_required_columns_are_all_mapped` passaram a considerar `dict_joins`.
- [x] **350 testes passando**
- [x] 9 páginas em `docs/api/search_trading_session/` + `nav:` do `mkdocs.yml` + `index.md` da
      seção + `README.md`
- [x] Reconciliação ao vivo contra `IN260729.zip` — ver abaixo

### Decisão do usuário durante a implementação

`StrtgyInf` publica o subjacente de cada perna **duas vezes**: o id bruto
(`UNDRLYG_INSTRM_ID{n}`) **e** o _ticker_ resolvido por auto-junção (`UNDRLYG_TCKR_SYMB{n}`),
espelhando o _reader_ consolidado coluna a coluna. Escolhido pelo usuário sobre a alternativa
"só o id bruto".

## Reconciliação ao vivo — `IN260729.zip`

Um processo por _reader_ (o `read_xml` carrega a árvore inteira, ~4 GB residentes por passada;
nove numa só interpretação somariam o pico). Contagens conferidas contra um censo `iterparse`
independente.

| Reader | Bloco | Linhas | Colunas | Colunas 100% nulas | Veredito |
|---|---|---:|---:|---|---|
| `InstrumentsFileFutrCtrctsReader` | `FutrCtrctsInf` | 650/650 | 44 | `PURE_GOLD_WGHT` | OK — `[0..1]`, sem ouro no pregão |
| `InstrumentsFileDrvsOptnExrcReader` | `DrvsOptnExrcInf` | 8.289/8.289 | 27 | — | OK |
| `InstrumentsFileStrtgyReader` | `StrtgyInf` | 1.065/1.065 | 43 | — | OK — as 2 pernas e as 2 junções resolveram |
| `InstrumentsFileNtlBdReader` | `NtlBdInf` | 373/373 | 27 | — | OK |
| `InstrumentsFileIntlBdReader` | `IntlBdInf` | 374/374 | 23 | — | OK |
| `InstrumentsFileFxdIncmNonTrdblReader` | `FxdIncmNonTrdblInf` | 144/144 | 62 | `EARLY_RED_DT`, `PERPTL_DBNR_INITL_PMT`, `PMT_PRDCTY_TP`, `SPCFCTN_NM`, `TRGT_INSTRM_ID{,_TP,_MKT_IDR_CD}` | OK — os 7 são `[0..1]` ou pendem do contêiner `[0..*]` `TrgtInstrmId` |
| `InstrumentsFileOtcReader` | `OTCInf` | 6/6 | 16 | — | OK |
| `InstrumentsFileCshReader` | `CshInf` | 3/3 | 17 | `ISIN` | OK — `[0..1]`, disponível não precisa ter |
| `InstrumentsFileFicReader` | `FICInf` | 2/2 | 16 | — | OK |

**9/9 exatos, `failures=0`.** Em todas as passadas: contagem batendo com o censo independente e
**nenhuma coluna exigida pelo contrato veio nula**. Cada coluna 100% nula tem veredito escrito
acima — todas previstas pela cardinalidade do catálogo antes da execução, nenhuma surpresa.

## Aberto / follow-ups

- [ ] Commit + PR (`Closes #150`…`#158`) + `/release` no merge
- [ ] **#165 (novo, aberto nesta sessão)** — auditoria dos 8 _readers_ **já publicados** contra o
      catálogo encontrou um campo com **dois nomes**: `UndrlygInstrmId/OthrId/Tp/Prtry` é `TP` em
      `InstrumentsFileFxdIncmReader` e `UNDRLYG_INSTRM_ID_TP` nos outros quatro. Defeito irmão:
      `TP` em `InstrumentsFileExrcEqtsReader`. **BREAKING**, fica para o seu próprio PR. O teste
      de colisão (um caminho → um nome) entra junto com a correção, por isso **não** foi
      adicionado aqui: falharia neste branch.
- [ ] #147 — o _reader_ consolidado ainda descarta o atributo `Ccy`
- [ ] #159–#161 (ouro) — 0 registros em `IN260729`, precisam de uma sessão com ouro registrado
- [ ] #136 — bot-merge suprime branch-delete / issue-close / docs-deploy
- [ ] `read_xml` ainda parseia a árvore inteira (~4 GB) — herdado de #143
