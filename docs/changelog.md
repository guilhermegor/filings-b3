# **Changelog**

Histórico de releases deste projeto. As entradas são geradas a partir das mensagens de
[Conventional Commit](https://www.conventionalcommits.org/) via
[commitizen](https://commitizen-tools.github.io/commitizen/), então os títulos de versão abaixo
acompanham o que de fato foi publicado.

**Como atualiza:** as seções abaixo são geradas a partir das tags do git e do histórico de commits
pelo `cz changelog`. A página publicada é regenerada **do zero a cada build da documentação** (o
workflow de docs roda `cz changelog` antes do `mkdocs build`), então ela sempre reflete o branch
padrão — a CI nunca faz commit do `CHANGELOG.md` de volta no repositório. Você nunca a edita à mão.
Regenere ou pré-visualize localmente a qualquer momento com `make changelog` (ou
`bash tasks.sh changelog`).

---

<!-- Single-sourced from the repo-root CHANGELOG.md — never edit the entries here by hand. -->
--8<-- "CHANGELOG.md"
