"""Hand written material classes for handlers whose command line cannot
be represented by the generic positional exporter (flags with values,
option loops, grouped positional blocks).

Nested helper ``BalloonSaturation`` collects ``-fc/-ac/-na/-nd`` pairs of
the Balloon family; the exported tokens are appended after the required
``p`` array and density, mirroring the C++ flag loop.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from suanpan.base import format_float, format_value
from suanpan.material._generated import Material
from suanpan.toolbox.format import FloatList


class BalloonSaturation(BaseModel):
    """One ``(a, b)`` saturation pair of the Balloon family."""

    model_config = {"validate_assignment": True}

    a: float = Field(description="abscissa of the saturation bound")
    b: float = Field(description="ordinate of the saturation bound")

    def to_tokens(self) -> list[str]:
        return [format_float(self.a), format_float(self.b)]


class _Balloon(Material):
    """Base of ``Balloon`` and ``Balloon1D`` sharing the flag loop."""

    sp_abstract = True

    #: type of the ``zr`` buffer selected by ``-memory``
    memory: Literal["minimum", "maximum", "mean"] = Field(
        default="mean",
        description=(
            "zr memory type via -memory: MINIMUM, MAXIMUM or MEAN (default MEAN)"
        ),
    )

    def _flag_tokens(self) -> list[str]:
        tokens: list[str] = []
        for name, flag in (
            ("bfc", "-fc"),
            ("bac", "-ac"),
            ("bna", "-na"),
            ("bnd", "-nd"),
        ):
            for pair in getattr(self, name):
                tokens.append(flag)
                tokens.extend(pair.to_tokens())
        if self.memory != "mean":
            tokens += ["-memory", self.memory]
        return tokens


class Balloon(_Balloon):
    """``material Balloon`` (C++ ``Balloon``), 3D balloon material."""

    keyword = "Balloon"
    summary = "3D balloon material with saturation buffers"

    p: FloatList = Field(
        description=(
            "exactly 24 values: elastic, poisson, kr, zr_size and the five "
            "4-component bounds u/fm/fc/am/ac"
        )
    )
    density: float = Field(description="density (required)")
    bfc: list[BalloonSaturation] = Field(
        default_factory=list, description="-fc pairs (backbone force)"
    )
    bac: list[BalloonSaturation] = Field(
        default_factory=list, description="-ac pairs (auxiliary force)"
    )
    bna: list[BalloonSaturation] = Field(
        default_factory=list, description="-na pairs (nucleation area)"
    )
    bnd: list[BalloonSaturation] = Field(
        default_factory=list, description="-nd pairs (nucleation decay)"
    )

    @field_validator("p")
    @classmethod
    def _check_p(cls, value: FloatList) -> FloatList:
        if len(value) != 24:
            raise ValueError("Balloon requires exactly 24 values in p")
        return value

    def to_commands(self) -> list[str]:
        parts = ["material", self.keyword, str(self.tag)]
        parts += format_value(self.p)
        parts += [format_float(self.density)]
        parts += self._flag_tokens()
        return [" ".join(parts)]


class Balloon1D(_Balloon):
    """``material Balloon1D`` (C++ ``Balloon1D``), uniaxial balloon."""

    keyword = "Balloon1D"
    summary = "1D balloon material with saturation buffers"

    p: FloatList = Field(
        description=(
            "exactly 23 values: elastic, kr, zr_size and the five "
            "4-component bounds u/fm/fc/am/ac"
        )
    )
    density: float = Field(description="density (required)")
    bfc: list[BalloonSaturation] = Field(
        default_factory=list, description="-fc pairs (backbone force)"
    )
    bac: list[BalloonSaturation] = Field(
        default_factory=list, description="-ac pairs (auxiliary force)"
    )
    bna: list[BalloonSaturation] = Field(
        default_factory=list, description="-na pairs (nucleation area)"
    )
    bnd: list[BalloonSaturation] = Field(
        default_factory=list, description="-nd pairs (nucleation decay)"
    )

    @field_validator("p")
    @classmethod
    def _check_p(cls, value: FloatList) -> FloatList:
        if len(value) != 23:
            raise ValueError("Balloon1D requires exactly 23 values in p")
        return value

    def to_commands(self) -> list[str]:
        parts = ["material", self.keyword, str(self.tag)]
        parts += format_value(self.p)
        parts += [format_float(self.density)]
        parts += self._flag_tokens()
        return [" ".join(parts)]


class ConcreteK4(Material):
    """``material ConcreteK4`` (C++ ``ConcreteK4``).

    The trailing boolean trio ``(enable_damage, enable_crack_closing,
    objective_damage)`` is parsed as one group: tokens are exported only
    as a complete triplet, exactly matching the single ``get_input`` call
    of the C++ parser.
    """

    keyword = "ConcreteK4"
    summary = "concrete with damage and crack closing"

    elastic_modulus: float = Field(description="elastic modulus")
    hardening: float = Field(description="hardening parameter")
    pool: FloatList = Field(description="exactly 8 concrete parameters")
    density: float = Field(default=0.0, description="density")
    enable_damage: bool = Field(default=True, description="enable damage")
    enable_crack_closing: bool = Field(default=True, description="enable crack closing")
    objective_damage: bool = Field(
        default=False, description="objective damage definition"
    )

    @field_validator("pool")
    @classmethod
    def _check_pool(cls, value: FloatList) -> FloatList:
        if len(value) != 8:
            raise ValueError("ConcreteK4 requires exactly 8 values in pool")
        return value

    def to_commands(self) -> list[str]:
        parts = [
            "material",
            self.keyword,
            str(self.tag),
            *format_value(self.elastic_modulus),
            *format_value(self.hardening),
        ]
        parts += format_value(self.pool)
        trio_set = (
            self.enable_damage != True,
            self.enable_crack_closing != True,
            self.objective_damage != False,
        )
        if any(trio_set):
            # a trailing group requires the density slot to be filled
            parts.append(format_float(self.density))
            parts += [
                "true" if self.enable_damage else "false",
                "true" if self.enable_crack_closing else "false",
                "true" if self.objective_damage else "false",
            ]
        elif self.density != 0.0:
            parts.append(format_float(self.density))
        return [" ".join(parts)]


class MultiSubloading1D(Material):
    """``material MultiSubloading1D`` (C++ ``Subloading1D``).

    Saturation terms are appended by repeatable ``-back`` and ``-core``
    flags, each followed by one ``(a, b)`` pair.
    """

    keyword = "MultiSubloading1D"
    summary = "multi-subloading surface 1D material"

    parameters: FloatList = Field(
        description=(
            "exactly 11 values: elastic, four iso-bound, four kin-bound "
            "values and u; the last value is the density"
        )
    )
    back: list[BalloonSaturation] = Field(
        default_factory=list, description="-back saturation pairs"
    )
    core: list[BalloonSaturation] = Field(
        default_factory=list, description="-core saturation pairs"
    )

    @field_validator("parameters")
    @classmethod
    def _check_parameters(cls, value: FloatList) -> FloatList:
        if len(value) != 11:
            raise ValueError("MultiSubloading1D requires exactly 11 parameters")
        return value

    def to_commands(self) -> list[str]:
        parts = ["material", self.keyword, str(self.tag)]
        parts += format_value(self.parameters)
        for flag, name in (("-back", "back"), ("-core", "core")):
            for pair in getattr(self, name):
                parts.append(flag)
                parts.extend(pair.to_tokens())
        return [" ".join(parts)]
