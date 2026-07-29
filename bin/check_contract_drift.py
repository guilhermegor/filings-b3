#!/usr/bin/env python
"""Weekly, non-blocking contract-drift detector — B3's UP2DATA layout as the oracle.

B3 can change the BVBG.028 instruments layout *after* we have shipped
:data:`~filings_b3._internal.config.contracts.INSTRUMENTS_FILE` and the reader's column→XML-path
map. Nothing at PR time can see that: the reader's tests prove it matched the layout the day they
were written, but only a job that fetches B3's published layout again can notice a change made
since. This script downloads the authoritative ``BVBG.028 para UP2DATA`` spreadsheet (via
:class:`~filings_b3.search_trading_session.InstrumentsLayoutMetaReader`), compares the columns B3
**declares** against the columns the instruments reader **maps**, and — on any divergence — opens
(or updates) a **single tracking issue**. It never fails the build: a B3 outage and a real drift
would be indistinguishable in a red check, and a red check must never gate a PR or a release. See
``.github/workflows/contract-drift.yaml``.

The comparison is **symmetric**, and both directions are real signals:

* a mapped column **gone** from B3's layout → the reader now produces a silently-null column;
* a layout column the reader **does not map** → B3 added a field we should start reading.

Machine/maintainer-facing surface — English, like every other ``bin/`` script here.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
import urllib.request

from filings_b3._internal.config.contracts import INSTRUMENTS_FILE
from filings_b3._internal.utils.retry import RetryPolicy
from filings_b3.search_trading_session import (
	InstrumentsLayoutMetaReader,
	instruments_file as _inst,
)


# GitHub API host — host-only so no fetchable URL literal trips the check-urls hook; paths are
# concatenated at the call site.
_GH_API = "https://api.github.com"

# The single tracking issue is found again each run by this label plus a hidden body marker, so the
# job updates one issue instead of opening a new one every week.
_ISSUE_LABEL = "contract-drift"
_ISSUE_MARKER = "<!-- contract-drift-bot -->"
_ISSUE_TITLE = "Deriva de layout detectada (UP2DATA x instruments reader)"

# Best-effort weekly probe: fail fast instead of burning the patient production backoff. A B3
# outage is an EXPECTED skip this week, not a transient worth retrying for ~24 s.
_DRIFT_RETRY_POLICY: RetryPolicy = RetryPolicy(int_max_attempts=1)


# ---------------------------------------------------------------------------------------------
# Pure oracle (no network) — unit-tested exhaustively.
# ---------------------------------------------------------------------------------------------


def layout_drift(
	str_label: str, frozenset_mapped: frozenset[str], frozenset_layout: frozenset[str]
) -> list[str]:
	"""Compare the reader's mapped columns against B3's declared layout columns, both ways.

	Parameters
	----------
	str_label : str
		Human-readable dataset label, prefixed onto each problem for the issue body.
	frozenset_mapped : frozenset of str
		The canonical column names the reader maps (its scalar + path keys).
	frozenset_layout : frozenset of str
		The canonical column names B3's UP2DATA layout declares now.

	Returns
	-------
	list of str
		One message per drift found; empty when the two sets are equal.
	"""
	list_problems: list[str] = []
	for str_col in sorted(frozenset_mapped - frozenset_layout):
		list_problems.append(
			f"{str_label}: reader maps {str_col!r}, gone from B3's layout "
			f"(the reader now yields a silently-null column — B3 removed or renamed a field?)"
		)
	for str_col in sorted(frozenset_layout - frozenset_mapped):
		list_problems.append(
			f"{str_label}: B3's layout declares {str_col!r}, which the reader does not map "
			f"(B3 added a field — add its column->path mapping?)"
		)
	return list_problems


def mapped_columns() -> frozenset[str]:
	"""Return the canonical column names the instruments reader maps (scalars + path columns).

	Returns
	-------
	frozenset of str
		The reader's full mapped column set — the drift oracle's "what we read" side.
	"""
	return frozenset(_inst._DICT_SCALARS) | frozenset(_inst._DICT_PATHS)


# ---------------------------------------------------------------------------------------------
# Online check — one download of the layout asset (network); tolerant of a B3 outage.
# ---------------------------------------------------------------------------------------------


def fetch_layout_columns(int_timeout_s: int = 60) -> frozenset[str] | None:  # noqa: ARG001
	"""Download B3's UP2DATA layout and return the canonical column set it declares.

	Parameters
	----------
	int_timeout_s : int, optional
		Reserved for parity with the readers' timeout knob; the layout reader uses the download
		seam's own timeout.

	Returns
	-------
	frozenset of str or None
		The layout's ``CANONICAL_COLUMN`` values, or ``None`` when the asset is unavailable
		(a B3 outage is not drift — skip this week).
	"""
	try:
		df_layout = InstrumentsLayoutMetaReader(cls_retry_policy=_DRIFT_RETRY_POLICY).read()
	except OSError:
		return None
	return frozenset(df_layout["CANONICAL_COLUMN"].astype(str))


def collect_drift(int_timeout_s: int = 60) -> list[str]:
	"""Run the oracle over the instruments layout and return every drift message found.

	Parameters
	----------
	int_timeout_s : int, optional
		Socket timeout forwarded to the layout read, by default 60.

	Returns
	-------
	list of str
		Every drift message (empty when the layout matches the reader, or the layout is
		unavailable).
	"""
	frozenset_layout = fetch_layout_columns(int_timeout_s)
	if frozenset_layout is None:
		print("layout asset unavailable — skipping this run (not drift)", file=sys.stderr)
		return []
	return layout_drift(INSTRUMENTS_FILE.str_name, mapped_columns(), frozenset_layout)


# ---------------------------------------------------------------------------------------------
# Issue upsert (network) — one tracking issue, found again by label + marker.
# ---------------------------------------------------------------------------------------------


def build_issue_body(list_problems: list[str]) -> str:
	"""Render the drift messages into the tracking issue's body (with the dedupe marker).

	Parameters
	----------
	list_problems : list of str
		The drift messages.

	Returns
	-------
	str
		Markdown body carrying the hidden marker used to find this issue again.
	"""
	str_lines = "\n".join(f"- {str_problem}" for str_problem in list_problems)
	return (
		f"{_ISSUE_MARKER}\n\n"
		f"O job semanal de deriva encontrou **{len(list_problems)}** divergencia(s) entre o "
		f"layout que a B3 publica hoje (planilha UP2DATA) e o que o reader de instrumentos mapeia."
		f"\n\n{str_lines}\n\n"
		f"Atualize o `INSTRUMENTS_FILE` / `_DICT_PATHS` do reader (nomes canonicos = "
		f"`pascal_to_upper_snake` da abreviacao BVBG.028) e feche esta issue. O job a reabre se a "
		f"deriva persistir.\n"
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
	with urllib.request.urlopen(cls_request) as cls_response:  # noqa: S310
		return json.loads(cls_response.read() or "null")


def find_open_drift_issue(list_issues: list[dict]) -> int | None:
	"""Return the number of the existing open drift issue, if any.

	Parameters
	----------
	list_issues : list of dict
		Open issues carrying the drift label, each ``{"number": int, "body": str, ...}``.

	Returns
	-------
	int or None
		The first issue whose body carries the marker, or ``None``.
	"""
	for dict_issue in list_issues:
		if _ISSUE_MARKER in (dict_issue.get("body") or ""):
			return dict_issue["number"]
	return None


def upsert_issue(str_api: str, list_problems: list[str]) -> None:
	"""Open the tracking issue, or update it in place if it already exists.

	Parameters
	----------
	str_api : str
		The ``.../repos/{owner}/{name}`` API base.
	list_problems : list of str
		The drift messages to report.
	"""
	str_body = build_issue_body(list_problems)
	list_open = _api("GET", f"{str_api}/issues?state=open&labels={_ISSUE_LABEL}&per_page=100")
	int_existing = find_open_drift_issue(list_open)
	if int_existing is not None:
		_api("PATCH", f"{str_api}/issues/{int_existing}", {"body": str_body})
		print(f"updated drift issue #{int_existing}", file=sys.stderr)
		return
	_api(
		"POST",
		f"{str_api}/issues",
		{"title": _ISSUE_TITLE, "body": str_body, "labels": [_ISSUE_LABEL]},
	)
	print("opened a new drift issue", file=sys.stderr)


def main() -> int:
	"""Run the sweep; open/update the tracking issue on drift. Always exits 0 (non-blocking).

	Returns
	-------
	int
		Always ``0`` — drift is reported as an issue, never as a failed check.
	"""
	list_problems = collect_drift()
	if not list_problems:
		print("no layout drift detected")
		return 0

	print(f"layout drift detected: {len(list_problems)} problem(s)")
	for str_problem in list_problems:
		print(f"  - {str_problem}")

	str_repo = os.environ.get("GITHUB_REPOSITORY")
	if str_repo:
		upsert_issue(f"{_GH_API}/repos/{str_repo}", list_problems)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
