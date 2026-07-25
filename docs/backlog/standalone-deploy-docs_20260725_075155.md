# Standalone deploy-docs workflow — issue #125

Issue: #125. Decouple versioned-docs deploy from the release, so a docs-only change can refresh
the `gh-pages` site without a package release (and without the local `mike deploy` guard dance).

## Done

- [x] **`.github/workflows/deploy-docs.yaml`** — standalone mike deploy with two entry points:
      `workflow_call` (release invokes it, passing the version) and `workflow_dispatch` (a
      maintainer redeploys/backfills any version from the Actions tab). `contents: write`,
      `fetch-depth: 0`, `cz changelog` regen (so the Changelog page's `--8<--` include resolves),
      computes the `X.Y` alias, `mike deploy --push --update-aliases <X.Y> latest` +
      `mike set-default --push latest`.
- [x] **Hardened against workflow injection** — the computed `minor` alias is passed to the deploy
      step via `env:` and referenced as `"$MINOR"`, never interpolated `${{ }}` straight into the
      `run:` shell (a malformed `version` input would otherwise survive the `cut` and inject).
      Improves on cvm's reference, which interpolates it directly.
- [x] **Refactored `release-pypi.yaml`** — the `deploy_docs` job is now a reusable-workflow call
      (`uses: ./.github/workflows/deploy-docs.yaml`, `with: version:
      ${{ needs.details.outputs.new_version }}`), keeping the prerelease guard
      (`if: needs.details.outputs.suffix == ''`) and `needs: [pypi, details]`. The inline mike
      steps are gone — one copy of the logic.
- [x] Both workflows parse; `yamllint` clean.

## Open

- [ ] **BlueprintX backport** — add `deploy-docs.yaml` to `templates/lib-minimal/` and refactor its
      `release-pypi.yaml` to call it. Captured in the lesson
      `scaffold-mike-doc-versioning-in-python-common.md` (amended 2026-07-25) + the repo mirror
      `docs/blueprintx-lessons.md`. Not done here — templates are only touched on explicit request.
- [ ] After merge, a `workflow_dispatch` run of `deploy-docs.yaml` (version `0.1.2`) is the live
      proof of the manual path; the `workflow_call` path re-proves on the next release.

## Notes

- The manual `mike deploy` we ran earlier (to publish the pt-BR site) is exactly what this
  workflow now does in CI — but from a runner with `GITHUB_TOKEN`, so it sidesteps the
  protected-branch guard and the pre-push `PRE_COMMIT_ALLOW_NO_CONFIG` hook that the local push
  hit.
- No `make deploy_docs` target added: `workflow_dispatch` supersedes it (CI has the write token
  and none of the local guards), so a local target would be the inferior path.
