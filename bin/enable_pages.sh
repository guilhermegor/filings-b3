#!/usr/bin/env bash
# Enable GitHub Pages for this repo — once, with the source matching the project's docs model.
#
# WHY THIS EXISTS: a workflow's GITHUB_TOKEN is a GitHub App installation token that CANNOT
# create a Pages site or change its source ("Resource not accessible by integration"). That
# needs repo-admin rights, which a maintainer running `make init` has (via `gh auth`) but CI
# does not. This script makes that one-time API call.
#
# TWO MODELS, auto-detected from mkdocs.yml:
#   * mike (versioned docs)  — mkdocs.yml declares `provider: mike`. Docs are deployed to the
#     `gh-pages` BRANCH by the release workflow, so Pages must serve "from a branch → gh-pages".
#     Guarded: the source is flipped ONLY once the gh-pages branch exists (the first `mike deploy`
#     creates it) — until then Pages is left untouched so the live site never points at an empty
#     branch. A mike scaffold and an Actions-artifact scaffold are mutually exclusive Pages models.
#   * Actions (flat site)    — no mike. The docs.yaml workflow deploys via actions/deploy-pages,
#     so Pages source = "GitHub Actions" (build_type=workflow).
#
# Idempotent + non-blocking: already-correct → no-op; gh absent / unauthenticated / not repo-admin
# (a fork/contributor) → WARN and return 0 so `init` still completes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# mkdocs.yml sits at the project root, one level up from bin/.
MKDOCS_YML="$SCRIPT_DIR/../mkdocs.yml"
PAGES_BRANCH="gh-pages"

require_gh() {
	# gh must be installed and authenticated. Missing either is a skip, not a failure.
	if ! command -v gh >/dev/null 2>&1; then
		print_status "warning" "gh CLI not found — skipping Pages enablement (enable once in Settings → Pages)"
		return 1
	fi
	if ! gh auth status >/dev/null 2>&1; then
		print_status "warning" "gh not authenticated — skipping Pages enablement (run 'gh auth login', then 'make enable_pages')"
		return 1
	fi
	return 0
}

resolve_repo() {
	# Print owner/repo for the current checkout, or empty when no GitHub remote resolves.
	gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true
}

uses_mike() {
	# True when the docs use mike (versioned model). Matches `provider: mike` under extra.version.
	[ -f "$MKDOCS_YML" ] && grep -Eq '^[[:space:]]*provider:[[:space:]]*mike[[:space:]]*$' "$MKDOCS_YML"
}

remote_branch_exists() {
	# True when the named branch exists on the GitHub remote.
	local str_repo="$1" str_branch="$2"
	gh api "repos/$str_repo/branches/$str_branch" >/dev/null 2>&1
}

set_pages_source() {
	# Create (POST) or update (PUT) the Pages source for the current model. $1 = owner/repo.
	local str_repo="$1"
	local str_method="POST"
	gh api "repos/$str_repo/pages" >/dev/null 2>&1 && str_method="PUT"

	if uses_mike; then
		# Versioned (mike) model: serve from the gh-pages branch — but only once it exists.
		if ! remote_branch_exists "$str_repo" "$PAGES_BRANCH"; then
			print_status "info" "No '$PAGES_BRANCH' branch yet — leaving Pages untouched (the first 'mike deploy' in the release workflow creates it, then re-run 'make enable_pages')"
			return 0
		fi
		print_status "info" "Setting GitHub Pages source to branch '$PAGES_BRANCH' for $str_repo (mike versioned docs)..."
		if printf '{"source":{"branch":"%s","path":"/"}}' "$PAGES_BRANCH" |
			gh api -X "$str_method" "repos/$str_repo/pages" --input - >/dev/null 2>&1; then
			print_status "success" "GitHub Pages now serves the versioned docs from '$PAGES_BRANCH'"
			return 0
		fi
	else
		# Flat (Actions) model: the docs.yaml workflow deploys the artifact.
		print_status "info" "Enabling GitHub Pages (source = GitHub Actions) for $str_repo..."
		if gh api -X "$str_method" "repos/$str_repo/pages" -f build_type=workflow >/dev/null 2>&1; then
			print_status "success" "GitHub Pages enabled — the docs deploy workflow can now publish"
			return 0
		fi
	fi

	# Most common cause: the caller is not a repo admin (a fork/contributor). Non-fatal.
	print_status "warning" "Could not set Pages source for $str_repo (needs repo-admin rights) — a maintainer must run 'make enable_pages' or set it in Settings → Pages"
	return 0
}

enable_pages() {
	local str_repo
	str_repo="$(resolve_repo)"
	if [ -z "$str_repo" ]; then
		print_status "warning" "No GitHub remote resolved — skipping Pages enablement (push the repo to GitHub first)"
		return 0
	fi
	set_pages_source "$str_repo"
}

main() {
	print_status "section" "GitHub Pages Enablement"
	# A skip (no gh / not authed) must not fail init — return 0 either way.
	if ! require_gh; then
		return 0
	fi
	enable_pages
}

main "$@"
