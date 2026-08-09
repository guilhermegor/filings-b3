# #183 — endpoint do BDI exige POST

Ledger da branch `fix/183-bdi-endpoint-exige-post`.

## O defeito

`BdiStocksSummaryReader(date(2026, 7, 29)).read()` esgotava as tentativas do _retry_ e morria com
`HTTP Error 405: Method Not Allowed`. Os **dois** _readers_ da seção não baixavam nada.

## Causa

O serviço é uma **API de POST**: a consulta viaja inteira no caminho da URL e o corpo é um objeto
JSON vazio. O `_internal/utils/http_downloader` só fazia `GET`.

O usuário trouxe a chamada que o próprio site faz. Reduzi ao mínimo e confirmei fora da
biblioteca — **sem _cookie_ algum**, sem `user-agent` de navegador, sem `origin`:

```bash
curl -X POST -H 'content-type: application/json' --data-raw '{}' \
  'https://arquivos.b3.com.br/bdi/table/EconomicIndicators/2026-08-07/2026-08-07/1/100'   # 200
curl -X POST -H 'content-type: application/json' --data-raw '{}' \
  'https://arquivos.b3.com.br/bdi/table/DailyAverageStocks/2026-07-29/2026-07-29/1/100'   # 200
```

Ou seja: **é o método, não bloqueio de robô nem `cf_clearance`**.

## Segundo defeito, achado só na verificação ao vivo

Com o POST no lugar, o `BdiBtbLendingOpenPositionsReader` voltou (1000×16) mas o
`BdiStocksSummaryReader` passou a falhar em outro ponto:

```
ValueError: 4 columns passed, passed data had 5 columns
```

A `DailyAverageStocks` declara **4 colunas** e envia **5 posições por linha**, a quinta sempre
`null`. Conferido em três tabelas: a `EconomicIndicators` bate exato (7×7), então **é por tabela**,
não uma propriedade do formato — um _reader_ não pode presumir nenhuma das duas formas.

Conserto: `_trim_unnamed_tail` descarta o excedente **apenas quando ele está inteiramente vazio**.
Um valor de verdade numa posição sem nome de coluna levanta `ValueError` — descartá-lo em silêncio
é exatamente como uma coluna da fonte deixa de chegar sem nada ficar vermelho, e o payload é
posicional, então não há como nomeá-lo.

## Desenho do _seam_

`download_file(..., bytes_payload=None, str_content_type=None)`:

- Sem `bytes_payload` → `GET`, como antes. Nenhum dos 4 chamadores existentes muda de
  comportamento.
- Com `bytes_payload` → `POST` carregando aqueles bytes.
- **O _seam_ não infere o `Content-Type`.** O que os bytes *significam* é conhecimento do
  chamador; adivinhar aqui tornaria uma codificação o padrão silencioso de todo endpoint futuro.
  Mesmo princípio da #182 (`str_declared_count_path`): o utilitário genérico não aprende o formato
  de uma fonte.

## O que foi feito

- [x] `http_downloader.download_file`: `bytes_payload` + `str_content_type` opcionais.
- [x] `_base_bdi_reader`: declara `_REQUEST_PAYLOAD = b"{}"` e
      `_REQUEST_CONTENT_TYPE = "application/json"`, e os passa em `_read_page`.
- [x] `_trim_unnamed_tail` + a falha alta para valor órfão.
- [x] Testes do _seam_ (`tests/unit/test_http_downloader.py`, novo): GET por padrão, POST com
      corpo e tipo, tipo não declarado não é enviado, corpo da resposta chega ao disco.
- [x] Teste do **_wiring_**: o _reader_ do BDI pede cada página com `(b"{}", "application/json")`.
- [x] Testes da cauda sem nome: cauda vazia é aparada, valor órfão falha.
- [x] 384 testes de unidade verdes.
- [x] **Verificação ao vivo dos dois _readers_** contra o pregão de 2026-08-07:
      `BdiStocksSummaryReader` 9×10 e `BdiBtbLendingOpenPositionsReader` 1000×16.
- [x] `docs/api/daily_bulletin/index.md` + `README.md`.

## Aberto

- **#185** (taxas de câmbio, Res. BCB 120) estava bloqueada por esta issue — **desbloqueada
  agora**.
- A resposta declara um `limitDate` por tabela (`"D-21"` na `EconomicIndicators`): o serviço só
  serve os últimos dias. Documentado, mas **ainda não é contrato executável** — vale decidir se
  vira validação quando houver mais _readers_ da seção.
- #186 (auditoria de cobertura das tabelas do BDI), #174, #159–#161, #136.
