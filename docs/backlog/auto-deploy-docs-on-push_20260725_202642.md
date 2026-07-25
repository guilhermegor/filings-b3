# #134 — auto-deploy docs on push to main touching docs

Branch: `ci/134-auto-deploy-docs-on-push`

## Problem

Versioned docs deploy was **release-owned** (`mike deploy` only inside `release-pypi.yaml`). A
docs-only PR (#133) merged → no release → the live `/0.1/` site stayed frozen at 0.1.3's structure.
The user asked why the new docs weren't online. Root-cause fix: auto-trigger the deploy on merges to
`main` that touch docs.

## Done

- [x] `.github/workflows/deploy-docs.yaml` — added a **third entry point**: `push` on `main`
      filtered to `docs/**` + `mkdocs.yml`, excluding `docs/backlog/**` (unpublished).
- [x] Version fallback: push has no `version` input, so `Compute X.Y Alias` falls back to the latest
      tag (`git describe --tags --abbrev=0 | sed 's/^v//'`), refreshing the current minor slot in
      place; **skips gracefully** (deploy step `if: skip != 'true'`) when no tag exists yet.
- [x] Workflow-level `concurrency: {group: deploy-docs, cancel-in-progress: false}` so a push-refresh
      and a release-deploy can't race on `gh-pages`.
- [x] `docs/contributing.md` — documented the 3 entry points + the concurrency serialization.
- [x] Lesson captured (amended `scaffold-mike-doc-versioning-in-python-common.md` in the global
      store + README index + repo mirror `docs/blueprintx-lessons.md`).

## Verification

- [x] yamllint clean; YAML parses; triggers = push/workflow_call/workflow_dispatch.
- [ ] After merge: confirm the push-triggered `deploy-docs` run fires and the site refreshes
      (this PR itself touches docs → the merge should trigger it, proving the feature live).

## Notes

- CI-only change; no `src/` diff → `s:release` reports no release on merge.
- The merge of THIS PR is the live proof: it touches `docs/contributing.md`, so it should trigger
  the new push deploy automatically.
