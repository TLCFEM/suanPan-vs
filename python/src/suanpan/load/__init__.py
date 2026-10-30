"""Loads and amplitudes, mirroring ``Load/LoadParser.cpp``
(the ``amplitude`` and ``load`` command families, including the shorthand
aliases such as ``cload`` and ``displacement``).

Every load shares the positional layout
``<TYPE> <tag> <amplitude tag> <magnitude> <dof> <tags...>``.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from suanpan.base import SuanpanObject, format_value
from suanpan.toolbox.dof import DofToken
from suanpan.toolbox.format import FloatList, IntList

__all__ = [
    "Acceleration",
    "Amplitude",
    "BodyForce",
    "Cload",
    "Combine",
    "Constant",
    "Cosine",
    "CustomAmplitude",
    "Decay",
    "Disp",
    "GroupBodyForce",
    "GroupCload",
    "GroupDisp",
    "GroupReferenceLoad",
    "LineUDL2D",
    "LineUDL3D",
    "Linear",
    "Load",
    "Modulated",
    "NZStrongMotion",
    "Ramp",
    "ReferenceLoad",
    "Sine",
    "SupportAcceleration",
    "SupportDisplacement",
    "SupportVelocity",
    "Tabular",
    "TabularSpline",
]


# --------------------------------------------------------------------------- #
# amplitudes                                                                  #
# --------------------------------------------------------------------------- #
class Amplitude(SuanpanObject):
    """Base class of amplitudes (``amplitude`` command)."""

    command = "amplitude"
    sp_abstract = True

    def to_commands(self) -> list[str]:
        from suanpan.base import sp_kind

        parts = [self.command, self.keyword, *format_value(self.tag)]
        for name, field in type(self).model_fields.items():
            if name == "tag" or sp_kind(field) != "positional":
                continue
            value = getattr(self, name)
            if value is None or value == []:
                continue
            parts.extend(format_value(value, field))
        return [" ".join(parts)]


class Constant(Amplitude):
    """``amplitude Constant`` (C++ ``Constant``) -- constant amplitude."""

    keyword = "Constant"
    summary = "constant amplitude 1"


class Ramp(Amplitude):
    """``amplitude Ramp`` (C++ ``Ramp``) -- linearly increasing amplitude."""

    keyword = "Ramp"
    summary = "amplitude equal to the step time"


class Tabular(Amplitude):
    """``amplitude Tabular`` (C++ ``Tabular``).

    Two parsing modes exist in the C++ source: when only a file name is
    given the file is used directly; when an ``up_rate`` follows, the data
    is upsampled with the given window function and window size.
    """

    keyword = "Tabular"
    summary = "amplitude from tabular data"

    file_name: str = Field(description="path to the tabular data file")
    up_rate: int | None = Field(
        default=None, ge=1, description="upsampling rate when provided"
    )
    window_type: str | None = Field(
        default=None, description="window function, default Hamming"
    )
    window_size: int | None = Field(
        default=None, ge=1, description="window size, default 8"
    )


class TabularSpline(Amplitude):
    """``amplitude TabularSpline`` (C++ ``TabularSpline``)."""

    keyword = "TabularSpline"
    summary = "amplitude from spline interpolated tabular data"

    file_name: str = Field(description="path to the tabular data file")


class Decay(Amplitude):
    """``amplitude Decay`` (C++ ``Decay``) -- ``A * exp(-t/TD)``."""

    keyword = "Decay"
    summary = "decaying amplitude"

    A: float = Field(description="peak value A")
    TD: float = Field(description="decay time constant TD")


class Linear(Amplitude):
    """``amplitude Linear`` (C++ ``Linear``) -- ``A * t``."""

    keyword = "Linear"
    summary = "linear ramp with slope A"

    A: float = Field(description="slope A")


class Combine(Amplitude):
    """``amplitude Combine`` (C++ ``Combine``) -- product of other amplitudes."""

    keyword = "Combine"
    summary = "multiplicative combination of other amplitudes"

    amplitude_tags: IntList = Field(
        default_factory=list, description="tags of amplitudes to multiply"
    )


class CustomAmplitude(Amplitude):
    """``amplitude Custom`` (C++ ``CustomAmplitude``)."""

    keyword = "Custom"
    summary = "amplitude from an expression"

    expression_tag: int = Field(description="tag of an ``expression`` object")


class _Fourier(Amplitude):
    """Base of ``Modulated``/``Sine``/``Cosine`` sharing one C++ handler."""

    sp_abstract = True

    W: float = Field(description="parameter W")
    values: FloatList = Field(
        default_factory=list,
        description="modulation / harmonic coefficients",
    )


class Modulated(_Fourier):
    """``amplitude Modulated`` (C++ ``Modulated``).

    ``W * prod(sin(2 * pi * f_i * t))`` over the modulation frequencies
    ``f_i``.
    """

    keyword = "Modulated"
    summary = "modulated amplitude"


class Sine(_Fourier):
    """``amplitude Sine`` (C++ ``Sine``), period ``0.5 * W``."""

    keyword = "Sine"
    summary = "sine harmonic amplitude"


class Cosine(_Fourier):
    """``amplitude Cosine`` (C++ ``Cosine``), period ``0.5 * W``."""

    keyword = "Cosine"
    summary = "cosine harmonic amplitude"


class NZStrongMotion(Amplitude):
    """``amplitude NZStrongMotion`` (C++ ``NZStrongMotion``)."""

    keyword = "NZStrongMotion"
    summary = "predefined NZ strong-motion record"

    name: str = Field(description="name of the built-in record")


# --------------------------------------------------------------------------- #
# loads                                                                       #
# --------------------------------------------------------------------------- #
class Load(SuanpanObject):
    """Base class of loads respecting the shared argument layout.

    ``<TYPE> <tag> <amplitude tag> <magnitude> <dof> <tags...>``

    Loads attach to the step in which they are defined; a load defined
    before any step stays active in every step (start step zero).
    """

    command = "load"
    sp_abstract = True

    amplitude_tag: int = Field(description="tag of the applied amplitude")
    magnitude: float = Field(description="load magnitude")
    dof: DofToken = Field(description="dof identifier (may expand, e.g. E)")
    object_tags: IntList = Field(
        default_factory=list,
        description="tags of nodes/elements/groups the load applies to",
    )

    def to_commands(self) -> list[str]:
        parts = [self.command, self.keyword, *format_value(self.tag)]
        parts += [
            str(self.amplitude_tag),
            *format_value(self.magnitude),
            self.dof,
            *format_value(self.object_tags),
        ]
        return [" ".join(parts)]


class Acceleration(Load):
    """``load Acceleration`` (C++ ``NodalAcceleration``) -- nodal acceleration."""

    keyword = "Acceleration"
    summary = "prescribed nodal acceleration"


class BodyForce(Load):
    """``load BodyForce`` (C++ ``BodyForce``) -- body force on elements."""

    keyword = "BodyForce"
    summary = "body force over elements"


class Cload(Load):
    """``load Cload`` (C++ ``NodalForce``) -- concentrated nodal force."""

    keyword = "Cload"
    aliases = ("cload",)
    summary = "concentrated nodal force"


class Disp(Load):
    """``load Disp`` (C++ ``NodalDisplacement``) -- prescribed displacement."""

    keyword = "Disp"
    aliases = ("Displacement", "DispLoad")
    summary = "prescribed nodal displacement"


class GroupBodyForce(Load):
    """``load GroupBodyForce`` (C++ ``GroupBodyForce``) over element groups."""

    keyword = "GroupBodyForce"
    summary = "body force over element groups"


class GroupCload(Load):
    """``load GroupCload`` (C++ ``GroupNodalForce``) over node groups."""

    keyword = "GroupCload"
    summary = "concentrated nodal force over node groups"


class GroupDisp(Load):
    """``load GroupDisp`` (C++ ``GroupNodalDisplacement``) over node groups."""

    keyword = "GroupDisp"
    aliases = ("GroupDisplacement", "GroupDispLoad")
    summary = "prescribed nodal displacement over node groups"


class _LineUDL(Load):
    """Distributed line load over consecutive node segments."""

    sp_abstract = True

    @field_validator("dof")
    @classmethod
    def _single_dof(cls, value: str) -> str:
        from suanpan.toolbox.dof import parse_dof

        if len(parse_dof(value)) != 1:
            raise ValueError("LineUDL requires a token expanding to exactly one DOF")
        return value


class LineUDL2D(_LineUDL):
    """``load LineUDL2D`` (C++ ``LineUDL2D``).

    The DOF token must expand to exactly one DOF and node tags form
    consecutive line segments.
    """

    keyword = "LineUDL2D"
    summary = "2D line distributed load"


class LineUDL3D(_LineUDL):
    """``load LineUDL3D`` (C++ ``LineUDL3D``)."""

    keyword = "LineUDL3D"
    summary = "3D line distributed load"


class ReferenceLoad(Load):
    """``load ReferenceLoad`` (C++ ``ReferenceForce``).

    The amplitude tag is parsed but deliberately not forwarded to the
    object -- the load scales purely by the constraint multiplier.
    """

    keyword = "ReferenceLoad"
    aliases = ("RefLoad", "RefForce")
    summary = "reference load scaled by the constraint multiplier"


class GroupReferenceLoad(Load):
    """``load GroupReferenceLoad`` (C++ ``GroupReferenceForce``) over groups."""

    keyword = "GroupReferenceLoad"
    aliases = ("GroupRefLoad", "GroupRefForce")
    summary = "reference load over groups"


class SupportDisplacement(Load):
    """``load SupportDisplacement`` (C++ ``SupportDisplacement``)."""

    keyword = "SupportDisplacement"
    summary = "support motion of displacement type"


class SupportVelocity(Load):
    """``load SupportVelocity`` (C++ ``SupportVelocity``)."""

    keyword = "SupportVelocity"
    summary = "support motion of velocity type"


class SupportAcceleration(Load):
    """``load SupportAcceleration`` (C++ ``SupportAcceleration``)."""

    keyword = "SupportAcceleration"
    summary = "support motion of acceleration type"
