#!/usr/bin/env bash
# Flip the free, API-settable GitHub security toggles for this repo.
#
# WHY THIS EXISTS: a published project should have supply-chain + vulnerability-reporting hygiene
# on, but the Settings → Security checkboxes are not reproducible and are silently forgotten on a
# fork or a fresh clone — the same rationale that put the branch ruleset in enable_repo_rules.sh.
# All three toggles are plain PUTs (204 No Content), so nothing needs a click.
#
# Sibling of enable_repo_rules.sh / enable_pages.sh: these are repo-settings writes, so CI's
# GITHUB_TOKEN (an App installation token) CANNOT make them — only a maintainer's `gh auth` with
# repo-admin can. Hence `make init`, not CI. Idempotent + non-blocking throughout.
#
# NOT scripted here (it needs no API call): GitHub auto-detects a root SECURITY.md and flips
# "Security policy" to Enabled by itself. The scaffold ships that file.
#
# Version bumps vs security fixes are DIFFERENT features:
#   * automated-security-fixes (below)  — Dependabot opens PRs for known VULNERABILITIES.
#   * .github/dependabot.yml (shipped)  — Dependabot opens PRs for ordinary VERSION updates.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

require_gh() {
	# gh must be installed and authenticated. Missing either is a skip, not a failure.
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping security toggles (run 'make enable_security' later)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping security toggles (run 'gh auth login', then 'make enable_security')"
		return 1
	fi
	return 0
}

resolve_repo() {
	# Print owner/repo for the current checkout, or empty when no GitHub remote resolves.
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

enable_toggle() {
	# PUT one security toggle. $1 = owner/repo, $2 = API path segment, $3 = human label.
	local str_repo="$1" str_path="$2" str_label="$3"
	if gh api -X PUT "repos/$str_repo/$str_path" >/dev/null 2>&1; then
		print_status "success" "$str_label enabled"
	else
		print_status "warning" "Could not enable $str_label (needs repo-admin rights, or it is unavailable for this repo) — check Settings → Code security"
	fi
}

main() {
	print_status "section" "GitHub Security Toggles"
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

	# Private vulnerability reporting — the intake channel SECURITY.md points researchers at.
	enable_toggle "$str_repo" "private-vulnerability-reporting" "Private vulnerability reporting"
	# Dependabot alerts must be on BEFORE automated security fixes, which depend on them.
	enable_toggle "$str_repo" "vulnerability-alerts" "Dependabot alerts"
	enable_toggle "$str_repo" "automated-security-fixes" "Dependabot security updates"
}

main "$@"
