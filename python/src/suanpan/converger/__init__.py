"""Convergers, mirroring ``Converger/ConvergerParser.cpp``
(the ``converger`` command).

Standard convergers share the signature
``converger <type> <tag> <tolerance> <max_iteration> <print_flag>``,
logic convergers take ``converger <type> <tag> <tag_a> <tag_b>`` instead,
and ``FixedNumber`` has no tolerance.
"""

from __future__ import annotations

from pydantic import Field

from suanpan.base import SuanpanObject, format_value

__all__ = [
    "AbsDisp",
    "AbsError",
    "AbsIncreAcc",
    "AbsIncreDisp",
    "AbsIncreEnergy",
    "AbsResidual",
    "Converger",
    "FixedNumber",
    "LogicConvergerAND",
    "LogicConvergerOR",
    "LogicConvergerXOR",
    "RelDisp",
    "RelError",
    "RelIncreAcc",
    "RelIncreDisp",
    "RelIncreEnergy",
    "RelResidual",
]


def _trim(*pairs: tuple[object, object]) -> list[object]:
    """Keep the positional prefix up to the last value differing from its
    eof-guarded default (tokens are positional in the C++ parser, so a
    later value forces all earlier ones to be emitted)."""
    last = -1
    for index, (value, default) in enumerate(pairs):
        if value != default:
            last = index
    return [value for value, _ in pairs[: last + 1]]


def _line(command: str, keyword: str, tag: int, *values: object) -> str:
    parts = [command, keyword, *format_value(tag)]
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            parts.append("true" if value else "false")
        elif isinstance(value, (int, float)):
            parts.extend(format_value(value))
        elif isinstance(value, str):
            parts.append(value)
        else:  # sequence
            parts.extend(format_value(value))
    return " ".join(parts)


class Converger(SuanpanObject):
    """Base class of convergers (``converger`` command)."""

    command = "converger"
    sp_abstract = True


class _Standard(Converger):
    """``converger <type> <tag> <tolerance> <max_iteration> <print_flag>``."""

    tolerance: float = Field(default=1e-6, description="tolerance (default 1E-6)")
    max_iteration: int = Field(default=10, description="maximum iteration (default 10)")
    print_flag: bool = Field(default=False, description="print each iteration")

    def to_commands(self) -> list[str]:
        return [
            _line(
                "converger",
                type(self).keyword,
                self.tag,
                *_trim(
                    (self.tolerance, 1e-6),
                    (self.max_iteration, 10),
                    (self.print_flag, False),
                ),
            )
        ]


class FixedNumber(Converger):
    """``converger FixedNumber`` (C++ ``FixedNumber``) -- fixed iterations."""

    keyword = "FixedNumber"
    summary = "converge after a fixed number of iterations"

    max_iteration: int = Field(default=10, description="number of iterations")
    print_flag: bool = Field(default=False, description="print each iteration")

    def to_commands(self) -> list[str]:
        return [
            _line(
                "converger",
                "FixedNumber",
                self.tag,
                *_trim((self.max_iteration, 10), (self.print_flag, False)),
            )
        ]


class LogicConverger(Converger):
    """Base of logic convergers combining other convergers by tag."""

    sp_abstract = True

    tag_a: int = Field(description="tag of the first converger")
    tag_b: int = Field(description="tag of the second converger")

    def to_commands(self) -> list[str]:
        return [
            _line("converger", type(self).keyword, self.tag, self.tag_a, self.tag_b)
        ]


class LogicConvergerAND(LogicConverger):
    """``converger LogicAND`` (C++ ``LogicConvergerAND``)."""

    keyword = "LogicAND"
    aliases = ("LogicConvergerAND",)
    summary = "converged when both convergers converge"


class LogicConvergerOR(LogicConverger):
    """``converger LogicOR`` (C++ ``LogicConvergerOR``)."""

    keyword = "LogicOR"
    aliases = ("LogicConvergerOR",)
    summary = "converged when either converger converges"


class LogicConvergerXOR(LogicConverger):
    """``converger LogicXOR`` (C++ ``LogicConvergerXOR``)."""

    keyword = "LogicXOR"
    aliases = ("LogicConvergerXOR",)
    summary = "converged when exactly one converger converges"


class AbsResidual(_Standard):
    """``converger AbsResidual`` (C++ ``AbsResidual``)."""

    keyword = "AbsResidual"
    summary = "absolute residual norm"


class RelResidual(_Standard):
    """``converger RelResidual`` (C++ ``RelResidual``)."""

    keyword = "RelResidual"
    summary = "relative residual norm"


class AbsIncreDisp(_Standard):
    """``converger AbsIncreDisp`` (C++ ``AbsIncreDisp``)."""

    keyword = "AbsIncreDisp"
    summary = "absolute displacement increment norm"


class RelIncreDisp(_Standard):
    """``converger RelIncreDisp`` (C++ ``RelIncreDisp``)."""

    keyword = "RelIncreDisp"
    summary = "relative displacement increment norm"


class AbsIncreAcc(_Standard):
    """``converger AbsIncreAcc`` (C++ ``AbsIncreAcc``)."""

    keyword = "AbsIncreAcc"
    summary = "absolute acceleration increment norm"


class RelIncreAcc(_Standard):
    """``converger RelIncreAcc`` (C++ ``RelIncreAcc``)."""

    keyword = "RelIncreAcc"
    summary = "relative acceleration increment norm"


class AbsDisp(_Standard):
    """``converger AbsDisp`` (C++ ``AbsDisp``)."""

    keyword = "AbsDisp"
    summary = "absolute displacement norm"


class RelDisp(_Standard):
    """``converger RelDisp`` (C++ ``RelDisp``)."""

    keyword = "RelDisp"
    summary = "relative displacement norm"


class AbsError(_Standard):
    """``converger AbsError`` (C++ ``AbsError``)."""

    keyword = "AbsError"
    summary = "absolute energy error norm"


class RelError(_Standard):
    """``converger RelError`` (C++ ``RelError``)."""

    keyword = "RelError"
    summary = "relative energy error norm"


class AbsIncreEnergy(_Standard):
    """``converger AbsIncreEnergy`` (C++ ``AbsIncreEnergy``)."""

    keyword = "AbsIncreEnergy"
    summary = "absolute energy increment norm"


class RelIncreEnergy(_Standard):
    """``converger RelIncreEnergy`` (C++ ``RelIncreEnergy``)."""

    keyword = "RelIncreEnergy"
    summary = "relative energy increment norm"
