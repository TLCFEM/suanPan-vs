"""Value helpers mirroring ``Toolbox/utility.h`` utilities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any

from pydantic import BeforeValidator

__all__ = ["as_float_list", "as_int_list", "as_str_list", "is_true"]


def is_true(value: str | bool) -> bool:
    """Parse a suanPan boolean token (``is_true`` in Toolbox/utility.h)."""
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"true", "1", "on", "yes", "y", "t"}


def _coerce_sequence(value: Any) -> list[Any]:
    """Accept ``1 2 3``, ``[1, 2, 3]``, ``'1 2 3'`` as lists."""
    if value is None:
        return []
    if isinstance(value, str):
        return value.split()
    if isinstance(value, Sequence):
        return list(value)
    return [value]


def as_int_list(value: Any) -> list[int]:
    """Coerce assorted inputs into a list of integers."""
    return [int(v) for v in _coerce_sequence(value)]


def as_float_list(value: Any) -> list[float]:
    """Coerce assorted inputs into a list of floats."""
    return [float(v) for v in _coerce_sequence(value)]


def as_str_list(value: Any) -> list[str]:
    """Coerce assorted inputs into a list of strings."""
    return [str(v) for v in _coerce_sequence(value)]


IntList = Annotated[list[int], BeforeValidator(as_int_list)]
FloatList = Annotated[list[float], BeforeValidator(as_float_list)]
StrList = Annotated[list[str], BeforeValidator(as_str_list)]
