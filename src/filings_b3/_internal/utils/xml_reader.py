"""XML ingestion seam — a namespaced, nested XML into a typed, contract-validated DataFrame.

The XML counterpart of :mod:`tabular_reader`. B3's Pesquisa por Pregão instruments files arrive as
ISO-20022 (BVBG.028.02) XML: namespaced, one repeating *record* element per instrument, with
type-specific sub-blocks (an equity's ticker lives under ``EqtyInf``, a future's under
``FutrCtrctsInf``). :func:`read_xml` flattens that into rows given a **row anchor** (the repeating
element's local name) and, per output column, an ordered list of **alternative element paths** —
the first that resolves for a given record wins (the "ou" case B3's consolidated layout uses).
File-level scalars (e.g. the report date) are resolved once and broadcast to every row. An
optional **row filter** keeps only the records carrying a given block, so one heterogeneous file
can also be read as a per-type frame without giving up the record-level context around it.

Parsing goes through :mod:`defusedxml`, never bare :mod:`xml.etree`: the input is a **downloaded**
artifact — a trust boundary — and defusedxml neutralises the entity-expansion / external-entity
attacks that stdlib ElementTree does not defend against. Matching is **namespace-agnostic** (by
local name), so a B3 namespace-version bump does not silently break every path.

The document is **streamed**, not materialised: records are projected as they close and their
subtrees released immediately, so peak memory tracks the rows kept rather than the file's size
(#167). This matters because one 660 MB artifact is read up to eighteen ways — under the previous
whole-tree parse a two-row projection cost as much as the full file (~3.0 GB either way; now
~1.13 GB against ~1.86 GB). Two consequences shape the code below: a file-level scalar is resolved
from whichever element carries it **as that element closes**, and joins are applied only once the
stream is exhausted, since a stream cannot look ahead to a record it has not reached.

The contract + dtype tail is shared with :mod:`tabular_reader` (``find_contract_problems`` then
``apply_dtypes``), so an XML read and a tabular read cannot diverge in how they validate or type.
Bare ``pd.read_*`` / raw XML parsing is banned project-wide; this seam is the one exempt place for
XML, so every XML read funnels through a contract + dtype check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from xml.etree.ElementTree import Element  # noqa: S405 - typing only; parsing uses defusedxml

from defusedxml.ElementTree import iterparse
import pandas as pd

from filings_b3._internal.utils.dtypes import apply_dtypes
from filings_b3._internal.utils.tabular_reader import (
	ContractError,
	FileContract,
	find_contract_problems,
)
from filings_b3._internal.utils.typing import type_checker


@type_checker
def _local_name(str_tag: str) -> str:
	"""Return an element tag's local name, dropping any ``{namespace}`` prefix.

	Parameters
	----------
	str_tag : str
		A tag as ElementTree exposes it (``"{urn:…}TckrSymb"`` for a namespaced document).

	Returns
	-------
	str
		The bare local name (``"TckrSymb"``).
	"""
	return str_tag.rpartition("}")[2]


# A path segment may carry a 1-based repeat index — `StrtgyLegList[2]` is the SECOND sibling of
# that name. Regulatory XML repeats a container instead of numbering it (a strategy's legs, a
# bond's coupons), so without this a repeated block is unreachable past its first occurrence.
_RE_INDEXED = re.compile(r"^(?P<name>[^\[\]]+)\[(?P<index>\d+)\]$")


@type_checker
def _nth_child(cls_elem: Element, str_local: str, int_index: int) -> Element | None:
	"""Return the ``int_index``-th (1-based) direct child with the given local name, or ``None``.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The parent element to search under.
	str_local : str
		The child's local name (namespace-agnostic).
	int_index : int
		1-based position among the siblings sharing that name.

	Returns
	-------
	xml.etree.ElementTree.Element or None
		The matching child, or ``None`` when there are fewer than ``int_index`` of them.
	"""
	int_seen = 0
	for cls_child in cls_elem:
		if _local_name(cls_child.tag) != str_local:
			continue
		int_seen += 1
		if int_seen == int_index:
			return cls_child
	return None


@type_checker
def _segment_child(cls_elem: Element, str_seg: str) -> Element | None:
	"""Resolve one path segment — plain local name, or ``Name[n]`` for the n-th repeat.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The parent element to search under.
	str_seg : str
		A single path segment, optionally carrying a 1-based ``[n]`` repeat index.

	Returns
	-------
	xml.etree.ElementTree.Element or None
		The matching child, or ``None`` when absent.
	"""
	cls_match = _RE_INDEXED.match(str_seg)
	if cls_match is None:
		return _first_child(cls_elem, str_seg)
	return _nth_child(cls_elem, cls_match["name"], int(cls_match["index"]))


@type_checker
def _first_child(cls_elem: Element, str_local: str) -> Element | None:
	"""Return the first direct child of ``cls_elem`` whose local name matches, or ``None``.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The parent element to search under.
	str_local : str
		The child's local name (namespace-agnostic).

	Returns
	-------
	xml.etree.ElementTree.Element or None
		The first matching child, or ``None`` when absent.
	"""
	for cls_child in cls_elem:
		if _local_name(cls_child.tag) == str_local:
			return cls_child
	return None


@type_checker
def _resolve_text(cls_elem: Element, str_path: str) -> str | None:
	"""Resolve a ``/``-joined local-name path of direct children to its leaf text.

	A ``*`` segment is a **single-level wildcard**: it matches any direct child under which the
	remainder of the path resolves (first match wins). One ``InstrmInf/*/TckrSymb`` path therefore
	covers every instrument sub-block type without enumerating them — and a sub-block type B3 adds
	later is picked up automatically, since each record carries exactly one sub-block.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The element the path is relative to.
	str_path : str
		A path of local names joined by ``/`` (e.g. ``"InstrmInf/EqtyInf/TckrSymb"`` or
		``"InstrmInf/*/TckrSymb"``). A final ``@name`` segment reads an **attribute** rather
		than element text (``"ExrcPric/@Ccy"``) — ISO-20022 carries an amount's currency as an
		attribute of the amount, so a money column's unit is otherwise unrecoverable.

	Returns
	-------
	str or None
		The stripped leaf text, or ``None`` when any segment is missing or the leaf is empty.
	"""
	str_seg, _, str_rest = str_path.partition("/")
	if str_seg.startswith("@"):
		return (cls_elem.get(str_seg[1:]) or "").strip() or None
	if str_seg == "*":
		for cls_child in cls_elem:
			str_val = _resolve_text(cls_child, str_rest) if str_rest else _leaf_text(cls_child)
			if str_val is not None:
				return str_val
		return None
	cls_next = _segment_child(cls_elem, str_seg)
	if cls_next is None:
		return None
	return _resolve_text(cls_next, str_rest) if str_rest else _leaf_text(cls_next)


@type_checker
def _has_path(cls_elem: Element, str_path: str) -> bool:
	"""Return whether ``str_path`` resolves to an existing element under ``cls_elem``.

	The existence counterpart of :func:`_resolve_text`: it answers "does this record carry this
	block?" rather than "what text does it hold?". A block that exists but whose leaves are all
	empty still counts as present — the record *is* of that type, it merely reports no values.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The element the path is relative to.
	str_path : str
		A ``/``-joined path of local names; ``*`` is a single-level wildcard.

	Returns
	-------
	bool
		``True`` when the path resolves to an element.
	"""
	str_seg, _, str_rest = str_path.partition("/")
	if str_seg.startswith("@"):
		return str_seg[1:] in cls_elem.attrib
	if str_seg == "*":
		return any(not str_rest or _has_path(cls_child, str_rest) for cls_child in cls_elem)
	cls_next = _segment_child(cls_elem, str_seg)
	if cls_next is None:
		return False
	return _has_path(cls_next, str_rest) if str_rest else True


@type_checker
def _leaf_text(cls_elem: Element) -> str | None:
	"""Return an element's stripped text, or ``None`` when it is empty.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		The leaf element.

	Returns
	-------
	str or None
		The stripped text, or ``None`` when blank.
	"""
	str_text = (cls_elem.text or "").strip()
	return str_text or None


@type_checker
def _scalar_from_candidate(cls_elem: Element, str_path: str) -> str | None:
	"""Resolve a file-level scalar path against an element that matches its **first** segment.

	Unlike a row-relative path, a scalar's first segment need not be a direct child of the root
	(the report date sits several levels down), so the caller matches that first segment against
	**any** element in the document and this resolves the remainder as direct children from there.

	Splitting it this way is what lets scalars be resolved from a *stream*: the caller tests each
	element as it closes, rather than walking a fully materialised tree.

	Parameters
	----------
	cls_elem : xml.etree.ElementTree.Element
		An element whose local name equals ``str_path``'s first segment.
	str_path : str
		A ``/``-joined local-name path (e.g. ``"RptParams/RptDtAndTm/Dt"``).

	Returns
	-------
	str or None
		The stripped leaf text, or ``None`` when the remainder does not resolve.
	"""
	_, _, str_rest = str_path.partition("/")
	str_text = _resolve_text(cls_elem, str_rest) if str_rest else (cls_elem.text or "").strip()
	return str_text or None


@type_checker
def _check_declared_count(path_file: Path, str_declared: str | None, int_seen: int) -> None:
	"""Verify the record count the file declares against the records actually parsed.

	Parameters
	----------
	path_file : pathlib.Path
		The XML that was read, named in the error.
	str_declared : str or None
		The declared count as the document spelled it, or ``None`` when the path did not resolve.
	int_seen : int
		How many record elements the parse actually saw.

	Raises
	------
	ValueError
		When the file declares no count at the requested path, declares a non-integer, or
		declares a number the parse did not match.
	"""
	if str_declared is None:
		raise ValueError(f"{path_file.name}: no record count at the declared-count path")
	if not str_declared.isdigit():
		raise ValueError(
			f"{path_file.name}: declared record count {str_declared!r} is not a number"
		)
	if int(str_declared) != int_seen:
		raise ValueError(
			f"{path_file.name}: declares {str_declared} records but holds {int_seen} — "
			"the download is incomplete"
		)


@type_checker
def read_xml(
	path_file: Path,
	str_row_tag: str,
	dict_paths: Mapping[str, Sequence[str]],
	dict_dtypes: dict[str, str],
	cls_contract: FileContract,
	dict_scalars: Mapping[str, str] | None = None,
	list_date_cols: Sequence[str] | None = None,
	list_decimal_cols: Sequence[str] | None = None,
	str_row_filter: str | None = None,
	dict_joins: Mapping[str, tuple[str, str, str]] | None = None,
	str_declared_count_path: str | None = None,
) -> pd.DataFrame:
	"""Flatten a namespaced XML into a typed, contract-validated DataFrame.

	Each element whose local name equals ``str_row_tag`` becomes one row. For each output column,
	the alternative paths in ``dict_paths`` are tried in order and the first that resolves (as a
	path relative to the record) supplies the value; file-level scalars in ``dict_scalars`` resolve
	once against the root and broadcast to every row. The frame is read entirely as text, then the
	shared tail validates it against ``cls_contract`` (raising :class:`ContractError`) and coerces
	types via :func:`utils.dtypes.apply_dtypes` — never pandas' inference.

	Parameters
	----------
	path_file : pathlib.Path
		The XML file to read.
	str_row_tag : str
		Local name of the repeating record element (one row per occurrence).
	dict_paths : mapping of {str: sequence of str}
		Output column → ordered alternative ``/``-joined local-name paths, relative to a record.
		The first alternative that resolves wins; an unresolved column is ``None`` for that row.
		A final ``@name`` segment reads an attribute (``"ExrcPric/@Ccy"``).
	dict_dtypes : dict of {str: str}
		Column→dtype mapping enforced via :func:`utils.dtypes.apply_dtypes`.
	cls_contract : FileContract
		The contract the flattened frame must satisfy (required columns must be mapped).
	dict_scalars : mapping of {str: str}, optional
		File-level columns → a single path resolved once against the root, broadcast to all rows.
	list_date_cols : sequence of str, optional
		Columns coerced to ``datetime.date``.
	list_decimal_cols : sequence of str, optional
		Columns coerced to exact :class:`decimal.Decimal` — money and any value whose fractional
		part carries meaning, never a binary float.
	str_row_filter : str, optional
		A record-relative path that a record must **carry** to become a row; records where it
		does not resolve are skipped. This is how one heterogeneous file yields a per-type
		frame: B3's instruments file nests each record's fields under exactly one of 20
		``InstrmInf`` sub-blocks, so ``"InstrmInf/ADRInf"`` keeps the ADR records alone while
		the row anchor stays on the full record — preserving the per-record report date and
		common attributes that live *outside* the sub-block. ``None`` (default) keeps every
		record. Filtering happens **before** contract validation, so a column required for this
		type is not judged against records of another type.
	dict_joins : mapping of {str: tuple of (str, str, str)}, optional
		**Self-join within the document**: column → ``(fk_path, pk_path, value_path)``. A record
		that references another record carries only an opaque identifier, while the useful value
		(a ticker) lives on the referenced record. Each record contributes
		``pk_path → value_path`` to a lookup table; the column is then ``fk_path``'s value
		translated through it, or ``None`` when the reference does not resolve. The lookup spans
		**every** record in the file, not only the filtered rows, so a filtered per-type read can
		still resolve references into types it excluded. Joining happens after all rows are read
		and **before** contract validation and typing.
	str_declared_count_path : str, optional
		Path to a **record count the file declares about itself** — resolved like a scalar, but
		never becoming a column, because it is a claim about the artifact rather than data. When
		given, the parse counts record elements **before** ``str_row_filter`` and raises if the
		two disagree. This is the only cheap defence against a **truncated download**, which is
		invisible by construction: the parser reads the bytes that arrived, the XML is well-formed
		up to the cut, and a smaller frame comes back with no error at all. The seam never learns
		what the count is *called* — the caller passes the path, so a format that declares nothing
		simply omits the argument and a format that declares it elsewhere passes its own path,
		instead of this seam growing a branch per source. (B3's BVBG.028 declares
		``BizGrpDtls/TtlNbOfMsg``.) ``None`` (default) verifies nothing.

	Returns
	-------
	pd.DataFrame
		The flattened rows with the declared types applied.

	Raises
	------
	ContractError
		When the flattened frame violates ``cls_contract``.
	ValueError
		When ``str_declared_count_path`` is given and the file declares no count there, declares a
		non-numeric one, or declares a number the parse did not match.
	"""
	# Lookup tables for the self-joins, keyed by primary-key path and value path together, so that
	# joins sharing a target build it once. Populated from EVERY record, including filtered rows.
	dict_lookups: dict[tuple[str, str], dict[str, str]] = {
		(str_pk, str_value): {} for _, str_pk, str_value in (dict_joins or {}).values()
	}

	# A scalar's first segment names the element it is resolved from; matching it as that element
	# CLOSES is what lets a scalar be read from a stream. First match wins, as before.
	dict_scalar_heads = {
		str_col: str_path.partition("/")[0] for str_col, str_path in (dict_scalars or {}).items()
	}
	dict_scalar_vals: dict[str, str | None] = dict.fromkeys(dict_scalars or {})

	# The declared count is resolved with the same "match the head element as it closes" trick as a
	# scalar, yet stays out of the frame, since it describes the artifact rather than the rows.
	str_count_head = (
		str_declared_count_path.partition("/")[0] if str_declared_count_path is not None else None
	)
	str_declared_count: str | None = None
	int_records_seen = 0

	list_rows: list[dict[str, str | None]] = []
	for _, cls_elem in iterparse(str(path_file), events=("end",)):
		str_local = _local_name(cls_elem.tag)

		for str_col, str_head in dict_scalar_heads.items():
			if dict_scalar_vals[str_col] is None and str_local == str_head:
				dict_scalar_vals[str_col] = _scalar_from_candidate(
					cls_elem, (dict_scalars or {})[str_col]
				)

		if (
			str_declared_count_path is not None
			and str_declared_count is None
			and (str_local == str_count_head)
		):
			str_declared_count = _scalar_from_candidate(cls_elem, str_declared_count_path)

		if str_local != str_row_tag:
			continue

		# Counted before the row filter, because the declaration describes the whole file — a
		# per-subtype read must compare against every record present, not the few it keeps.
		int_records_seen += 1

		for (str_pk, str_value), dict_lookup in dict_lookups.items():
			str_key = _resolve_text(cls_elem, str_pk)
			str_val = _resolve_text(cls_elem, str_value)
			if str_key is not None and str_val is not None:
				dict_lookup[str_key] = str_val
		if str_row_filter is None or _has_path(cls_elem, str_row_filter):
			dict_row: dict[str, str | None] = {}
			for str_col, seq_paths in dict_paths.items():
				dict_row[str_col] = next(
					(
						str_val
						for str_path in seq_paths
						if (str_val := _resolve_text(cls_elem, str_path)) is not None
					),
					None,
				)
			# Store the raw foreign key; it is translated below, once every record has been seen.
			for str_col, (str_fk, _, _) in (dict_joins or {}).items():
				dict_row[str_col] = _resolve_text(cls_elem, str_fk)
			list_rows.append(dict_row)

		# Release the record's subtree now that it has been projected — this is what keeps memory
		# flat. What stays behind is one empty element per record, bytes rather than the gigabytes
		# a fully materialised tree cost, plus the non-record elements scalars are read from.
		cls_elem.clear()

	# Checked before anything is projected or validated, because a truncated file's rows are each
	# individually valid — every later gate would pass on data that is merely missing its tail.
	if str_declared_count_path is not None:
		_check_declared_count(path_file, str_declared_count, int_records_seen)

	# Scalars and joins are applied here, not while building each row, because either may only
	# resolve after some rows have already been emitted — a stream cannot look ahead.
	for dict_row in list_rows:
		dict_row.update(dict_scalar_vals)
		for str_col, (_, str_pk, str_value) in (dict_joins or {}).items():
			str_key = dict_row[str_col]
			dict_row[str_col] = (
				dict_lookups[(str_pk, str_value)].get(str_key) if str_key is not None else None
			)

	list_cols = list(dict_scalars or {}) + list(dict_paths) + list(dict_joins or {})
	df_raw = pd.DataFrame(list_rows, columns=list_cols, dtype="object")

	list_problems = find_contract_problems(df_raw, cls_contract)
	if list_problems:
		raise ContractError(list_problems)
	return apply_dtypes(
		df_raw,
		dict_dtypes=dict_dtypes,
		list_date_cols=list_date_cols,
		list_decimal_cols=list_decimal_cols,
	)
