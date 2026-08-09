# #182 — contagem de registros que o arquivo declara

Ledger da branch `feat/182-contagem-declarada-de-registros`.

## O risco

Um download interrompido é **invisível por construção**: o _parser_ em _stream_ lê os bytes que
chegaram, o XML é bem-formado até o corte, cada linha que chegou é válida, contrato e tipagem
passam — e o `read()` devolve um _frame_ menor, indistinguível de um pregão com menos
instrumentos. Nada fica vermelho.

O arquivo já traz a defesa no cabeçalho: `TtlNbOfMsg` (em ISO-20022 cada `<Instrm>` é uma
_message_). Conferido nos dois _snapshots_ do `IN260729`: declarado 183.174 / contados 183.174,
e 183.164 / 183.164.

## Desenho — o _seam_ não conhece o formato

Decisão do dono do repositório, e é o que torna a guarda reaproveitável:

- `read_xml` recebe `str_declared_count_path=None` — **opcional**. O _seam_ prevê que a
  declaração **possa** existir, nunca que exista; um formato que não declara nada simplesmente
  omite o argumento.
- **Por caminho, não por nome de _tag_.** Quem sabe que a contagem se chama `TtlNbOfMsg` e onde
  ela mora é o _reader_ concreto (`_DECLARED_COUNT_PATH = "BizGrpDtls/TtlNbOfMsg"`). Fixar o nome
  dentro de `_internal/utils/xml_reader.py` acoplaria um utilitário genérico de XML ao esquema de
  uma bolsa, e o próximo formato exigiria um segundo caminho de código em vez de um argumento.
- A contagem é resolvida com o mesmo mecanismo dos escalares (casar o elemento-cabeça quando ele
  fecha), mas **não vira coluna** — é uma afirmação sobre o artefato, não dado.
- Contada **antes** do `str_row_filter`, senão os 17 _readers_ por sub-bloco reprovariam por
  construção (8.293 linhas contra 183.174 declaradas).

## O que foi feito

- [x] `read_xml`: parâmetro opcional, contagem antes do filtro, `_check_declared_count` com três
      falhas nomeadas (nada declarado no caminho, declaração não-numérica, número que não bate).
- [x] `_base_instruments_file_reader`: passa `BizGrpDtls/TtlNbOfMsg`.
- [x] Testes do _seam_ (5): contagem certa passa; arquivo com menos registros do que declara
      falha; contagem feita antes do filtro; caminho dado sem declaração falha; sem caminho não
      confere nada.
- [x] Teste do **_wiring_** na família: um `IN` adulterado (declara 51, entrega 50) faz o
      `InstrumentsFileReader.read()` falhar — sem ele, remover o argumento do _reader_ não
      quebraria nenhum teste.
- [x] 377 testes de unidade verdes.
- [x] Verificação ao vivo contra o `IN260729` real: o caminho resolve no _snapshot_ de
      pós-fechamento (183.174 registros, 664 MB — o de pré-abertura tem 183.164 e ~660 MB, que é
      o número citado no #167), lido em _stream_, e os 183.174 declarados batem; o _reader_ por
      sub-bloco segue com 8.293 linhas.
- [x] `docs/api/search_trading_session/index.md` + `README.md`.

## Aberto

- Nada nesta issue. Segue em aberto no projeto: #183 (endpoint do BDI com HTTP 405), #174
  (chore de CI), #159–#161 (ouro, bloqueadas por _fixture_), #136 (bot-merge).
