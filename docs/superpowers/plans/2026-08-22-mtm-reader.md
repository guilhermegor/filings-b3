# MTM Reader (`filings-b3#80`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `MaximumTheoreticalMarginReader` to `filings_b3.search_trading_session` that turns B3's daily `MT{yymmdd}.zip` into a typed, contract-validated, provenance-stamped DataFrame with one row per `(instrument, holdingDay)`.

**Architecture:** The MTM file is **hierarchical** — interleaved `INSTRUMENT` and `MTM` records — while `_BasePregaoReader`'s lifecycle ends in `read_table()`, which reads flat tabular files. Rather than bypass the base (losing download-with-retry, raw-artifact retention, contract enforcement, dtype coercion and provenance stamping), this reader overrides the one seam that already exists for compound sources: `locate_table()`. It extracts the ZIP member and **flattens** it into a derived flat CSV, returning that path. The base then runs unchanged.

Three properties make this correct rather than a hack:

1. `hash_artifact(path_download)` hashes the **original** download, so provenance stays bound to the real artifact, not the derived one.
2. `path_raw` retains the **original** ZIP as bronze; the derived CSV is written to a separate temporary directory and never pollutes the datalake.
3. Writing the derived CSV ourselves means we control its encoding (UTF-8, matching `read_table`'s `utf-8-sig` default) and its decimal separator — so no change to `_BasePregaoReader` is needed at all.

**Tech Stack:** Python 3.12, pandas, stdlib `csv`, existing `_internal` seams (`http_downloader`, `zip_extractor`, `raw_workspace`, `tabular_reader`, `provenance`, `dtypes`).

**Spec:** `~/.claude/specs/2026-08-22-tradesessions-api-amendment.md` §13 (layout, semantics, verified volumes), amending `~/.claude/specs/2026-07-31-marketdata-fm-architecture-design.md`.

**Issue:** `filings-b3#80` — *feat: migrate b3_maximum_theoretical_margin B3 dataset into filings-b3*. Source to dehydrate: `~/github/stpstone/src/stpstone/ingestion/countries/br/exchange/b3_maximum_theoretical_margin.py` (class `B3MaximumTheoreticalMargin`).

## Global Constraints

- **Indentation is TABS**, not spaces. Every file in `src/filings_b3/` uses tabs.
- **`from __future__ import annotations`** at the top of every module.
- **Numpydoc docstrings** on every public module, class, function, and method.
- **Naming prefixes** are mandatory and match the surrounding code: `str_`, `list_`, `dict_`, `tuple_`, `path_`, `cls_`, `df_`, `int_`, `bool_`. Module-level private constants are `_UPPER_SNAKE`.
- **Money and any value whose fractional part carries meaning is `Decimal`, never `float`.** `_internal.utils.dtypes._to_decimal` **rejects** a `float` input by design and calls `Decimal(str_value)` on text — so `"44,3"` raises `decimal.InvalidOperation`. Comma decimals MUST be normalised to `.` **as text**, never through `float()`.
- **Readers perform no persistence.** `read()` returns a DataFrame.
- **Every reader accepts `path_raw: Path | None = None`** and keeps the untouched raw artifact there when set.
- **Public only from the section path:** `from filings_b3.search_trading_session import MaximumTheoreticalMarginReader`. The package root exports no readers (issue #163).
- **Conventional Commits**, atomic, one logical change per commit.

## Verified Source Facts

Confirmed against the real trading session of **2026-08-21** and against B3's current layout spreadsheet `MargemteoricaMaxima-Atualizado2.xlsx`.

⚠️ The `.zip` files published as *"Layout Mercado de Derivativos — Margem Teórica Máxima para Ativos Líquidos"* (2005 and 2017 editions) describe a **legacy, different** product: a flat 6-field record per `(date, market, commodity, series, C/V)` with a single margin value and **no `holdingDay`**. Same name, different file. Do not use them.

File: `MT{yymmdd}.zip` → member `MaximumTheoreticalMargin.csv`. Delimiter `;`, decimal separator **comma**, one trailing empty field on `MTM` rows.

```
2026-08-21;maximumTheoreticalMargin;1          <- header:  date; file id; version
INSTRUMENT;200002981938;8;BVMF;44,3;PETR4      <- 6 fields, always
MTM;1;;;0;0;                                   <- 7 fields, always (7th empty)
MTM;2;;;31,01;31,01;
...
MTM;10;;;19,935;19,935;
INSTRUMENT;200002981940;8;BVMF;7,45;BPACA494
MTM;1;0;0;;;
MTM;2;0;-32,7955;;;
```

| Record | Pos | Field | Notes |
|---|---|---|---|
| header | 1 | Date | `AAAA-MM-DD` |
| | 2 | File id | fixed `maximumTheoreticalMargin` |
| | 3 | Version | |
| `INSTRUMENT` | 2 | Instrument identification | |
| | 3 | Instrument origin | `4`=ISIN, `8`=Symbol, `H`=Clearinghouse |
| | 4 | Clearinghouse id | fixed `BVMF` |
| | 5 | **Reference price** | numeric 11.7 |
| | 6 | Trading code | |
| `MTM` | 2 | **holdingDay** | numeric 2 |
| | 3 | Max theoretical margin — **bought** — phi1 | numeric 14.4 |
| | 4 | Max theoretical margin — **sold** — phi1 | numeric 14.4 |
| | 5 | Min margin credit (**collateral**) — phi1 | numeric 14.4 |
| | 6 | Min margin credit (**collateral**) — phi2 | numeric 14.4 |

**Volume:** 145,090 `INSTRUMENT` blocks × exactly 10 `holdingDay` = 1,450,900 `MTM` rows; 1,595,992 lines per day. The flattener **must stream** — never read the whole file into memory.

**Fill pattern follows instrument class, not buy/sell** (this is why the file looks "messy"): bought/sold only = 143,216 (options and futures — they have positions, they are not accepted as collateral); collateral only = 733 (`NTN-B`, `DBR …`, `BRL`, `ITUB4 BZ` — they are collateral, not positions); both = 1,141 (BDRs, ETFs, shares). **Margin values can be negative** (`BPACA494`: bought `0`, sold `-32,7955`). Empty fields are legitimate and must stay empty, never become `0`.

---

### Task 1: MTM flattener

The pure function that turns the interleaved record stream into flat rows. Streaming, no pandas, no network — the piece worth reviewing on its own.

**Files:**
- Create: `src/filings_b3/search_trading_session/_mtm_flattener.py`
- Test: `tests/unit/test_mtm_flattener.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `flatten_mtm(path_src: Path, path_dest: Path) -> Path` — reads the raw MTM CSV at `path_src`, writes a flat `;`-delimited UTF-8 CSV to `path_dest`, returns `path_dest`.
  - `MTM_COLUMNS: tuple[str, ...]` — the flat header, in order.
  - `MtmFormatError(ValueError)` — raised on a malformed record stream.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_mtm_flattener.py`:

```python
"""Unit tests for the MTM flattener."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from filings_b3.search_trading_session._mtm_flattener import (
	MTM_COLUMNS,
	MtmFormatError,
	flatten_mtm,
)


SAMPLE = (
	"2026-08-21;maximumTheoreticalMargin;1\n"
	"INSTRUMENT;200002981938;8;BVMF;44,3;PETR4\n"
	"MTM;1;;;0;0;\n"
	"MTM;2;;;31,01;31,01;\n"
	"INSTRUMENT;200002981940;8;BVMF;7,45;BPACA494\n"
	"MTM;1;0;0;;;\n"
	"MTM;2;0;-32,7955;;;\n"
)


def _write(path_dir: Path, str_content: str) -> Path:
	path_src = path_dir / "MaximumTheoreticalMargin.csv"
	path_src.write_text(str_content, encoding="latin-1")
	return path_src


def _rows(path_csv: Path) -> list[dict[str, str]]:
	with path_csv.open(encoding="utf-8", newline="") as file_out:
		return list(csv.DictReader(file_out, delimiter=";"))


def test_flatten_emits_one_row_per_instrument_holding_day(tmp_path: Path) -> None:
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	list_rows = _rows(path_out)
	assert len(list_rows) == 4


def test_flatten_header_matches_declared_columns(tmp_path: Path) -> None:
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	with path_out.open(encoding="utf-8") as file_out:
		str_header = file_out.readline().strip()
	assert str_header == ";".join(MTM_COLUMNS)


def test_flatten_propagates_instrument_block_and_report_date(tmp_path: Path) -> None:
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	dict_row = _rows(path_out)[1]
	assert dict_row["RPT_DT"] == "2026-08-21"
	assert dict_row["INSTRM_ID"] == "200002981938"
	assert dict_row["INSTRM_SRC"] == "8"
	assert dict_row["CLRG_HOUSE_ID"] == "BVMF"
	assert dict_row["TCKR_SYMB"] == "PETR4"
	assert dict_row["HLDG_DAY"] == "2"


def test_flatten_normalises_comma_decimals_to_dot(tmp_path: Path) -> None:
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	dict_row = _rows(path_out)[1]
	assert dict_row["REF_PRIC"] == "44.3"
	assert dict_row["MIN_MRGN_CRDT_COLTRL_PHI1"] == "31.01"


def test_flatten_preserves_negative_values(tmp_path: Path) -> None:
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	dict_row = _rows(path_out)[3]
	assert dict_row["MAX_THEOR_MRGN_SELL_PHI1"] == "-32.7955"


def test_flatten_keeps_empty_fields_empty(tmp_path: Path) -> None:
	"""An absent margin is absent, never zero — the fill pattern encodes instrument class."""
	path_out = flatten_mtm(_write(tmp_path, SAMPLE), tmp_path / "flat.csv")
	dict_row = _rows(path_out)[1]
	assert dict_row["MAX_THEOR_MRGN_BUY_PHI1"] == ""
	assert dict_row["MAX_THEOR_MRGN_SELL_PHI1"] == ""
	dict_collateral_absent = _rows(path_out)[3]
	assert dict_collateral_absent["MIN_MRGN_CRDT_COLTRL_PHI1"] == ""


def test_flatten_rejects_mtm_before_any_instrument(tmp_path: Path) -> None:
	str_bad = "2026-08-21;maximumTheoreticalMargin;1\nMTM;1;;;0;0;\n"
	with pytest.raises(MtmFormatError, match="MTM record before any INSTRUMENT"):
		flatten_mtm(_write(tmp_path, str_bad), tmp_path / "flat.csv")


def test_flatten_rejects_unexpected_header(tmp_path: Path) -> None:
	str_bad = "2026-08-21;somethingElse;1\nINSTRUMENT;1;8;BVMF;1,0;X\n"
	with pytest.raises(MtmFormatError, match="unexpected file id"):
		flatten_mtm(_write(tmp_path, str_bad), tmp_path / "flat.csv")


def test_flatten_rejects_unknown_record_type(tmp_path: Path) -> None:
	str_bad = "2026-08-21;maximumTheoreticalMargin;1\nWIDGET;1;2\n"
	with pytest.raises(MtmFormatError, match="unknown record type 'WIDGET'"):
		flatten_mtm(_write(tmp_path, str_bad), tmp_path / "flat.csv")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy python -m pytest tests/unit/test_mtm_flattener.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'filings_b3.search_trading_session._mtm_flattener'`

- [ ] **Step 3: Write the implementation**

Create `src/filings_b3/search_trading_session/_mtm_flattener.py`:

```python
"""Flatten B3's interleaved Margem Teórica Máxima records into tabular rows.

``MaximumTheoreticalMargin.csv`` is not tabular. It is a record stream: a one-line header, then
``INSTRUMENT`` blocks each followed by exactly ten ``MTM`` lines — one per ``holdingDay``. The
``INSTRUMENT`` line carries the fields that identify and price the instrument; the ``MTM`` lines
carry the margin values for that instrument. Neither is meaningful alone.

:func:`flatten_mtm` reshapes that into one row per ``(instrument, holdingDay)`` by propagating the
block header onto each of its ``MTM`` lines, which is what lets the reader reuse
``_base_pregao_reader``'s ordinary ``read_table`` lifecycle instead of bypassing it.

Two source properties drive the implementation:

- **Volume.** A single session is ~1.6 million lines, so the file is streamed line by line and
  written out as it goes — never accumulated in memory.
- **Decimal comma.** Values arrive as ``"44,3"``. ``utils.dtypes._to_decimal`` calls
  ``Decimal(text)``, which rejects a comma, and it deliberately refuses ``float`` input so that a
  lossy value can never be laundered into a type advertising exactness. The separator is therefore
  normalised **as text** here — the one place it can be done without ever materialising a float.

Empty fields are written through as empty, never defaulted to zero: which of the two value pairs a
row fills encodes the instrument's class (a position instrument has bought/sold margins, a
collateral instrument has collateral minimums, and some are both), so a blank is information.
"""

from __future__ import annotations

import csv
from pathlib import Path


# Flat output header, in emission order.
MTM_COLUMNS: tuple[str, ...] = (
	"RPT_DT",
	"INSTRM_ID",
	"INSTRM_SRC",
	"CLRG_HOUSE_ID",
	"REF_PRIC",
	"TCKR_SYMB",
	"HLDG_DAY",
	"MAX_THEOR_MRGN_BUY_PHI1",
	"MAX_THEOR_MRGN_SELL_PHI1",
	"MIN_MRGN_CRDT_COLTRL_PHI1",
	"MIN_MRGN_CRDT_COLTRL_PHI2",
)

# Fixed identifier B3 stamps in field 2 of the header line.
_FILE_ID: str = "maximumTheoreticalMargin"
# The source is Latin-1; B3 has never emitted a non-ASCII byte here, but decoding explicitly beats
# inheriting whatever the platform default happens to be.
_SRC_ENCODING: str = "latin-1"
_DELIMITER: str = ";"


class MtmFormatError(ValueError):
	"""The MTM record stream does not match B3's published structure."""


def _normalise(str_value: str) -> str:
	"""Return a numeric field with a dot decimal separator, preserving blanks exactly.

	Parameters
	----------
	str_value : str
		Raw field text as published (e.g. ``"44,3"``, ``"-32,7955"``, ``""``).

	Returns
	-------
	str
		The same text with ``,`` replaced by ``.``; an empty input returns empty.
	"""
	return str_value.strip().replace(",", ".")


def flatten_mtm(path_src: Path, path_dest: Path) -> Path:
	"""Flatten an MTM record stream into one row per ``(instrument, holdingDay)``.

	Parameters
	----------
	path_src : pathlib.Path
		The raw ``MaximumTheoreticalMargin.csv`` extracted from ``MT{yymmdd}.zip``.
	path_dest : pathlib.Path
		Where to write the derived flat CSV (UTF-8, ``;``-delimited, dot decimals).

	Returns
	-------
	pathlib.Path
		``path_dest``, for chaining into ``locate_table``.

	Raises
	------
	MtmFormatError
		If the header names an unexpected file id, an ``MTM`` record appears before any
		``INSTRUMENT``, or a record type other than ``INSTRUMENT``/``MTM`` is encountered.
	"""
	with (
		path_src.open(encoding=_SRC_ENCODING, newline="") as file_in,
		path_dest.open("w", encoding="utf-8", newline="") as file_out,
	):
		cls_writer = csv.writer(file_out, delimiter=_DELIMITER, lineterminator="\n")
		cls_writer.writerow(MTM_COLUMNS)

		str_header = file_in.readline().rstrip("\n")
		list_header = str_header.split(_DELIMITER)
		if len(list_header) < 2 or list_header[1].strip() != _FILE_ID:
			raise MtmFormatError(
				f"unexpected file id in header {str_header!r}: expected {_FILE_ID!r}"
			)
		str_rpt_dt = list_header[0].strip()

		list_block: list[str] = []
		for str_line in file_in:
			str_line = str_line.rstrip("\n")
			if not str_line.strip():
				continue
			list_field = str_line.split(_DELIMITER)
			str_kind = list_field[0].strip()
			if str_kind == "INSTRUMENT":
				list_block = [
					str_rpt_dt,
					list_field[1].strip(),
					list_field[2].strip(),
					list_field[3].strip(),
					_normalise(list_field[4]),
					list_field[5].strip(),
				]
			elif str_kind == "MTM":
				if not list_block:
					raise MtmFormatError(f"MTM record before any INSTRUMENT: {str_line!r}")
				cls_writer.writerow(
					[
						*list_block,
						list_field[1].strip(),
						_normalise(list_field[2]),
						_normalise(list_field[3]),
						_normalise(list_field[4]),
						_normalise(list_field[5]),
					]
				)
			else:
				raise MtmFormatError(f"unknown record type {str_kind!r} in line {str_line!r}")
	return path_dest
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `rtk proxy python -m pytest tests/unit/test_mtm_flattener.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Run lint and type checks**

Run: `rtk proxy python -m ruff check src/filings_b3/search_trading_session/_mtm_flattener.py tests/unit/test_mtm_flattener.py && rtk proxy python -m mypy src/filings_b3/search_trading_session/_mtm_flattener.py`
Expected: no findings. Fix anything reported before committing.

- [ ] **Step 6: Commit**

```bash
rtk git add src/filings_b3/search_trading_session/_mtm_flattener.py tests/unit/test_mtm_flattener.py
rtk git commit -m "feat: add MTM record-stream flattener

Turns B3's interleaved INSTRUMENT/MTM records into one row per
(instrument, holdingDay), streaming and normalising the decimal comma
as text so no value is ever routed through a float.

Refs #80"
```

> Run every `git commit` with `dangerouslyDisableSandbox: true`, never piped through `tail`/`head`/`grep`, then verify with `echo "===EXIT=$?===" ; rtk git log --oneline -1`. A commit that prints success in the sandbox overlay can still leave HEAD unmoved.

---

### Task 2: Contract, reader, and public export

The deliverable: `MaximumTheoreticalMarginReader(date_ref=...).read()` returns the typed frame.

**Files:**
- Create: `src/filings_b3/_internal/config/contracts/search_trading_session/maximum_theoretical_margin.py`
- Create: `src/filings_b3/search_trading_session/maximum_theoretical_margin.py`
- Modify: `src/filings_b3/_internal/config/contracts/search_trading_session/__init__.py` (add the export, following the existing lines)
- Modify: `src/filings_b3/search_trading_session/__init__.py` (add import and `__all__` entry, alphabetically)
- Test: `tests/unit/test_maximum_theoretical_margin.py`

**Interfaces:**
- Consumes: `flatten_mtm`, `MTM_COLUMNS` from Task 1.
- Produces: `MaximumTheoreticalMarginReader` — a `_BasePregaoReader` subclass with `str_source_key = "maximum_theoretical_margin"`, `build_url() -> str`, and `locate_table(path_download: Path) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_maximum_theoretical_margin.py`:

```python
"""Unit tests for MaximumTheoreticalMarginReader."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

from filings_b3._internal.config.contracts import MAXIMUM_THEORETICAL_MARGIN
from filings_b3.search_trading_session import MaximumTheoreticalMarginReader


SAMPLE = (
	"2026-08-21;maximumTheoreticalMargin;1\n"
	"INSTRUMENT;200002981938;8;BVMF;44,3;PETR4\n"
	"MTM;1;;;0;0;\n"
	"MTM;2;;;31,01;31,01;\n"
)


def test_build_url_uses_mt_code_and_two_digit_year() -> None:
	cls_reader = MaximumTheoreticalMarginReader(date_ref=date(2026, 8, 21))
	assert cls_reader.build_url() == (
		"https://www.b3.com.br/pesquisapregao/download?filelist=MT260821.zip"
	)


def test_contract_names_the_source_key() -> None:
	assert MAXIMUM_THEORETICAL_MARGIN.str_source_key == "maximum_theoretical_margin"
	assert MaximumTheoreticalMarginReader.str_source_key == "maximum_theoretical_margin"


def test_locate_table_returns_a_flat_csv_leaving_the_zip_untouched(tmp_path: Path) -> None:
	path_zip = tmp_path / "MT260821.zip"
	with zipfile.ZipFile(path_zip, "w") as cls_zip:
		cls_zip.writestr("MaximumTheoreticalMargin.csv", SAMPLE.encode("latin-1"))
	int_size_before = path_zip.stat().st_size

	cls_reader = MaximumTheoreticalMarginReader(date_ref=date(2026, 8, 21))
	path_table = cls_reader.locate_table(path_zip)

	assert path_table.suffix == ".csv"
	assert path_table.read_text(encoding="utf-8").splitlines()[0].startswith("RPT_DT;")
	assert path_zip.stat().st_size == int_size_before


def test_locate_table_writes_outside_the_download_directory(tmp_path: Path) -> None:
	"""The derived CSV must not land in path_raw — bronze keeps the original artifact only."""
	path_zip = tmp_path / "MT260821.zip"
	with zipfile.ZipFile(path_zip, "w") as cls_zip:
		cls_zip.writestr("MaximumTheoreticalMargin.csv", SAMPLE.encode("latin-1"))

	cls_reader = MaximumTheoreticalMarginReader(date_ref=date(2026, 8, 21))
	path_table = cls_reader.locate_table(path_zip)

	assert tmp_path not in path_table.parents
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `rtk proxy python -m pytest tests/unit/test_maximum_theoretical_margin.py -v`
Expected: FAIL — `ImportError: cannot import name 'MAXIMUM_THEORETICAL_MARGIN'`

- [ ] **Step 3: Write the contract**

Create `src/filings_b3/_internal/config/contracts/search_trading_session/maximum_theoretical_margin.py`:

```python
"""Contract for the Pesquisa por Pregão Margem Teórica Máxima file.

The contract validates the **flattened** frame, not the raw record stream: by the time
``read_table`` runs, ``_mtm_flattener`` has already reshaped ``INSTRUMENT``/``MTM`` into one row
per ``(instrument, holdingDay)``. Those eleven columns are wholly derived from B3's published
layout, so this is a **full-column** contract — a column the source stops emitting is drift, and
so is a column it starts emitting.
"""

from __future__ import annotations

from filings_b3._internal.utils.tabular_reader import FileContract


MAXIMUM_THEORETICAL_MARGIN = FileContract(
	"Pesquisa por Pregão — Margem Teórica Máxima",
	"maximum_theoretical_margin",
	(
		"RPT_DT",
		"INSTRM_ID",
		"INSTRM_SRC",
		"CLRG_HOUSE_ID",
		"REF_PRIC",
		"TCKR_SYMB",
		"HLDG_DAY",
		"MAX_THEOR_MRGN_BUY_PHI1",
		"MAX_THEOR_MRGN_SELL_PHI1",
		"MIN_MRGN_CRDT_COLTRL_PHI1",
		"MIN_MRGN_CRDT_COLTRL_PHI2",
	),
	(),
	bool_full_column=True,
)
```

Then register it in the two aggregators. `MAXIMUM_THEORETICAL_MARGIN` sorts **after**
`INSTRUMENTS_LAYOUT_META` in both, so each edit appends one line to the end of an existing block.

In `src/filings_b3/_internal/config/contracts/search_trading_session/__init__.py` — add the import
beside the sibling ones, and the name as the last entry of `__all__`:

```python
from filings_b3._internal.config.contracts.search_trading_session.maximum_theoretical_margin import (  # noqa: E501
	MAXIMUM_THEORETICAL_MARGIN,
)
```

```python
	"INSTRUMENTS_LAYOUT_META",
	"MAXIMUM_THEORETICAL_MARGIN",
]
```

In `src/filings_b3/_internal/config/contracts/__init__.py` — add it to the
`search_trading_session` import block (last name in that parenthesised list) and to `__all__`:

```python
from filings_b3._internal.config.contracts.search_trading_session import (
	INSTRUMENTS_FILE,
	# … existing names unchanged …
	INSTRUMENTS_LAYOUT_META,
	MAXIMUM_THEORETICAL_MARGIN,
)
```

```python
	"INSTRUMENTS_LAYOUT_META",
	"MAXIMUM_THEORETICAL_MARGIN",
]
```

- [ ] **Step 3b: Add the contract/flattener consistency guard**

The contract's `tuple_required` and `MTM_COLUMNS` describe the same eleven columns in two files.
Nothing structural keeps them in step, and the failure mode is a `ContractError` at read time with
no hint of the cause. One assertion removes the whole class of bug — append to
`tests/unit/test_maximum_theoretical_margin.py`:

```python
def test_contract_matches_the_flattener_output_columns() -> None:
	"""The contract validates exactly the columns the flattener emits, in order."""
	from filings_b3.search_trading_session._mtm_flattener import MTM_COLUMNS

	assert MAXIMUM_THEORETICAL_MARGIN.tuple_required == MTM_COLUMNS
```

- [ ] **Step 4: Write the reader**

Create `src/filings_b3/search_trading_session/maximum_theoretical_margin.py`:

```python
"""Pesquisa por Pregão — Margem Teórica Máxima (maximum theoretical margin).

B3 publishes ``MT{yymmdd}.zip`` daily, holding ``MaximumTheoreticalMargin.csv``. Officially the
file is *"Margem Teórica Máxima para Posições em Aberto e Valor Mínimo de Ativos Depositados em
Garantia"* — **two products in one file**, which is what the two pairs of value columns are:

- ``MAX_THEOR_MRGN_BUY_PHI1`` / ``MAX_THEOR_MRGN_SELL_PHI1`` — margin for an **open position**,
  populated for options and futures. These can be **negative**.
- ``MIN_MRGN_CRDT_COLTRL_PHI1`` / ``MIN_MRGN_CRDT_COLTRL_PHI2`` — minimum credit value when the
  instrument is **deposited as collateral**, populated for government bonds, currency and shares.

Which pair a row fills therefore encodes the instrument's class, not a buy/sell split, and an
empty field is information — it is written through as empty, never defaulted.

Beware the ``.zip`` layouts B3 publishes as *"Layout Mercado de Derivativos — Margem Teórica Máxima
para Ativos Líquidos"* (2005 and 2017 editions): they document a **legacy, different** file — a
flat 6-field record with a single margin value and no ``holdingDay``. The current layout lives in
``MargemteoricaMaxima-Atualizado2.xlsx``.

The source is a record stream rather than a table, so :meth:`locate_table` flattens it before the
inherited lifecycle reads it. Provenance still hashes the original ``.zip``, and ``path_raw`` still
keeps that original — the flattened CSV is a private intermediate.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from filings_b3._internal.config.contracts import MAXIMUM_THEORETICAL_MARGIN
from filings_b3._internal.utils.zip_extractor import extract_all
from filings_b3.search_trading_session._base_pregao_reader import (
	PREGAO_DOWNLOAD_BASE,
	_BasePregaoReader,
)
from filings_b3.search_trading_session._mtm_flattener import flatten_mtm


# Every column stays source text except the five numeric ones, which become exact Decimal.
_DICT_DTYPES: dict[str, str] = {
	"INSTRM_ID": "string",
	"INSTRM_SRC": "string",
	"CLRG_HOUSE_ID": "string",
	"TCKR_SYMB": "string",
	"HLDG_DAY": "Int64",
}
_LIST_DATE_COLS: tuple[str, ...] = ("RPT_DT",)
# Price and every margin value: money, so exact Decimal — never a binary float.
_LIST_DECIMAL_COLS: tuple[str, ...] = (
	"REF_PRIC",
	"MAX_THEOR_MRGN_BUY_PHI1",
	"MAX_THEOR_MRGN_SELL_PHI1",
	"MIN_MRGN_CRDT_COLTRL_PHI1",
	"MIN_MRGN_CRDT_COLTRL_PHI2",
)
# Member inside MT{yymmdd}.zip.
_MEMBER_NAME: str = "MaximumTheoreticalMargin.csv"


class MaximumTheoreticalMarginReader(_BasePregaoReader):
	"""Reader for B3's daily maximum theoretical margin file.

	Returns one row per ``(instrument, holdingDay)`` — 145,090 instruments × 10 holding days on a
	typical session — with the reference price and all four margin values as exact
	:class:`decimal.Decimal`.

	Parameters
	----------
	date_ref : datetime.date
		Trading session to read; the URL is built for this date.
	path_raw : pathlib.Path, optional
		Directory in which to **keep** the downloaded raw ``.zip`` (the datalake's bronze layer).
		``None`` (default) uses a temporary directory removed on exit.
	cls_logger : LogEmitter, optional
		Injected log sink; defaults to a stdlib-backed :class:`LogEmitter`.
	cls_retry_policy : RetryPolicy, optional
		Injected retry/backoff schedule for the download; ``None`` uses the seam's own default.
	"""

	str_source_key = "maximum_theoretical_margin"
	cls_contract = MAXIMUM_THEORETICAL_MARGIN
	dict_dtypes = _DICT_DTYPES
	list_date_cols = _LIST_DATE_COLS
	list_decimal_cols = _LIST_DECIMAL_COLS

	def build_url(self) -> str:
		"""Return the ``MT{yymmdd}.zip`` download URL for :attr:`date_ref`.

		Returns
		-------
		str
			The trading-session download endpoint with this session's file code.
		"""
		return f"{PREGAO_DOWNLOAD_BASE}?filelist=MT{self.date_ref:%y%m%d}.zip"

	def locate_table(self, path_download: Path) -> Path:
		"""Extract the member and flatten its record stream into a tabular CSV.

		The derived CSV is written to a private temporary directory, **not** beside the
		download: when ``path_raw`` is set that directory is the datalake's bronze layer, and
		bronze holds the artifact as published, not our intermediates. The temporary directory
		is intentionally not context-managed — the inherited ``read`` consumes the file
		immediately afterwards, and the OS reclaims the directory at process exit.

		Parameters
		----------
		path_download : pathlib.Path
			The ``MT{yymmdd}.zip`` just downloaded.

		Returns
		-------
		pathlib.Path
			The flattened, UTF-8, dot-decimal CSV for ``read_table``.
		"""
		path_work = Path(tempfile.mkdtemp(prefix="mtm_"))
		extract_all(path_download, path_work)
		# ponytail: mkdtemp is reclaimed at process exit rather than by a context manager,
		# because read() consumes the file on the next line. If this reader ever runs in a
		# long-lived process ingesting many sessions, wrap it in TemporaryDirectory instead.
		return flatten_mtm(path_work / _MEMBER_NAME, path_work / "mtm_flat.csv")
```

- [ ] **Step 5: Export the reader**

In `src/filings_b3/search_trading_session/__init__.py`, add the import beside the others and the
name to `__all__` in alphabetical position (it sorts before `InstrumentsFile…`):

```python
from filings_b3.search_trading_session.maximum_theoretical_margin import (
	MaximumTheoreticalMarginReader,
)
```

```python
__all__ = [
	"InstrumentsFileAdrReader",
	# … existing entries unchanged …
	"InstrumentsLayoutMetaReader",
	"MaximumTheoreticalMarginReader",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `rtk proxy python -m pytest tests/unit/test_maximum_theoretical_margin.py -v`
Expected: PASS — 5 passed

- [ ] **Step 7: Run the full suite, lint and types**

Run: `rtk proxy python -m pytest tests/unit -q && rtk proxy python -m ruff check src tests && rtk proxy python -m mypy src`
Expected: all green. The full suite catches an `__init__.py` export or contract-registry mistake that the new tests alone would not.

- [ ] **Step 8: Commit**

```bash
rtk git add src/filings_b3/_internal/config/contracts src/filings_b3/search_trading_session tests/unit/test_maximum_theoretical_margin.py
rtk git commit -m "feat: add MaximumTheoreticalMarginReader

Migrates b3_maximum_theoretical_margin from stpstone. The source is a
record stream, so locate_table flattens it into a tabular CSV and the
inherited pregao lifecycle reads it unchanged; provenance still hashes
the original zip and path_raw still keeps it.

Closes #80"
```

---

### Task 3: Real-session verification and documentation

Proves the reader against the real artifact rather than a synthetic fixture, and pins the two facts the design rests on.

**Files:**
- Create: `tests/integration/test_maximum_theoretical_margin_session.py`
- Modify: `docs/usage.md` (add the reader to the trading-session examples)

**Interfaces:**
- Consumes: `MaximumTheoreticalMarginReader` from Task 2.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the integration test**

The test is skipped unless a real session file is supplied, so CI stays offline and hermetic.

Create `tests/integration/test_maximum_theoretical_margin_session.py`:

```python
"""Verification of MaximumTheoreticalMarginReader against a real B3 session.

Skipped unless ``MTM_SESSION_CSV`` points at a real ``MaximumTheoreticalMargin.csv``. Run it as::

    MTM_SESSION_CSV=~/Downloads/pesquisa-pregao/MT260821/MaximumTheoreticalMargin.csv \\
        rtk proxy python -m pytest tests/integration -v
"""

from __future__ import annotations

import csv
import os
from decimal import Decimal
from pathlib import Path

import pytest

from filings_b3.search_trading_session._mtm_flattener import flatten_mtm


STR_ENV = "MTM_SESSION_CSV"

pytestmark = pytest.mark.skipif(
	not os.environ.get(STR_ENV), reason=f"{STR_ENV} not set — real-session test skipped"
)


@pytest.fixture
def path_flat(tmp_path: Path) -> Path:
	path_src = Path(os.environ[STR_ENV]).expanduser()
	return flatten_mtm(path_src, tmp_path / "flat.csv")


def test_every_instrument_has_exactly_ten_holding_days(path_flat: Path) -> None:
	dict_count: dict[str, int] = {}
	with path_flat.open(encoding="utf-8", newline="") as file_in:
		for dict_row in csv.DictReader(file_in, delimiter=";"):
			dict_count[dict_row["INSTRM_ID"]] = dict_count.get(dict_row["INSTRM_ID"], 0) + 1
	assert set(dict_count.values()) == {10}


def test_petr4_collateral_haircut_is_exact(path_flat: Path) -> None:
	"""1 - collateral/reference price reproduces B3's published haircut exactly.

	This is the property the gold layer downstream depends on, and it only holds because the
	decimal comma is normalised as text — a float round-trip loses the exactness.
	"""
	dict_by_day: dict[str, dict[str, str]] = {}
	with path_flat.open(encoding="utf-8", newline="") as file_in:
		for dict_row in csv.DictReader(file_in, delimiter=";"):
			if dict_row["TCKR_SYMB"] == "PETR4":
				dict_by_day[dict_row["HLDG_DAY"]] = dict_row

	dict_expected = {"2": Decimal("0.3000"), "3": Decimal("0.3600"), "10": Decimal("0.5500")}
	for str_day, dec_expected in dict_expected.items():
		dict_row = dict_by_day[str_day]
		dec_haircut = 1 - Decimal(dict_row["MIN_MRGN_CRDT_COLTRL_PHI1"]) / Decimal(
			dict_row["REF_PRIC"]
		)
		assert round(dec_haircut, 4) == dec_expected


def test_no_value_field_contains_a_comma(path_flat: Path) -> None:
	with path_flat.open(encoding="utf-8", newline="") as file_in:
		for dict_row in csv.DictReader(file_in, delimiter=";"):
			for str_col in ("REF_PRIC", "MIN_MRGN_CRDT_COLTRL_PHI1"):
				assert "," not in dict_row[str_col]
```

- [ ] **Step 2: Run it against the real session**

Run:
```bash
MTM_SESSION_CSV="$HOME/Downloads/pesquisa-pregao (3)/MT260821/MaximumTheoreticalMargin.csv" \
  rtk proxy python -m pytest tests/integration/test_maximum_theoretical_margin_session.py -v
```
Expected: PASS — 3 passed. The first test asserts 145,090 instruments × 10 holding days.

- [ ] **Step 3: Confirm it skips cleanly without the env var**

Run: `rtk proxy python -m pytest tests/integration -v`
Expected: 3 skipped, 0 failed.

- [ ] **Step 4: Document the reader**

Add to `docs/usage.md`, in the Pesquisa por Pregão section, matching the surrounding example style:

````markdown
### Margem Teórica Máxima

```python
from datetime import date
from pathlib import Path

from filings_b3.search_trading_session import MaximumTheoreticalMarginReader

df = MaximumTheoreticalMarginReader(
    date_ref=date(2026, 8, 21),
    path_raw=Path("~/datalake/bronze/b3/mtm").expanduser(),
).read()
```

One row per `(instrument, holdingDay)`. The two value pairs are different products sharing one
file: `MAX_THEOR_MRGN_BUY_PHI1`/`MAX_THEOR_MRGN_SELL_PHI1` are margins on an **open position**
(options and futures, and they can be negative), while
`MIN_MRGN_CRDT_COLTRL_PHI1`/`MIN_MRGN_CRDT_COLTRL_PHI2` are minimum credit values for the
instrument **deposited as collateral** (bonds, currency, shares). An empty field means the
instrument is not of that class — it is never zero.
````

- [ ] **Step 5: Commit**

```bash
rtk git add tests/integration/test_maximum_theoretical_margin_session.py docs/usage.md
rtk git commit -m "test: verify MTM reader against a real B3 session

Pins the two properties the downstream gold layer depends on: exactly
ten holding days per instrument, and an exact collateral haircut from
1 - collateral/reference price.

Refs #80"
```

---

## Known Characteristics

Not defects; recorded so a reviewer does not mistake them for oversights.

- **Memory.** A full session flattens to 1,450,900 rows × 11 columns, five of which become
  `Decimal` — Python objects, not a numpy dtype. Expect ~1.5 GB peak in `read()`. This is the
  deliberate cost of the exactness requirement; the fix, if it ever becomes one, is chunked reads
  in the consumer, never a float dtype.
- **`holdingDay` semantics unresolved.** B3's layout says "T+0, T+1…" but the data runs 1–10, and
  `PETR4` at `HLDG_DAY=1` carries collateral `0`, which would imply a 100% haircut. The reader
  passes the value through as published and takes no position; resolve it in the consumer after
  comparing two sessions.
- **`phi1` vs `phi2`.** Both collateral values coincide in every sample inspected. Both columns are
  carried; do not collapse them until a session is found where they diverge.
- **Instruments priced at zero.** The `BRL` block carries `REF_PRIC` `0`. The reader emits it
  faithfully; any division downstream must handle it explicitly.
