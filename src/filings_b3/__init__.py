"""filings-b3 package."""

from importlib.metadata import PackageNotFoundError, version


try:
	__version__ = version("filings-b3")
except PackageNotFoundError:  # pragma: no cover - source tree without an installed dist
	__version__ = "0.0.0"


__all__ = ["__version__"]
