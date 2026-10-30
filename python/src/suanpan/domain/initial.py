"""Initial conditions, mirroring ``create_new_initial`` in
``Toolbox/command.cpp`` (the ``initial`` command).

Initial conditions set nodal state before the analysis starts.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from suanpan.base import SuanpanObject, format_value
from suanpan.toolbox.format import FloatList, IntList

__all__ = [
    "InitialAcceleration",
    "InitialAngularVelocity",
    "InitialCondition",
    "InitialDisplacement",
    "InitialMaterialHistory",
    "InitialVelocity",
]


class InitialCondition(SuanpanObject):
    """Base class of initial conditions (``initial`` command).

    The ``initial`` command carries no object tag -- it describes a state
    mutation rather than a domain object.  ``tag`` is still accepted (and
    defaults to zero) so the class fits the object model, but it is never
    exported by the concrete subclasses.  The parser stores initial
    conditions as an ordered list.
    """

    command = "initial"
    sp_abstract = True

    tag: int = Field(default=0, description="unused, not exported")

    def to_commands(self) -> list[str]:
        raise NotImplementedError(
            f"{type(self).__name__} is abstract; use InitialDisplacement, "
            "InitialVelocity, ... "
        )


class _Nodal(InitialCondition):
    """Common shape of point-wise nodal initial conditions."""

    magnitude: float = Field(description="magnitude of the initial value")
    dof: int = Field(ge=1, description="dof identifier (one-based)")
    node_tags: IntList = Field(default_factory=list, description="node tags")

    def to_commands(self) -> list[str]:
        parts = ["initial", self.keyword]
        parts += [
            _f(self.magnitude),
            str(self.dof),
            *format_value(self.node_tags),
        ]
        return [" ".join(parts)]


def _f(value: float) -> str:
    from suanpan.base import format_float

    return format_float(value)


class InitialDisplacement(_Nodal):
    """``initial disp``/``initial displacement``."""

    keyword = "disp"
    aliases = ("displacement",)
    summary = "initial nodal displacement"


class InitialVelocity(_Nodal):
    """``initial vel``/``initial velocity``."""

    keyword = "vel"
    aliases = ("velocity",)
    summary = "initial nodal velocity"


class InitialAcceleration(_Nodal):
    """``initial acc``/``initial acceleration``."""

    keyword = "acc"
    aliases = ("acceleration",)
    summary = "initial nodal acceleration"


class InitialAngularVelocity(InitialCondition):
    """``initial avel``/``initial angularvelocity``.

    Every listed node receives ``magnitude x (coor - reference)`` as its
    initial velocity; the reference node coordinate must be resolvable when
    the model is validated.
    """

    keyword = "avel"
    aliases = ("angularvelocity",)
    summary = "initial angular velocity about a reference node"

    magnitude: FloatList = Field(description="angular velocity vector (3 components)")
    reference_node: int = Field(description="reference node tag")
    node_tags: IntList = Field(default_factory=list, description="node tags")

    @field_validator("magnitude")
    @classmethod
    def _check_vector(cls, value: FloatList) -> FloatList:
        if len(value) != 3:
            raise ValueError("angular velocity requires exactly three components")
        return value

    def to_commands(self) -> list[str]:
        parts = ["initial", self.keyword]
        parts += [_f(v) for v in self.magnitude]
        parts += [str(self.reference_node), *format_value(self.node_tags)]
        return [" ".join(parts)]


class InitialMaterialHistory(InitialCondition):
    """``initial material history`` sets the initial history of a material."""

    keyword = "material"
    summary = "initial material history"

    material_tag: int = Field(description="material tag")
    history: FloatList = Field(
        default_factory=list, description="initial history parameters"
    )

    def to_commands(self) -> list[str]:
        parts = ["initial", "history"]
        parts += [str(self.material_tag), *format_value(self.history)]
        return [" ".join(parts)]
