"""Ports — the behavioural boundary interfaces of the library (hexagonal, private).

In ports-and-adapters terms these ABCs are the **ports**: the abstract operation each
macro-section's concrete classes (the *adapters*) implement, so every variant conforms to the
same shape. They ship inside the wheel under ``_internal`` but are **not** part of the public
API — consumers import the concrete readers, never these ports. Re-export each port here so
callers use one import: ``from filings_b3._internal.config.ports import IngestionReader``.
"""

from filings_b3._internal.config.ports.ingestion_reader import IngestionReader


__all__ = ["IngestionReader"]
