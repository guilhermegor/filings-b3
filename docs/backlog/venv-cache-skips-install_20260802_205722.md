# #169 — o cache do venv fazia a CI pular a instalação e ficar verde num ambiente velho

Branch: `fix/169-venv-cache-skips-install`. Closes #169.

## Checklist

- [x] Defeito 1 — chave do cache passa a hashear `poetry.lock` **e** `pyproject.toml`
- [x] Defeito 2 — `path:` do cache reduzido a `.venv` (nunca um arquivo versionado)
- [x] Defeito 3 — `poetry check --lock` promovido a step próprio, incondicional, antes do restore
- [x] Defeito 4 (fora do escopo original, decisão do usuário) — release workflows param de
      **regenerar** o lock e passam a falhar alto
- [x] Sweep: os 3 workflows, 4 jobs — nenhuma instância do padrão sobrou
- [x] Teste *should-fail* do gate (falha com lock defasado, passa com árvore limpa)
- [x] `docs/contributing.md` — invariante registrada onde a afirmação vivia
- [ ] `/release` ao mergear (é `fix:` → PATCH; só CI, mas o tipo pede)

## O defeito

Três defeitos acoplados faziam a CI **passar sem instalar nada**:

1. `hashFiles('pyproject.toml')` sozinho na chave → todo diff *lock-only* é cache hit. É
   exatamente o diff que `versioning-strategy: lockfile-only` do Dependabot produz.
2. `poetry.lock` dentro de `path:` do cache → o cache restaurado **sobrescreve o lockfile
   commitado**, então o gate validava um artefato de cache, não a árvore.
3. `poetry check --lock` morava dentro do step guardado por `if: cache-hit != 'true'` → o gate
   era desligado pela mesma condição que o tornaria barato.

Medido no `wwdates`: `Install Dependencies` = `skipped` nos 15 jobs da matriz, job inteiro
`success`. **Um step pulado não é um step que falha** — o sinal está na conclusão dos *steps*,
não do *job*.

## Por que era pior do que "CI lenta"

`docs/contributing.md` afirmava que o `lockfile-only` mantém "a CI honesta sobre o que os
consumidores instalam". A afirmação era **falsa** enquanto o defeito 1 existia. E a tabela de
classes de risco do `pr_gate` dá auto-merge à classe `deps` com "a suíte de testes é o gate" —
ou seja, bumps de dependência **mergeavam sozinhos**, chancelados por uma suíte que nunca
instalou o bump. O Dependabot deste repo era um no-op decorativo.

## O sweep (o ponto que mais importa para a próxima vez)

A issue nomeava só `tests.yaml`. O mesmo bloco, **verbatim**, estava em `release-pypi.yaml` e
`release-test-pypi.yaml` — os workflows que publicam no PyPI. Consertar só o arquivo citado
deixaria o caminho de release restaurando `.venv` velho.

Pior: nos dois workflows de release o bloco não só pulava a instalação, ele **regenerava o
lock** (`rm -f poetry.lock && poetry lock --no-cache`) — re-resolvendo toda dependência para a
última versão in-range, no caminho que **publica**. Isso contradiz frontalmente o contrato que o
próprio `tests.yaml` enuncia ("never regenerate the lock in CI"). Um wheel publicado podia ser
construído contra dependências que ninguém revisou nem commitou.

Verificação estrutural pós-fix, nos 4 jobs dos 3 workflows: gate presente, incondicional e antes
do cache; `path` sem arquivo versionado; `poetry.lock` na chave. **Nenhum defeito restante.**

## O teste *should-fail*

Um gate que não examina nada reporta sucesso, então o gate foi exercitado nos dois sentidos:

| cenário | `poetry check --lock` |
|---|---|
| árvore limpa | exit **0** |
| dep adicionada sem re-lock | exit **1** (`pyproject.toml changed significantly`) |

Detalhe que justifica olhar o exit code e não o log: o comando imprime ~14 *warnings* de
deprecação idênticos **nos dois casos**. Quem lê o log no olho não distingue passa de falha.

## Aberto / follow-up

- **`pywin32` não existe no `pyproject.toml`.** Os 3 workflows carregam um bloco que copia o
  `pyproject.toml`, roda dois `re.sub` para remover `platform = "win32"` e `pywin32 = …`, e
  depois restaura o original. Os regexes não casam com nada — é cerimônia morta em torno de um
  arquivo que ela não altera. Não removido aqui para não misturar escopo; vale uma issue própria.
- O `poetry check --lock` roda agora em todos os legs da matriz (era pulado em cache quente).
  Custo desprezível, mas é uma mudança de comportamento: um lock defasado que antes passava
  silenciosamente em release agora **falha o release**. É o comportamento desejado.
