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

The contract + dtype tail is shared with :mod:`tabular_reader` (``find_contract_problems`` then
``apply_dtypes``), so an XML read and a tabular read cannot diverge in how they validate or type.
Bare ``pd.read_*`` / raw XML parsing is banned project-wide; this seam is the one exempt place for
XML, so every XML read funnels through a contract + dtype check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from xml.etree.ElementTree import Element  # noqa: S405 - typing only; parsing uses defusedxml

from defusedxml.ElementTree import parse as parse_xml
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
	cls_next = _first_child(cls_elem, str_seg)
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
	cls_next = _first_child(cls_elem, str_seg)
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
def _resolve_scalar(cls_root: Element, str_path: str) -> str | None:
	"""Resolve a file-level scalar path anywhere in the tree (first match wins).

	Unlike a row-relative path, a scalar's first segment need not be a direct child of the root
	(the report date sits several levels down), so the first segment is matched against **any**
	descendant and the remainder walked as direct children from there.

	Parameters
	----------
	cls_root : xml.etree.ElementTree.Element
		The document root.
	str_path : str
		A ``/``-joined local-name path (e.g. ``"RptParams/RptDtAndTm/Dt"``).

	Returns
	-------
	str or None
		The stripped leaf text of the first resolving match, or ``None``.
	"""
	list_seg = str_path.split("/")
	str_rest = "/".join(list_seg[1:])
	for cls_elem in cls_root.iter():
		if _local_name(cls_elem.tag) != list_seg[0]:
			continue
		str_text = _resolve_text(cls_elem, str_rest) if str_rest else (cls_elem.text or "").strip()
		if str_text:
			return str_text
	return None


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

	Returns
	-------
	pd.DataFrame
		The flattened rows with the declared types applied.

	Raises
	------
	ContractError
		When the flattened frame violates ``cls_contract``.
	"""
	cls_root = parse_xml(str(path_file)).getroot()

	dict_scalar_vals = {
		str_col: _resolve_scalar(cls_root, str_path)
		for str_col, str_path in (dict_scalars or {}).items()
	}

	list_rows: list[dict[str, str | None]] = []
	for cls_rec in cls_root.iter():
		if _local_name(cls_rec.tag) != str_row_tag:
			continue
		if str_row_filter is not None and not _has_path(cls_rec, str_row_filter):
			continue
		dict_row: dict[str, str | None] = dict(dict_scalar_vals)
		for str_col, seq_paths in dict_paths.items():
			dict_row[str_col] = next(
				(
					str_val
					for str_path in seq_paths
					if (str_val := _resolve_text(cls_rec, str_path)) is not None
				),
				None,
			)
		list_rows.append(dict_row)

	list_cols = list(dict_scalars or {}) + list(dict_paths)
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
