#!/usr/bin/env bash
# Provision the `pr-quality-gate` branch ruleset + the repo settings the PR gate depends on.
#
# WHY THIS EXISTS: merge protection that lives in a maintainer's memory is protection a fresh
# clone or fork silently lacks. The ENTIRE ruleset is writable through the REST API, so nothing
# here needs a click in Settings → Rules. Like enable_pages.sh, these are repo-settings writes:
# CI's GITHUB_TOKEN (an App installation token) CANNOT make them — only a maintainer's `gh auth`
# with repo-admin can. Hence `make init`, not CI.
#
# WHAT IT APPLIES (idempotent — looked up BY NAME, then PUT if it exists / POST if it does not;
# never a blind POST, which would duplicate the ruleset):
#   * pull_request              — required_approving_review_count: 0 (see below) +
#                                 required_review_thread_resolution: true, so review comments are
#                                 binding (unresolved → no merge) instead of decorative.
#   * code_scanning             — CodeQL, security alerts high_or_higher, alerts at `errors`.
#   * copilot_code_review       — its OWN rule type (NOT a pull_request parameter — see below).
#   * non_fast_forward, deletion — no force-push, no branch deletion.
#   * required_status_checks    — ONLY when REQUIRED_CHECKS below is non-empty (see the warning).
# Plus the settings the gate cannot set itself: code-scanning default setup, allow_auto_merge,
# delete_branch_on_merge, and the `do-not-merge` opt-out label.
#
# ⚠️ required_approving_review_count MUST be 0: GitHub forbids an author approving their own PR,
# so any value >= 1 locks a solo maintainer out of merging their own work. Zero still forces every
# change through a PR — that is the actual guardrail.
#
# ⚠️ Copilot automatic code review is REST-settable, but as its own rule type. The intuitive
# `pull_request.parameters.automatic_copilot_code_review_enabled` returns HTTP 422 "Unexpected
# parameter", which makes the feature LOOK UI-only — it is not.
#
# ⚠️ THE AUTOMATIC/MANUAL BOUNDARY IS REPO CONFIG vs ACCOUNT PLAN. Every repository setting here
# is scriptable. What is NOT is the account's entitlement: the copilot_code_review rule only fires
# if the author has access to Copilot code review, and code review is NOT part of Copilot Free.
# Without a qualifying plan the rule sits correctly configured and INERT — no review appears and
# nothing errors. The silence is the trap; the ruleset JSON looks perfect either way. Every OTHER
# rule (PR required, CI green, CodeQL clean) works regardless of any Copilot plan.
#   Do NOT diagnose this via `gh api user/copilot_billing` → 404: that endpoint is for org seat
#   management and 404s for a personal account even when Copilot Free is active. Read the plan page.
#
# DELIBERATELY NOT ENABLED (each would be a second source of truth for a gate this scaffold
# already owns): "Require code quality results" (subjective AI severity on the merge path — ruff,
# mypy and the bin/check_*.py gates already enforce quality deterministically) and "Restrict code
# coverage" (preview; the floor is single-sourced in .coveragerc fail_under).
#
# Idempotent + non-blocking: gh absent / unauthenticated / not repo-admin → WARN and return 0 so
# `init` still completes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

RULESET_NAME="pr-quality-gate"

# ⚠️ EMPTY BY DEFAULT, ON PURPOSE — DO NOT GUESS CHECK NAMES.
# A required status check that never reports blocks every PR FOREVER (GitHub waits for a result
# that will never arrive), and the names here must match the check-run names exactly — which for a
# matrix job include the expanded matrix values. Populate it from a REAL PR once CI has run:
#
#   gh api repos/:owner/:repo/commits/<pr-head-sha>/check-runs --jq '.check_runs[].name' | sort -u
#
# then list the ones that must gate merges. While empty, the rule is simply not added, and CI
# still runs on every PR — it just does not block the merge button.
REQUIRED_CHECKS=()

require_gh() {
	# gh must be installed and authenticated. Missing either is a skip, not a failure.
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping ruleset provisioning (run 'make enable_repo_rules' later)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping ruleset provisioning (run 'gh auth login', then 'make enable_repo_rules')"
		return 1
	fi
	return 0
}

resolve_repo() {
	# Print owner/repo for the current checkout, or empty when no GitHub remote resolves.
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

build_rules_json() {
	# Emit the rules array. required_status_checks is appended only when REQUIRED_CHECKS is set,
	# because an unsatisfiable required check is a permanent merge block (see the warning above).
	local str_checks_rule=""
	if [ ${#REQUIRED_CHECKS[@]} -gt 0 ]; then
		local str_contexts=""
		local str_check
		for str_check in "${REQUIRED_CHECKS[@]}"; do
			str_contexts+="$(printf '{"context":"%s"},' "$str_check")"
		done
		str_contexts="${str_contexts%,}"
		str_checks_rule=$(printf ',{"type":"required_status_checks","parameters":{"strict_required_status_checks_policy":false,"required_status_checks":[%s]}}' "$str_contexts")
	fi

	cat <<EOF
[
  {"type":"pull_request","parameters":{
    "required_approving_review_count":0,
    "dismiss_stale_reviews_on_push":false,
    "require_code_owner_review":false,
    "require_last_push_approval":false,
    "required_review_thread_resolution":true
  }},
  {"type":"code_scanning","parameters":{"code_scanning_tools":[
    {"tool":"CodeQL","security_alerts_threshold":"high_or_higher","alerts_threshold":"errors"}
  ]}},
  {"type":"copilot_code_review","parameters":{
    "review_on_push":true,
    "review_draft_pull_requests":false
  }},
  {"type":"non_fast_forward"},
  {"type":"deletion"}${str_checks_rule}
]
EOF
}

build_ruleset_json() {
	# The full ruleset payload. `~DEFAULT_BRANCH` survives a branch rename and ports to any repo.
	local str_rules
	str_rules="$(build_rules_json)"
	cat <<EOF
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": $str_rules
}
EOF
}

apply_ruleset() {
	# Idempotent: find the ruleset BY NAME, then PUT (update) or POST (create). $1 = owner/repo.
	local str_repo="$1"
	local str_id
	str_id=$(gh api "repos/$str_repo/rulesets" --jq \
		".[] | select(.name == \"$RULESET_NAME\") | .id" 2>/dev/null | head -1 || true)

	if [ -n "$str_id" ]; then
		print_status "info" "Updating existing ruleset '$RULESET_NAME' (id $str_id)..."
		if build_ruleset_json | gh api -X PUT "repos/$str_repo/rulesets/$str_id" --input - >/dev/null 2>&1; then
			print_status "success" "Ruleset '$RULESET_NAME' updated"
			return 0
		fi
	else
		print_status "info" "Creating ruleset '$RULESET_NAME' on ~DEFAULT_BRANCH..."
		if build_ruleset_json | gh api -X POST "repos/$str_repo/rulesets" --input - >/dev/null 2>&1; then
			print_status "success" "Ruleset '$RULESET_NAME' created"
			return 0
		fi
	fi

	print_status "warning" "Could not apply ruleset to $str_repo (needs repo-admin rights) — a maintainer must run 'make enable_repo_rules'"
	return 0
}

enable_code_scanning() {
	# The code_scanning rule needs a tool to gate on. Already-configured → the PATCH is a no-op.
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo/code-scanning/default-setup" -f state=configured >/dev/null 2>&1; then
		print_status "success" "CodeQL default setup configured"
	else
		print_status "warning" "Could not configure CodeQL default setup (needs repo-admin, or the language is unsupported) — enable it in Settings → Code security"
	fi
}

enable_merge_settings() {
	# Prerequisites the PR gate CANNOT set itself. Without allow_auto_merge the
	# enablePullRequestAutoMerge mutation SILENTLY NO-OPS — the feature is inert with no error.
	local str_repo="$1"
	if gh api -X PATCH "repos/$str_repo" -F allow_auto_merge=true -F delete_branch_on_merge=true >/dev/null 2>&1; then
		# Read the setting BACK: a green API call is not proof the mutation took.
		local str_state
		str_state=$(gh api "repos/$str_repo" --jq .allow_auto_merge 2>/dev/null || echo "unknown")
		if [ "$str_state" = "true" ]; then
			print_status "success" "allow_auto_merge + delete_branch_on_merge enabled (verified)"
		else
			print_status "warning" "allow_auto_merge reads back as '$str_state' — auto-merge will silently no-op until it is true"
		fi
	else
		print_status "warning" "Could not set merge settings on $str_repo (needs repo-admin rights)"
	fi
}

ensure_optout_label() {
	# The PR gate's opt-OUT escape hatch: safe classes auto-merge by default; this label disables it.
	local str_repo="$1"
	gh label create "do-not-merge" --repo "$str_repo" --color "b60205" \
		--description "Block this PR from auto-merging (PR gate opt-out)" --force >/dev/null 2>&1 &&
		print_status "success" "Label 'do-not-merge' present (auto-merge opt-out)" ||
		print_status "warning" "Could not create the 'do-not-merge' label on $str_repo"
}

main() {
	print_status "section" "Repository Rules & Merge Settings"
	# A skip (no gh / not authed) must not fail init — return 0 either way.
	if ! require_gh; then
		return 0
	fi

	local str_repo
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "warning" "No GitHub remote resolved — skipping (push the repo to GitHub first)"
		return 0
	fi

	enable_code_scanning "$str_repo"
	enable_merge_settings "$str_repo"
	ensure_optout_label "$str_repo"
	apply_ruleset "$str_repo"

	if [ ${#REQUIRED_CHECKS[@]} -eq 0 ]; then
		print_status "info" "No required status checks declared — CI runs but does not block merges. Populate REQUIRED_CHECKS in bin/enable_repo_rules.sh from a real PR's check-run names, then re-run."
	fi
}

main "$@"
