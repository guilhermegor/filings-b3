# Align .github with filings-cvm; harden auto-merge branch cleanup — issue #127

Issue: #127. Compared `filings-b3/.github/` against the sibling `filings-cvm/.github/` and closed
the one functional gap in the merged-PR reconciler (the mechanism that deletes an auto-merged PR's
branch), plus filename parity.

## Done

- [x] **Added the `concurrency` guard** to the reconciler — `group: reconcile-merged-prs`,
      `cancel-in-progress: false`. Without it, the daily schedule tick and a `pull_request:[closed]`
      event could race on the same branch/issue (both trying to delete the head ref). This was the
      only functional difference from cvm's version.
- [x] **Renamed** `pr-reconcile.yaml` → `reconcile-merged-prs.yaml` for folder-name parity with
      cvm, keeping b3's richer WHY comments (the measured GITHUB_TOKEN-suppression findings).
- [x] Updated the reference in `docs/contributing.md`.
- [x] Deleted the merged orphan branch `fix/required-checks-116` (PR #117, merged 2026-07-23) —
      left behind because a squash-merge tip is not an ancestor of main and the reconciler's window
      had passed.
- [x] `yamllint` clean; the workflow parses and `concurrency` is present.

## Verified already-present (no change needed)

- [x] `delete_branch_on_merge: true` is set → **human-merged** PRs delete their branch immediately.
- [x] The **bot/auto-merge** branch+issue cleanup already existed (the reconciler): for a merge by
      `GITHUB_TOKEN`, `delete_branch_on_merge` does not fire, so the scheduled reconciler is the
      guaranteed backstop. The user's "auto-merged PR must delete its own branch" is satisfied by
      this path — immediate deletion for a bot merge is impossible with `GITHUB_TOKEN` (the
      "no new workflow runs" suppression); the daily sweep is the accepted trade-off, not a PAT.

## Deliberately NOT ported (legitimate differences — the "why/where")

- `contract-drift.yaml` and `portal-completeness.yaml` are **cvm-only**: weekly, non-blocking
  detectors for the **CVM regulatory data portal** (cvm issues #98 / #111). filings-b3 reads B3
  exchange data and has no such portal. A B3 analogue (e.g. a live-glossary contract-drift check,
  relevant given the stpstone-vs-live column drift we hit) would be a **new feature**, not a
  folder-alignment — file it separately if wanted.
- The other common files (`CLAUDE.md`, `tests.yaml`, `pr-gate.yaml`, `dependabot.yml`, …) differ in
  **project-specific content**, not tooling shape; blindly overwriting them with cvm's would clobber
  b3's own matrix/paths/domain text. Left as-is.

## Open

- [ ] After merge, the reconciler still runs on its daily schedule; nothing to prove live beyond
      the next auto-merged ci/deps/docs PR getting swept.
