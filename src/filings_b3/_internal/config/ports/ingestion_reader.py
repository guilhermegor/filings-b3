"""Ingestion reader port — the shared contract every reader (adapter) implements.

Every ingestion solution turns a file downloaded from B3 into a typed, contract-validated
:class:`pandas.DataFrame`. This ABC is the **port** (hexagonal ports-and-adapters) pinning
that single operation — :meth:`read` — so callers can treat any reader polymorphically and
every new dataset conforms to the same shape. It is private (``_internal``): consumers import
the concrete readers, never this port.

The port is deliberately **thin**: it pins *behaviour*, not a lifecycle. B3's 105 datasets are
not homogeneous — most are CSV/ZIP downloads, but the ``clearing`` warranties are scraped HTML
and ``market_data`` reaches a legacy BMF portal — so a single Template-Method base spanning all
of them would accrete a hook per exception. Instead, each macro-section that *is* internally
homogeneous ships its own ``_base_*_reader.py`` beside its readers (e.g.
``daily_bulletin/_base_bdi_reader.py`` for the 39 BDI datasets); a reader whose source fits no
family implements :meth:`read` directly against this port.

Constructor convention — ``path_raw``
-------------------------------------
Ports pin behaviour, not construction, so this cannot be enforced in the ABC; it is the
convention every reader in this library (and every sibling ingestion package) follows.

**Every concrete reader accepts ``path_raw: Path | None = None``.** When ``None`` the raw
artifact lands in a :class:`tempfile.TemporaryDirectory` destroyed on exit — nothing
*persists*, though the read does transiently touch the filesystem. When set, the untouched raw
artifact (``.zip``, ``.csv``, ``.html``, ``.xlsx``, …) is written there and **kept**.

That matters because it is the datalake's bronze layer: when a source changes its contract and
the transform breaks, the exact bytes that broke it are still on disk and replayable, rather
than lost to a re-fetch of an already-changed source. Readers get this by routing through the
:func:`_internal.utils.raw_workspace.raw_workspace` context manager rather than branching on
the tempdir themselves.
"""

from __future__ import annotations

from abc import abstractmethod

import pandas as pd

from filings_b3._internal.utils.typing import ABCTypeCheckerMeta


class IngestionReader(metaclass=ABCTypeCheckerMeta):
	"""Contract for an ingestion reader: B3 file → typed DataFrame.

	``ABCTypeCheckerMeta`` gives both abstract-method enforcement (a partial adapter fails at
	instantiation) and runtime type checking of every call. Concrete readers inherit the port
	and its metaclass — do **not** redeclare ``metaclass`` on a subclass; Python inherits it.

	Methods
	-------
	read()
		Read the configured B3 source into a typed, contract-validated DataFrame.
	"""

	@abstractmethod
	def read(self) -> pd.DataFrame:
		"""Read the configured B3 source into a typed, validated DataFrame.

		Returns
		-------
		pd.DataFrame
			The parsed rows, with explicit column types applied and provenance stamped.

		Raises
		------
		NotImplementedError
			Always — a concrete reader must override this method.
		"""
		raise NotImplementedError
