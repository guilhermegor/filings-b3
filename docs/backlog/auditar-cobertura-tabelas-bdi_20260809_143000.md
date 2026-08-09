# #186 — auditoria de cobertura das tabelas do BDI

Ledger da branch `chore/186-auditar-cobertura-tabelas-bdi`.

## O resultado

| Estado | Tabelas |
|---|---|
| Implementadas | 3 |
| Com issue (já existia) | 34 |
| **Sem cobertura nenhuma** | **32** |
| **Total publicado pela B3** | **69** |

As 32 viraram as issues **#189–#220**, todas em Backlog no kanban.

## Por que a lacuna existia

O _backlog_ do BDI nasceu do inventário da **stpstone**, não do catálogo da **B3**. Medido: 38
módulos da stpstone apontam para tabelas do BDI, alcançando **36 tabelas distintas** — exatamente
o recorte que virou issue. As outras 33 nunca existiram para o projeto.

Isso é um **falso negativo por construção**: a suíte fica verde *porque* ninguém está olhando. Não
havia reader quebrado, nem teste vermelho, nem issue parada — só ausência. E ela só apareceu
quando um usuário pediu as taxas de câmbio (#185), não porque o processo a tenha detectado.

Confirmação de que o recorte da stpstone era válido no que cobria: **zero** módulos apontam para
tabela fora da lista da B3.

## Como o cruzamento foi feito

Antes de mapear à mão, testei uma hipótese que valeu: **os módulos da stpstone citam o nome da
tabela da B3 na URL que constroem**. Então o mapa `módulo → tabela` sai por _regex_, e
`módulo → issue` sai do título das issues (`b3_*`). O elo que faltava era mecânico o tempo todo.

(Achado lateral: a stpstone já usava `requests.post(url, json={})`. O defeito da #183 — GET contra
uma API de POST — nasceu na migração, não numa mudança da B3.)

## O índice autoritativo

`GET https://arquivos.b3.com.br/bdi/table/classifications` → as 69 tabelas em 14 classificações.
Descoberto no _bundle_ do SPA do BDI, que expõe as rotas `/table/all`, `/table/classifications`,
`/table/delayed`, `/table/export`, `/table/token`, `/download/chapters`, `/download/status`.

Três armadilhas medidas:

1. **A rota de índice é GET; a de dados é POST.** Invertidas — `/table/classifications` devolve
   405 a um POST.
2. `/table/all` existe mas devolve `{}`.
3. **Nome de tabela inexistente devolve 200 com tabela vazia, nunca 404.** Sondar nome por
   tentativa é inútil, e "vazio" não distingue *nome errado* de *sem dado naquele dia*.

## O que foi entregue

- [x] **32 issues** (#189–#220), uma por tabela sem cobertura, cada uma citando a classificação, o
      nome amigável, a regra bloqueante de confirmar o layout e a `curl` que revela `columns[]`,
      `limitDate` e `texts[]`.
- [x] `bin/bdi_catalog.py` — as 69 tabelas com estado e destino, em ordem alfabética (um _diff_
      mostra inserção, nunca reordenação).
- [x] `bin/check_bdi_catalog.py` — busca o índice da B3, compara **nos dois sentidos** e abre/
      atualiza **uma** issue de rastreio. Nunca reprova o _build_: uma queda da B3 e uma
      divergência real são indistinguíveis num check vermelho.
- [x] Job `catalog` acrescentado ao `contract-drift.yaml` em vez de um workflow novo — mesma
      natureza, mesma cadência, e **um gatilho agendado a menos para manter vivo** (o GitHub
      desativa um `schedule` após ~60 dias sem push).
- [x] 10 testes do oráculo puro, incluindo os _should-fail_: tabela nova, tabela aposentada,
      índice vazio (que levanta em vez de reportar 69 falsas aposentadorias), e o marcador que
      separa esta issue de rastreio da issue do outro job — os dois compartilham o label.
- [x] Executado de verdade: `catalog agrees with B3 (69 tables)`, exit 0.

## Decisões que valem registro

- **O marcador, não o label, identifica a issue.** Os dois jobs semanais usam `contract-drift`;
  casar só pelo label faria cada um sequestrar a issue do outro. Tem teste.
- **Índice vazio levanta.** Não dá para distinguir de divergência total, e reportar as 69 entradas
  como "aposentadas" seria pior que silêncio — o chamador trata como semana pulada.
- **Não existe estado "sem cobertura" no catálogo.** Uma tabela sem destino é exatamente o defeito
  que ele previne; o teste reprova a entrada em vez de aceitá-la como valor legítimo.
- O checker roda **sem Poetry** no CI: usa só a biblioteca padrão, então instalar o pacote só
  somaria minutos e um modo de falha.

## Aberto

- As 32 issues estão em Backlog, nenhuma iniciada.
- #174, #136, #159–#161 (ouro, bloqueadas por _fixture_), #175.
