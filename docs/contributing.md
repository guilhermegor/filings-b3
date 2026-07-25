# **Contribuindo**

Tudo o que você precisa para desenvolver, testar e publicar esta biblioteca.

> **Veja também:** [Uso](usage.md) · [Referência da API](api/index.md) · o `CONTRIBUTING.md` na
> raiz do repositório contém a política oficial de branch/PR e de mensagens de commit.

---

## Preparando o ambiente de desenvolvimento

O projeto traz tanto um `Makefile` quanto um `tasks.sh` paralelo, então use o que servir para a sua
máquina — **`make init`**, ou **`bash tasks.sh init`** quando o `make` não estiver disponível (por
exemplo, um shell padrão do Windows).

```bash
make init        # semeia o .env, cria o venv do Poetry + instala deps, instala os hooks do pre-commit
# ou, sem make:
bash tasks.sh init
```

O `init` compõe `ensure_env` (semear `.env`), `venv` (criar o virtualenv do Poetry, instalar
**todas** as dependências, incluindo dev + docs) e `precommit` (instalar os hooks do git). O Poetry
é instalado automaticamente se estiver ausente.

## Testes e lint

```bash
make unit_tests          # poetry run pytest tests/unit/
make integration_tests   # poetry run pytest tests/integration/
make lint                # ruff + mypy + codespell + pydocstyle + gates de shell/sql/yaml
```

A CI roda os mesmos gates em cada pull request; mantenha-os verdes localmente antes de dar push.

## Verificando o pacote construído

Antes de abrir um PR de release, confirme que o _wheel_ realmente constrói e importa — isto pega
erros de empacotamento (um `__init__` faltando, um subpacote `_internal/` não enviado) que os
testes na árvore de código nunca revelam:

```bash
make install_dist_locally    # python -m build → instala → smoke-import → reporta o wheel construído
```

## Publicando a documentação (versionada, via mike)

O site publicado é **versionado**: um consumidor fixado em um release mais antigo lê a documentação
*daquele release*, não a do HEAD. O [mike](https://github.com/jimporter/mike) mantém a árvore de
versões no branch `gh-pages` e o MkDocs-Material renderiza o seletor de versões.

Os workflows dividem o trabalho:

| Workflow | Gatilho | O que faz |
|---|---|---|
| `Docs - Strict Build Check` (`docs.yaml`) | todo push + PR | apenas `mkdocs build --strict` — pega links/nav quebrados antes de um release. **Nunca faz deploy.** |
| `Deploy Versioned Docs` (`deploy-docs.yaml`) | 3 pontos de entrada (abaixo) | faz o deploy com `mike deploy --update-aliases <X.Y> latest` |
| `Release to PyPI` (`release-pypi.yaml`) | release manual | após a publicação no PyPI ter sucesso, **chama** o `deploy-docs.yaml` com a versão publicada |

O `deploy-docs.yaml` tem **três gatilhos**:

1. **`workflow_call`** — o pipeline de release o invoca **depois** da publicação no PyPI, então o
   site anuncia a versão que de fato foi publicada.
2. **`workflow_dispatch`** — um mantenedor pode (re)deployar uma versão manualmente pela aba
   Actions (para semear o `gh-pages`, backfillar docs de uma versão já publicada, etc.).
3. **`push` em `main`** tocando `docs/**` ou `mkdocs.yml` (exceto `docs/backlog/**`, não publicado)
   — uma mudança **somente-docs** não gera release, então sem isto ela ficaria invisível até o
   próximo release re-rodar o mike. No `push` não há versão de entrada, então o deploy mira o slot
   `X.Y` da **tag de release mais recente** — atualizando-o no lugar, nunca criando um novo.

Observações:

- **A granularidade é `X.Y`** — `1.4.2` e `1.4.7` compartilham a entrada `1.4`; o alias `latest`
  sempre segue o release mais recente e é a versão padrão de aterrissagem.
- **Prereleases nunca movem o `latest`** — uma versão com sufixo (`1.2.3rc1`) constrói e publica,
  mas o job de deploy da documentação é pulado.
- **Deploys são serializados** (`concurrency: deploy-docs`) para que um refresh por `push` e um
  deploy por release não corram no `gh-pages`.

### Configuração única do Pages

O mike serve a partir do **branch `gh-pages`**, então o Pages precisa estar configurado como
*Deploy from a branch → gh-pages*. O `GITHUB_TOKEN` do workflow não pode mudar isso (é um token de
GitHub App sem direitos de admin do repositório), então faça-o com a sua própria autenticação do
`gh`:

```bash
make enable_pages          # ou: bash tasks.sh enable_pages
```

Isto já roda dentro de `make init` / `bash tasks.sh init`, e é **idempotente e não bloqueante** —
avisa e continua se o `gh` estiver ausente/não autenticado, se nenhum remote resolver, ou se você
não for admin do repositório (um fork), então nunca quebra o `init`.

**A ordem importa:** o branch `gh-pages` não existe até o primeiro deploy de release criá-lo. Até
lá, o `enable_pages` deliberadamente deixa o Pages intocado (para que o site nunca aponte para um
branch vazio) e pede que você rode de novo. Então: faça o primeiro release, depois rode
`make enable_pages` uma vez. Alternativa manual: *Settings → Pages → Build and deployment →
Source: Deploy from a branch → `gh-pages` / `/`*.

## Pull requests

1. Crie o branch a partir do branch padrão seguindo a política de prefixos (`feat/…`, `fix/…`, …).
2. Preencha o template de PR por completo.
3. Garanta que os checks da CI (testes, lint, build da documentação) passem — eles são o gate de
   merge.

## Fazendo releases

Os releases são **guiados por tag e sem segredos** quando o projeto está conectado a um remote do
GitHub:

- A versão é a **tag do git** (via `poetry-dynamic-versioning`); o `pyproject.toml` guarda um
  _placeholder_ `0.0.0`. Não edite à mão. Dispare um release pela aba Actions
  (`Release to PyPI` / `Release to Test PyPI`, `workflow_dispatch` com a versão), ou dando push em
  uma tag `vX.Y.Z`.
- O workflow de release roda a **suíte completa de testes** como gate rígido, constrói com
  `python -m build` e publica via **OIDC trusted publishing** (`pypa/gh-action-pypi-publish`) — sem
  `PYPI_TOKEN` armazenado.
- O changelog é regenerado a partir das tags no momento do release/build (`make changelog`
  localmente); a CI nunca faz commit do `CHANGELOG.md` de volta no branch padrão protegido.

### Configuração do mantenedor — trusted publisher (uma vez, antes do primeiro release)

Registre um **trusted publisher** em **ambos** [pypi.org](https://pypi.org) e
[test.pypi.org](https://test.pypi.org). Cada claim precisa bater exatamente com o workflow, senão o
upload falha com um `invalid-publisher` opaco:

| Claim | Valor |
|-------|-------|
| Owner / repository | seu `<owner>` / `<repo>` do GitHub |
| Workflow filename | `release-pypi.yaml` (PyPI) / `release-test-pypi.yaml` (Test PyPI) |
| Environment | `release-pypi` / `release-test-pypi` |
| PyPI **Project Name** | precisa ser igual ao nome da distribuição (`name` no `pyproject.toml`) |

Para o primeiríssimo upload o projeto ainda não existe — registre um **pending publisher** no nível
da conta (não nas configurações de um projeto existente). Publicar de um laptop em vez da CI é o
único caso que ainda precisa de um API token; o OIDC só funciona a partir do GitHub Actions.

### Escolhendo os alvos de publicação

O scaffold conecta os workflows de release para o registro público oficial (PyPI) e um registro de
staging (Test PyPI). Para publicar em uma fonte **privada / não oficial** — uma fonte git
(`pip install git+https://…`), um índice PEP 503 privado, ou (para ecossistemas que suportam)
GitHub Packages — configure a fonte do lado do consumidor no `pyproject.toml` com uma guarda de
prioridade explícita contra confusão de dependências (`priority = "explicit"` do `poetry`;
`pip --index-url`, nunca `--extra-index-url`).

## Marca do site de documentação

A imagem de marca fica em `docs/assets/b3-logo.png`, conectada como logo/favicon do cabeçalho
(`theme.logo` / `theme.favicon` no `mkdocs.yml`) e como imagem da landing no `docs/index.md` (e do
cabeçalho do `README.md`). Para trocá-la:

1. Substitua `docs/assets/b3-logo.png` pelo seu próprio arquivo (mantenha o nome, ou atualize os
   dois caminhos no `mkdocs.yml`, o `<img>` no `docs/index.md` e o do `README.md`). O `README.md`
   renderiza a partir da cópia na raiz `assets/b3-logo.png` (o GitHub resolve relativo à raiz).
2. Ajuste **tamanho, posição e borda** direto nos atributos do `<img>` — `width="200"` (escala),
   `align="right"` (posição) e `style="border-radius: 15px;"` (borda arredondada) — no `docs/index.md`
   e no `README.md`.

## Proteção do repositório & segurança (uma vez, com script)

`make init` roda três helpers com gate de admin. Eles são **idempotentes e não bloqueantes**: sem
`gh`, sem auth, sem um remote do GitHub, ou sem direitos de admin do repositório, eles avisam e
pulam, então o `init` ainda completa para contribuidores e scaffolds offline. Rode qualquer um
deles isoladamente depois:

| Alvo | O que provisiona |
|--------|--------------------|
| `make enable_pages` | Fonte do GitHub Pages (branch gh-pages para docs versionada, senão Actions) |
| `make enable_repo_rules` | O ruleset de branch `pr-quality-gate` + as configurações de merge que o PR gate precisa |
| `make enable_security` | Relato privado de vulnerabilidades, alertas do Dependabot, atualizações de segurança do Dependabot |

### O ruleset `pr-quality-gate`

Aplicado a `~DEFAULT_BRANCH` (essa ref sobrevive a um rename de branch), buscado **pelo nome** para
que um novo run atualize no lugar em vez de criar uma duplicata:

| Regra | Configuração | Porquê |
|------|---------|-----|
| `pull_request` | `required_approving_review_count: 0` | ⚠️ **Precisa ser 0.** O GitHub proíbe aprovar o próprio PR, então qualquer valor ≥ 1 tranca um mantenedor solo para fora do merge do próprio trabalho. Zero ainda força toda mudança por um PR — essa é a real guarda. |
| `pull_request` | `required_review_thread_resolution: true` | Torna os comentários de review **vinculantes**: uma thread não resolvida bloqueia o merge em vez de ser decorativa. |
| `code_scanning` | CodeQL, security `high_or_higher`, alerts `errors` | Alertas ficam em `errors`: `errors_and_warnings`/`all` começam a bloquear merges em queries estilísticas, duplicando ruff/mypy com ruído. |
| `copilot_code_review` | `review_on_push: true` | É o **próprio tipo de regra** — não um parâmetro de `pull_request` (isso retorna HTTP 422 e faz o recurso parecer só de UI). |
| `non_fast_forward`, `deletion` | ligados | Sem force-push, sem deleção de branch no branch padrão. |
| `required_status_checks` | **vazio por padrão** | ⚠️ Deliberado. Um check obrigatório cujo nome nunca reporta bloqueia **todo** PR para sempre. Preencha `REQUIRED_CHECKS` em `bin/enable_repo_rules.sh` a partir de um PR real — `gh api repos/:owner/:repo/commits/<sha>/check-runs --jq ".check_runs[].name"` — depois rode de novo. |

**Deliberadamente não habilitado:** *Require code quality results* (severidade subjetiva de IA no
caminho de merge — ruff, mypy e os gates `bin/check_*.py` já impõem qualidade deterministicamente) e
*Restrict code coverage* (preview; o piso é fonte única no `.coveragerc` `fail_under`).

### Automático vs manual — a fronteira é config do repo vs plano da conta

**Nada aqui precisa de um clique.** Toda configuração de *repositório* acima é script. O que **não**
é script é o direito da sua *conta*: a regra `copilot_code_review` só dispara se o autor tem acesso
ao Copilot code review, e **code review não faz parte do Copilot Free**. Sem um plano qualificado, a
regra fica corretamente configurada e **inerte** — nenhum review aparece e nada dá erro. Esse
silêncio é a armadilha, porque o JSON do ruleset parece perfeito de qualquer jeito.

Toda outra regra (PR obrigatório, CI verde, CodeQL limpo) funciona independentemente de qualquer
plano do Copilot, então o ruleset vale a pena ser aplicado incondicionalmente. O Copilot Pro é
gratuito para estudantes, professores e mantenedores de OSS populares verificados.

> **Não** diagnostique isso com `gh api user/copilot_billing` → 404: esse endpoint é para
> gerenciamento de assentos de org/enterprise e dá 404 para uma conta pessoal mesmo com o Copilot
> Free ativo.

### Segurança

`SECURITY.md` na raiz do repositório é autodetectado pelo GitHub (sem chamada de API) e vira a
*Security policy* para Enabled; `make enable_security` liga a entrada correspondente de relato
privado, mais os alertas do Dependabot e as atualizações de segurança. Bumps de versão comuns são
separados — veja `.github/dependabot.yml`, que usa `versioning-strategy: lockfile-only` para
atualizar o `poetry.lock` (mantendo a CI honesta sobre o que os consumidores instalam) sem nunca
reescrever suas faixas do `pyproject`.

## Fluxo automatizado de PR (o quality gate)

Todo PR é classificado por `bin/pr_gate.py` (workflow `pr-gate.yaml`), que o rotula, posta um único
comentário fixo com uma tabela de status por eixo, e entrega as **classes seguras** ao auto-merge
nativo do GitHub. Duas regras são todo o design:

**Classificado por CAMINHO, nunca por tamanho do diff.** A mudança perigosa é *semântica*, não
grande: uma edição de um caractere em uma constante de schema/contrato é o menor diff possível e o
mais perigoso — e todo teste ainda passa, porque os testes afirmam o contrato que foi escrito.
Então o tamanho nunca decide elegibilidade; os caminhos alterados decidem. (O único lugar onde o
tamanho ainda importa — um diff `XL` é vetado — é **dispensado para um diff só de lockfile**, cuja
contagem de linhas acompanha quantos hashes de dependência mudaram, não o risco.)

| Classe de risco | Caminhos | Auto-merge? |
|------------|-------|-------------|
| `src` | `src/` | ❌ define o que "passar" significa |
| `tests` | `tests/` | ❌ define o que "passar" significa |
| `other` | qualquer coisa não casada | ❌ desconhecido = inseguro (default-deny) |
| `ci` | `.github/`, `bin/`, `Makefile`, `tasks.sh`, `.pre-commit-config.yaml` | ✅ |
| `deps` | `pyproject.toml`, `poetry.lock`, `requirements.txt` | ✅ (a suíte de testes é o gate) |
| `docs` | `docs/`, `mkdocs.yml`, `README.md`, `CHANGELOG.md`, … | ✅ |

**O consentimento é opt-OUT.** As classes seguras dão auto-merge **sem label**; adicione
`do-not-merge` para forçar um merge humano. O auto-merge nativo **não pula nada** — o GitHub segura
o merge até que todo check obrigatório do ruleset esteja verde, então o gate só decide
*elegibilidade*, nunca *se passou*.

Edite a tabela de risco (a constante `RISK_PATHS`) em `bin/pr_gate.py` para o layout real do seu
projeto.

### ⚠️ Depois de mudar a política do gate, faça o backfill dos PRs abertos

O gate roda em eventos de `pull_request`, então um PR que já estava **aberto** quando você muda a
política (as regras de classificação/consentimento em `pr_gate.py`, ou `allow_auto_merge` /
`delete_branch_on_merge`) **nunca é reavaliado** — ele mantém os labels e o estado de auto-merge que
recebeu sob as regras antigas até algum evento novo tocá-lo. Isso não é um bug; o gate simplesmente
nunca rodou de novo. Então, depois de mergear uma mudança de política, rode o backfill:

```bash
gh workflow run pr-gate.yaml -f backfill=true   # reavalia todo PR aberto
# para um PR do Dependabot, `gh pr comment <n> --body "@dependabot rebase"` também funciona
```

### PRs mergeados por bot e o reconciler

Um PR mergeado por **auto-merge nativo** (uma ação de bot) **não** fecha a issue vinculada e **não**
deleta o branch, mesmo com `delete_branch_on_merge` ligado — ações feitas por bot são
deliberadamente inertes para prevenir recursão de automação. O `reconcile-merged-prs.yaml` conserta ambos:
fecha as issues do `Closes #N` e deleta o branch de head dos PRs mergeados. Seu **run diário
agendado é o conserto real** — eventos agendados são isentos da supressão de "sem novos runs de
workflow" que também engole o caminho rápido `pull_request: [closed]` de um merge de bot. A latência
é de até um dia; esse é o custo aceito de não precisar de um personal access token.

### O gate de work-ledger

`bin/check_backlog_ledger.py` (pre-commit + CI) reprova um branch que toca `src/` ou caminhos de CI
mas não adiciona um ledger `docs/backlog/<kebab>_YYYYMMDD_HHMMSS.md` com um checklist `- [ ]` —
tornando a convenção de work-ledger por branch estrutural, em vez de algo que você lembra. Branches
rotineiros só de docs/deps/tests não precisam de nenhum.
