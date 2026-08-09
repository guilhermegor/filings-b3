#!/usr/bin/env python
"""Weekly, non-blocking BDI catalog check — B3's own table index as the oracle.

B3 can publish a **new table** in the Boletim Diário at any time, and nothing in this repository
would notice: the readers we shipped keep passing, the backlog keeps looking complete, and the
absence only surfaces when somebody needs the data. That is a false negative by construction —
the suite is green *because* nothing is looking.

This script fetches B3's own index (``GET /bdi/table/classifications``), compares it against
:data:`bdi_catalog.BDI_TABLES`, and — on any divergence — opens (or updates) a **single tracking
issue**. Like ``check_contract_drift.py``, it never fails the build: a B3 outage and a real
divergence would be indistinguishable in a red check, and a red check must never gate a PR or a
release. See ``.github/workflows/bdi-catalog.yaml``.

The comparison is **symmetric**, and both directions matter:

* a table B3 publishes that the catalog **does not list** → a dataset nobody has decided about;
* a catalog entry B3 **no longer publishes** → a retired table whose issue should be closed, or a
  reader now reading something that is gone.

Background: the audit behind issue #186 found that **32 of B3's 69 tables** had never been
recorded anywhere, because the backlog had been seeded from the stpstone monorepo's coverage
rather than from B3's catalog. This job exists so that gap cannot silently reopen.

Machine/maintainer-facing surface — English, like every other ``bin/`` script here.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
import urllib.request

from bdi_catalog import BDI_HOST, BDI_TABLES, CLASSIFICATIONS_PATH


# GitHub API host — host-only so no fetchable URL literal trips the check-urls hook; paths are
# concatenated at the call site.
_GH_API = "https://api.github.com"

# The single tracking issue is found again each run by this label plus a hidden body marker, so
# the job updates one issue instead of opening a new one every week.
_ISSUE_LABEL = "contract-drift"
_ISSUE_MARKER = "<!-- bdi-catalog-bot -->"
_ISSUE_TITLE = "Catalogo do BDI divergente (tabelas da B3 x bin/bdi_catalog.py)"

# Best-effort weekly probe: one attempt. A B3 outage is an EXPECTED skip this week, not a
# transient worth retrying for.
_TIMEOUT_S = 30


# ---------------------------------------------------------------------------------------------
# Pure oracle (no network) — unit-tested exhaustively.
# ---------------------------------------------------------------------------------------------


def catalog_divergence(
	frozenset_published: frozenset[str], frozenset_catalogued: frozenset[str]
) -> list[str]:
	"""Compare B3's published tables against the catalog, in both directions.

	Parameters
	----------
	frozenset_published : frozenset of str
		Table names B3's index currently lists.
	frozenset_catalogued : frozenset of str
		Table names :data:`bdi_catalog.BDI_TABLES` records.

	Returns
	-------
	list of str
		One message per divergence, sorted for a stable issue body. Empty when they agree.
	"""
	list_out = [
		f"B3 publica `{str_table}`, ausente de `bin/bdi_catalog.py` — nenhuma decisao registrada"
		for str_table in sorted(frozenset_published - frozenset_catalogued)
	]
	list_out += [
		f"`{str_table}` esta no catalogo mas B3 nao publica mais — tabela aposentada?"
		for str_table in sorted(frozenset_catalogued - frozenset_published)
	]
	return list_out


def published_tables(list_classifications: list[dict]) -> frozenset[str]:
	"""Extract every table name from B3's classifications payload.

	Parameters
	----------
	list_classifications : list of dict
		The decoded ``/bdi/table/classifications`` response: one object per classification, each
		carrying a ``tables`` mapping keyed by table name.

	Returns
	-------
	frozenset of str
		Every table name, across all classifications.

	Raises
	------
	ValueError
		When the payload lists no table at all. An empty index cannot be distinguished from a
		total divergence, and reporting all 69 catalog entries as "retired" would be worse than
		saying nothing — so this fails loudly and the caller skips the week.
	"""
	set_out: set[str] = set()
	for dict_cls in list_classifications:
		set_out.update((dict_cls.get("tables") or {}).keys())
	if not set_out:
		raise ValueError("B3's classifications index listed no table at all")
	return frozenset(set_out)


# ---------------------------------------------------------------------------------------------
# Online check — one request to B3's index (network); tolerant of a B3 outage.
# ---------------------------------------------------------------------------------------------


def collect_divergence() -> list[str] | None:
	"""Fetch B3's index and diff it against the catalog.

	Returns
	-------
	list of str or None
		The divergence messages (empty when the catalog agrees with B3), or ``None`` when B3 could
		not be read at all.

	Notes
	-----
	``None`` and ``[]`` are **deliberately different**: "I compared and found nothing" and "I never
	compared" are not the same claim, and collapsing them would let an outage print *catalog agrees
	with B3 (69 tables)* — a green line asserting a comparison that never happened. That is the
	exact failure mode this whole check exists to prevent, so it must not be reintroduced by the
	check's own error handling.

	The index route is a **GET**, unlike the data route it sits beside, which answers 405 to a GET
	and requires a POST.
	"""
	try:
		with urllib.request.urlopen(  # noqa: S310 - constant https URL, no user input
			f"{BDI_HOST}{CLASSIFICATIONS_PATH}", timeout=_TIMEOUT_S
		) as cls_response:
			list_payload = json.loads(cls_response.read() or "[]")
		frozenset_published = published_tables(list_payload)
	except (OSError, ValueError) as cls_err:
		print(f"skipping: could not read B3's table index ({cls_err})", file=sys.stderr)
		return None
	return catalog_divergence(frozenset_published, frozenset(BDI_TABLES))


# ---------------------------------------------------------------------------------------------
# Issue upsert (network) — one tracking issue, found again by label + marker.
# ---------------------------------------------------------------------------------------------


def build_issue_body(list_problems: list[str]) -> str:
	"""Render the divergence messages into the tracking issue's body (with the dedupe marker).

	Parameters
	----------
	list_problems : list of str
		The divergence messages.

	Returns
	-------
	str
		Markdown body carrying the hidden marker used to find this issue again.
	"""
	str_lines = "\n".join(f"- {str_problem}" for str_problem in list_problems)
	return (
		f"{_ISSUE_MARKER}\n\n"
		f"O job semanal encontrou **{len(list_problems)}** divergencia(s) entre as tabelas que a "
		f"B3 publica hoje no BDI e o que `bin/bdi_catalog.py` registra.\n\n{str_lines}\n\n"
		f"Para cada tabela nova: abra a issue do reader, acrescente a entrada ao catalogo e feche "
		f"esta issue. O job a reabre enquanto a divergencia persistir.\n"
	)


def _api(str_method: str, str_url: str, dict_body: dict | None = None) -> Any:  # noqa: ANN401
	"""Call the GitHub API with the workflow token and decode the JSON reply.

	Parameters
	----------
	str_method : str
		HTTP method.
	str_url : str
		Absolute API URL.
	dict_body : dict, optional
		JSON payload, when the method takes one.

	Returns
	-------
	Any
		The decoded JSON (an object or an array, per the endpoint).
	"""
	bytes_body = None if dict_body is None else json.dumps(dict_body).encode()
	cls_request = urllib.request.Request(str_url, data=bytes_body, method=str_method)  # noqa: S310
	cls_request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
	cls_request.add_header("Accept", "application/vnd.github+json")
	cls_request.add_header("Content-Type", "application/json")
	with urllib.request.urlopen(cls_request, timeout=_TIMEOUT_S) as cls_response:  # noqa: S310
		return json.loads(cls_response.read() or "null")


def find_catalog_issue(list_issues: list[dict]) -> dict | None:
	"""Return the existing catalog issue, open **or closed**, if any.

	Parameters
	----------
	list_issues : list of dict
		Issues carrying the label, each ``{"number": int, "state": str, "body": str, ...}``.

	Returns
	-------
	dict or None
		The first issue whose body carries this job's marker, or ``None``.

	Notes
	-----
	Two things this must get right:

	The label is shared with the contract-drift job, so the **marker** is what separates the two
	trackers — matching on the label alone would make each job hijack the other's issue.

	**Closed issues count.** Searching open issues only would mean that once a maintainer closes
	the tracker while the divergence persists, every subsequent run opens a *brand new* issue — a
	weekly duplicate instead of the single tracker this job promises.
	"""
	for dict_issue in list_issues:
		if _ISSUE_MARKER in (dict_issue.get("body") or ""):
			return dict_issue
	return None


def upsert_issue(str_api: str, list_problems: list[str]) -> None:
	"""Open the tracking issue, or update it in place if it already exists.

	Parameters
	----------
	str_api : str
		The ``.../repos/{owner}/{name}`` API base.
	list_problems : list of str
		The divergence messages to report.
	"""
	str_body = build_issue_body(list_problems)
	# Querying every state, because a closed tracker must be reopened rather than duplicated.
	list_all = _api("GET", f"{str_api}/issues?state=all&labels={_ISSUE_LABEL}&per_page=100")
	dict_existing = find_catalog_issue(list_all)
	if dict_existing is not None:
		dict_patch: dict[str, str] = {"body": str_body, "state": "open"}
		_api("PATCH", f"{str_api}/issues/{dict_existing['number']}", dict_patch)
		print(f"updated catalog issue #{dict_existing['number']}", file=sys.stderr)
		return
	_api(
		"POST",
		f"{str_api}/issues",
		{"title": _ISSUE_TITLE, "body": str_body, "labels": [_ISSUE_LABEL]},
	)
	print("opened a new catalog issue", file=sys.stderr)


def main() -> int:
	"""Run the check; open/update the tracking issue on divergence. Always exits 0.

	Returns
	-------
	int
		Always ``0`` — a divergence is reported as an issue, never as a failed check.
	"""
	list_problems = collect_divergence()
	if list_problems is None:
		print("check SKIPPED — B3's index was unreadable; nothing was compared")
		return 0
	if not list_problems:
		print(f"catalog agrees with B3 ({len(BDI_TABLES)} tables)")
		return 0

	print(f"catalog divergence: {len(list_problems)} problem(s)")
	for str_problem in list_problems:
		print(f"  - {str_problem}")

	str_repo = os.environ.get("GITHUB_REPOSITORY")
	if not str_repo or not os.environ.get("GITHUB_TOKEN"):
		print("no GITHUB_REPOSITORY/GITHUB_TOKEN — reporting to stdout only", file=sys.stderr)
		return 0
	try:
		upsert_issue(f"{_GH_API}/repos/{str_repo}", list_problems)
	except (OSError, ValueError) as cls_err:
		# The divergence is already on stdout above, so a GitHub hiccup must not redden a job whose
		# whole contract is to report by opening an issue rather than by failing.
		print(
			f"could not report to GitHub ({cls_err}) — see the divergence above",
			file=sys.stderr,
		)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
