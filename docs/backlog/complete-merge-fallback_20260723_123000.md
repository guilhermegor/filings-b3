# Close the last babysitting gap: finish an eligible green PR that cannot be armed

Issue: #116 (completes it). PR #117 made auto-merge work for the *normal* path — a PR opened,
checks pending, gate arms auto-merge, GitHub merges when green (proved end-to-end by #117
merging itself, `mergedBy: app/github-actions`).

## The gap that remained

GitHub **refuses** to arm auto-merge on a PR that is *already* mergeable — there is nothing left
to queue behind. The gate then warned and abandoned it, so the PR sat open until a human merged
it. That is exactly what happened to PR #1: `mergedBy: guilhermegor`, by hand.

It is not a rare edge. It fires whenever checks finish **before** the gate runs:

- a policy **backfill** (`workflow_dispatch`) over already-green open PRs;
- a **reopened** PR whose checks already passed;
- removing **`do-not-merge`** after CI went green — the `labeled`/`unlabeled` trigger re-runs the
  gate on a PR that is by then fully green.

## The fix

`should_complete_merge(eligible, armed, gate_state, mergeable_state)` — a pure, unit-tested
predicate — plus a `PUT /pulls/:n/merge` (squash) in `main()` when it returns True.

It merges **only** when *all* of:

| Condition | Why |
|---|---|
| `eligible` | `src`/`tests`/`other` are never auto-merged; the fallback must not smuggle them in |
| **not** `armed` | if GitHub is holding the merge, it owns it — never race it |
| `gate_state == "success"` | the gate's own axes are all terminal **and** green |
| GitHub's `mergeable_state == "clean"` | **the ruleset's verdict**, not this script's |

### Why this does not breach "never let a gate script judge check results and merge"

The script does not judge. `mergeable_state == "clean"` is **GitHub's** statement that every
required check *of the ruleset* passed — the merge only completes a decision already made
elsewhere. The gate's own `success` view is required *as well*, as a second, independent
condition: a PR whose required checks never reported cannot pass both.

`mergeable_state` is re-fetched immediately before the merge, because GitHub computes it
asynchronously — the value read at the start of the run is stale, and `unknown` is explicitly
treated as "no".

## Tests

6 added (46 in `test_pr_gate.py`, **182 repo-wide**), covering: the happy path, armed (must not
race), ineligible, every non-success gate state, and every non-`clean` mergeable state including
`unknown`.

## Status of the guarantee

| Path | Covered by |
|---|---|
| PR opened, checks pending | auto-merge armed → GitHub merges when green (**proved**: #117) |
| Checks already green when the gate runs | this fallback |
| Not eligible (`src`/`tests`/`other`) | never merged — by design |
| `do-not-merge` present | never merged — by design |
| Required checks red | GitHub blocks; neither path can merge |

## Open

- [ ] Backport to BlueprintX: `pr_gate.py` (all four fixes) + `contents: write` in
      `pr-gate.yaml`. `REQUIRED_CHECKS=()` stays empty in the template — it is per-repo data.
