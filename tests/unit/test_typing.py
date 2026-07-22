"""Smoke test: the runtime type-checking engine resolves in the wheel layout."""

import pytest

from filings-b3._internal.utils.typing import TypeChecker, type_checker


class _Sample(metaclass=TypeChecker):
	"""Exercise the metaclass after the ``_internal`` import rewrite."""

	@staticmethod
	def doubled(x: int) -> int:
		"""Return ``x`` doubled.

		Parameters
		----------
		x : int
			A number.

		Returns
		-------
		int
			``x * 2``.
		"""
		return x * 2


def test_engine_imports_and_enforces_after_rewrite() -> None:
	"""The rewritten engine imports and rejects a wrong-typed argument."""
	assert _Sample.doubled(5) == 10
	with pytest.raises(TypeError):
		_Sample.doubled("five")


def test_decorator_rejects_wrong_type() -> None:
	"""The decorator validates a standalone function's arguments."""

	@type_checker
	def add(a: int, b: int) -> int:
		"""Add two ints.

		Parameters
		----------
		a : int
			First addend.
		b : int
			Second addend.

		Returns
		-------
		int
			The sum.
		"""
		return a + b

	assert add(1, 2) == 3
	with pytest.raises(TypeError):
		add(1, "two")
