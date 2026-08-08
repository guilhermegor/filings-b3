# #180 — reader de instrumentos não lê o arquivo real da B3

Ledger da branch `fix/180-reader-instrumentos-nao-le-arquivo-real`.

## O defeito

`InstrumentsFileEqtyReader(date(2026, 7, 29)).read()` levantava
`ValueError: expected exactly one .xml member in download, found []`. Todos os 18 _readers_ da
família falhavam ponta a ponta, contra **qualquer** pregão.

Duas causas somadas em `_base_instruments_file_reader._locate_xml`:

1. O download é um `.zip` cujo único membro é **outro** `.zip`; `extract_all` desembrulha um
   nível só e devolvia o zip interno.
2. O zip interno traz **dois** XML BVBG.028.02 — um por _snapshot_ intradiário —, e o método
   exigia exatamente um.

Conferido em `IN260728`, `IN260729`, `IN260803`, `IN260807`: os quatro têm a mesma forma. Não é
_drift_; a reconciliação da família (#143, #148) sempre passou pelo `read_xml` sobre um XML já
extraído à mão, nunca pelo `read()`.

## Por que os testes não pegaram

O _fixture_ `tests/fixtures/instruments_IN_sample.zip` era um zip **plano** com **um** XML —
uma forma que a B3 nunca publica. 366 testes verdes sobre um arquivo que não existe.

## O que foi feito

- [x] `_locate_xml` desembrulha zips aninhados (com guarda contra ciclo) e escolhe o XML de
      maior `CreDtAndTm`; sem `CreDtAndTm` no cabeçalho, falha alto.
- [x] `_snapshot_stamp` lê o carimbo nos primeiros 4 KB — não parseia os ~660 MB do corpo.
- [x] _fixture_ reconstruído na forma **real**: zip-dentro-de-zip, _snapshot_ de 40 registros
      (00:20:11) + o definitivo de 50 (18:39:48), com o **mais recente escrito primeiro** no
      arquivo para que ordem de membro não passe por seleção de _snapshot_.
- [x] Testes: seleção do _snapshot_ tardio, arquivo sem XML, _snapshot_ sem `CreDtAndTm`.
      366 testes de unidade verdes.
- [x] Reconciliação ao vivo contra `IN260729` real:
      `InstrumentsFileOptnOnSpotAndFuturesReader` devolveu **8.293** linhas — exatamente a
      contagem do _snapshot_ de pós-fechamento (o de pré-abertura tem 8.289), provando a
      escolha certa sobre o arquivo de verdade.
- [x] `docs/api/search_trading_session/index.md` + `README.md` descrevem a forma real do arquivo.

## Aberto — vira issue própria

- **Guarda de contagem declarada.** O cabeçalho traz `TtlNbOfMsg` (183.174 no _snapshot_ de
  29/07), que é a B3 declarando quantos `<Instrm>` o arquivo contém — hoje ignorado. Um
  download truncado produz XML válido até onde chegou e passa em silêncio. Decisão do
  usuário: **fazer para a família toda**, e de forma **desacoplada do formato** — o `read_xml`
  recebe, opcionalmente, o *caminho* até a contagem declarada; quem sabe que ela se chama
  `TtlNbOfMsg` e onde mora é o _reader_ concreto, nunca o _seam_. É a próxima issue a atacar.
- **`BdiStocksSummaryReader` está quebrado** por outra causa: o endpoint
  `arquivos.b3.com.br/bdi/table/...` devolve **HTTP 405** a GET (confirmado fora da lib, com e
  sem cabeçalhos). Precisa de issue própria.
- **#159–#161 (ouro) seguem bloqueadas por _fixture_**: censo dos sub-blocos em `IN260729` e
  `IN260807`, nos dois _snapshots_ de cada, achou 17 blocos e **zero** `SpotGoldInf` /
  `FwdGoldInf` / `PureGoldInf`. Não é o pregão — a B3 não publica esses blocos nesses arquivos.
