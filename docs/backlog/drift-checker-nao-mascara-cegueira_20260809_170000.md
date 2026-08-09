# #222 — o checker de deriva não pode mascarar a própria cegueira

Ledger da branch `fix/222-drift-checker-nao-mascara-cegueira`.

## Como estes defeitos foram achados

Não por um teste, nem por um _run_ vermelho. A revisão da PR #221 apontou três defeitos no
`check_bdi_catalog.py` — o irmão **novo**, escrito espelhando o `check_contract_drift.py`. Lá foram
corrigidos antes do merge; aqui estavam publicados havia semanas.

**Um defeito no código novo é evidência sobre o código antigo que lhe serviu de molde.**

## Os quatro defeitos

### 1. Uma queda da B3 era reportada como "sem deriva"

`collect_drift()` devolvia `[]` tanto quando **comparou e não achou nada** quanto quando **não
conseguiu comparar**, e o `main()` imprimia `no layout drift detected`. Uma linha verde afirmando
uma comparação que nunca aconteceu — exatamente a cegueira que o job existe para remover.

Agora `None` e `[]` dizem coisas diferentes, com mensagem de _skip_ explícita.

### 2. Uma issue de rastreio fechada virava duplicata semanal

A busca era `state=open`. Fechar a issue enquanto a deriva persistisse fazia o job abrir uma
**issue nova toda semana** — e o corpo que ele mesmo escreve promete o contrário: *"O job a reabre
se a deriva persistir"*. Agora consulta `state=all` e manda `{"state": "open"}` no `PATCH`.

### 3. Sem `timeout`, e uma falha do GitHub avermelhava o job

`urlopen` sem `timeout` pendura o job até o teto do _runner_. E a exceção subia livre, deixando
vermelho um job cujo contrato inteiro é reportar abrindo issue em vez de falhar — com a deriva já
no stdout. Agora tem `timeout` e `except (OSError, ValueError)`.

### 4. (novo, achado aqui) Sem token era `KeyError`

O guarda checava só `GITHUB_REPOSITORY`, mas o `_api` lê `os.environ['GITHUB_TOKEN']` direto. Uma
variável sem a outra derrubava o job com `KeyError` não tratado.

## Por que sobreviveram tanto tempo

O módulo de teste existia — e **não testava nada disto**. O docstring dele dizia:

> *"Only the offline oracle is unit-tested — the network fetch and GitHub issue upsert are
> exercised in the weekly job."*

"Exercitado no job semanal" **não é cobertura**: ninguém lê um _run_ agendado que passou. A prova é
que renomear `find_open_drift_issue` → `find_drift_issue` não quebrou teste nenhum.

## Controle negativo — o que torna estes testes evidência

Rodei os 5 testes novos **contra o código antigo**:

```
5 failed, 7 passed     <- codigo antigo
12 passed              <- codigo corrigido
```

Cada teste novo falha pelo seu próprio defeito, e os 7 antigos passam nos dois lados. Sem isso,
um teste novo verde não distingue "o conserto funciona" de "o teste não olha".

## O que foi feito

- [x] Os quatro consertos em `bin/check_contract_drift.py`.
- [x] `bin/pr_gate.py` — mesmo buraco de `timeout` no `urlopen` (item de escopo da issue,
      confirmado). Corrigido; os 9 avisos de lint do arquivo são pré-existentes (9 antes, 9
      depois).
- [x] 5 testes novos + docstring do módulo corrigido, que afirmava uma cobertura que não existia.
- [x] Controle negativo executado, acima.
- [x] 409 testes de unidade verdes.

## Aberto

- Nada nesta issue. Os avisos de lint pré-existentes do `pr_gate.py` seguem — fora de escopo aqui.
