# Reconciler `--json merged` bug — sweep silently no-ops — issue #129

Issue: #129. The merged-PR reconciler ran green but reconciled nothing; found while proving the
#127 alignment live.

## Root cause (measured live)

`reconcile_pr` gated on a **non-existent** `gh pr view` field:

```bash
merged=$(gh pr view "$pr" --json merged --jq .merged 2>/dev/null || echo "false")
[ "$merged" = "true" ] || return 0
```

`gh pr view <n> --json merged` → `Unknown JSON field: "merged"`. `2>/dev/null` swallows the error,
`|| echo "false"` sets `merged="false"`, so **every PR returns early** and the sweep does nothing —
green, because `return 0` is success. The real field is `state` (`"MERGED"` for a merged PR).

Live proof: reconciler run 30155847746 (green) after bot-auto-merges #126/#128 left issues #125/#127
**OPEN** and both head branches alive, despite correct `closingIssuesReferences`.

## Done

- [x] Fixed `reconcile_pr`: `--json state --jq .state` + `[ "$pr_state" = "MERGED" ]` (distinct var
      from the `state` reused in the issue loop). Comment records the trap.
- [x] Dry-ran the fixed logic locally: correctly targets #125/#127 to close and both orphan branches
      (`ci/125-*`, `ci/127-*`) to delete. `yamllint` + YAML parse clean.

## Open

- [ ] After merge, run the reconciler once (workflow_dispatch) to CLOSE #125/#127/#129 and delete
      the orphan branches — the live proof the fix reconciles.
- [ ] BlueprintX lesson: the template's `pr-reconcile.yaml` ships the same broken `--json merged`,
      so the "auto-merged PRs don't close issues" fix is itself inert in every scaffolded project.
      Amend `auto-merged-prs-do-not-close-their-linked-issues.md`.

## Note

filings-cvm does NOT have this bug (it uses a job-level `if` + `state`), so the bug is in the
`lib-minimal`/`python-common` template that filings-b3 was generated from — cvm's reconciler was
rewritten past it. This is exactly why the lesson's "provoke the bot path to verify" methodology
matters: triggering it live is what exposed the inert fix.
