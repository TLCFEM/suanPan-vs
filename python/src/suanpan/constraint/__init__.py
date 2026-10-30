"""Constraints, criteria and interactions, mirroring
``Constraint/ConstraintParser.cpp`` (the ``constraint``, ``criterion`` and
``interaction`` command families).

Constraints attach to the step in which they are defined; a constraint
defined before any step stays active in every step (start step zero).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

from suanpan.base import SuanpanObject, format_float, format_value
from suanpan.recorder import validate_output_token
from suanpan.toolbox.dof import DofToken, parse_dof
from suanpan.toolbox.format import FloatList, IntList

__all__ = [
    "MPC",
    "Constraint",
    "Criterion",
    "Embed2D",
    "Embed3D",
    "FiniteRestitutionWallPenalty",
    "FiniteRigidWallMultiplier",
    "FiniteRigidWallPenalty",
    "Fix",
    "Fix2",
    "FixedLength2D",
    "FixedLength3D",
    "FixedParticle",
    "GroupMultiplierBC",
    "GroupPenaltyBC",
    "Hertzian",
    "Interaction",
    "LJPotential2D",
    "LinearSpring2D",
    "LogicCriteriaAll",
    "LogicCriteriaAny",
    "MPCNode",
    "MaxDisplacement",
    "MaxHistory",
    "MaxResistance",
    "MaximumForce2D",
    "MaximumForce3D",
    "MaximumGap2D",
    "MaximumGap3D",
    "MinDisplacement",
    "MinHistory",
    "MinResistance",
    "MinimumGap2D",
    "MinimumGap3D",
    "MolecularDynamics2D",
    "MolecularDynamics3D",
    "MultiplierBC",
    "NodeFacet",
    "NodeLine",
    "ParticleCollision2D",
    "ParticleCollision3D",
    "PenaltyBC",
    "RestitutionWallPenalty",
    "RigidWallMultiplier",
    "RigidWallPenalty",
    "Sleeve2D",
    "Sleeve3D",
    "StrainEnergyEvolution",
]


def _f(value: float) -> str:
    return format_float(value)


def _tokens(*values: object) -> list[str]:
    parts: list[str] = []
    for value in values:
        if isinstance(value, bool):
            parts.append("true" if value else "false")
        elif value is None:
            continue
        elif isinstance(value, (int, float)):
            parts.append(_f(value))
        elif isinstance(value, str):
            parts.append(value)
        else:
            parts.extend(format_value(value))
    return parts


class Constraint(SuanpanObject):
    """Base class of all constraints (``constraint`` command)."""

    command = "constraint"
    sp_abstract = True


class Criterion(SuanpanObject):
    """Base class of criteria (``criterion`` command)."""

    command = "criterion"
    sp_abstract = True


class Interaction(SuanpanObject):
    """Base class of interactions (``interaction`` command)."""

    command = "interaction"
    sp_abstract = True


# --------------------------------------------------------------------------- #
# boundary conditions                                                         #
# --------------------------------------------------------------------------- #
class _BC(Constraint):
    """``constraint <TYPE> <tag> <dof> <nodes...>``."""

    sp_abstract = True

    dof: DofToken = Field(description="dof identifier (may expand, e.g. E)")
    node_tags: IntList = Field(
        default_factory=list, description="constrained node tags"
    )

    @field_validator("dof")
    @classmethod
    def _check_dof(cls, value: str) -> str:
        if not parse_dof(value):
            raise ValueError(f"unknown dof identifier {value!r}")
        return value

    def to_commands(self) -> list[str]:
        parts = ["constraint", self.keyword, *format_value(self.tag), self.dof]
        parts += format_value(self.node_tags)
        return [" ".join(parts)]


class Fix(_BC):
    """``constraint Fix`` (C++ ``PenaltyBC``) -- penalty based BC."""

    keyword = "Fix"
    aliases = ("PenaltyBC",)
    summary = "penalty based boundary condition"


class Fix2(_BC):
    """``constraint Fix2`` (C++ ``MultiplierBC``) -- multiplier based BC."""

    keyword = "Fix2"
    aliases = ("MultiplierBC",)
    summary = "multiplier based boundary condition"


class GroupPenaltyBC(_BC):
    """``constraint GroupPenaltyBC`` -- penalty BC over node groups."""

    keyword = "GroupPenaltyBC"
    summary = "penalty based boundary condition over node groups"


class GroupMultiplierBC(_BC):
    """``constraint GroupMultiplierBC`` -- multiplier BC over node groups."""

    keyword = "GroupMultiplierBC"
    summary = "multiplier based boundary condition over node groups"


# keep the C++ class names importable
PenaltyBC = Fix
MultiplierBC = Fix2


class Embed2D(Constraint):
    """``constraint Embed2D <tag> <element> <node>`` (C++ ``Embed<2>``)."""

    keyword = "Embed2D"
    summary = "embed a node into a 2D element"

    element_tag: int = Field(description="host element tag")
    node_tag: int = Field(description="embedded node tag")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "constraint",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.element_tag),
                    str(self.node_tag),
                ]
            )
        ]


class Embed3D(Embed2D):
    """``constraint Embed3D`` (C++ ``Embed<3>``)."""

    keyword = "Embed3D"
    summary = "embed a node into a 3D element"


class FixedLength2D(Constraint):
    """``constraint FixedLength2D <tag> <node_i> <node_j>`` (C++ ``FixedLength<2>``)."""

    keyword = "FixedLength2D"
    aliases = ("R2D2",)
    summary = "maintain the distance between two nodes in 2D"

    node_i: int = Field(description="first node tag")
    node_j: int = Field(description="second node tag")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "constraint",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.node_i),
                    str(self.node_j),
                ]
            )
        ]


class FixedLength3D(FixedLength2D):
    """``constraint FixedLength3D`` (C++ ``FixedLength<3>``)."""

    keyword = "FixedLength3D"
    aliases = ("R3D2",)
    summary = "maintain the distance between two nodes in 3D"


class _TwoNodes(Constraint):
    """Constraints parameterised by two nodes and one float."""

    sp_abstract = True

    node_i: int = Field(description="first node tag")
    node_j: int = Field(description="second node tag")
    value: float = Field(description="limiting value")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "constraint",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.node_i),
                    str(self.node_j),
                    _f(self.value),
                ]
            )
        ]


class _TwoNodesOnly(Constraint):
    """Constraints parameterised by two nodes with no extra parameter."""

    sp_abstract = True

    node_i: int = Field(description="first node tag")
    node_j: int = Field(description="second node tag")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "constraint",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.node_i),
                    str(self.node_j),
                ]
            )
        ]


class MaximumForce2D(_TwoNodes):
    """``constraint MaximumForce2D`` (C++ ``MaxForce<2>``)."""

    keyword = "MaximumForce2D"
    aliases = ("MaxForce2D",)
    summary = "limit the force between two nodes in 2D"

    value: float = Field(description="maximum force")


class MaximumForce3D(MaximumForce2D):
    """``constraint MaximumForce3D`` (C++ ``MaxForce<3>``)."""

    keyword = "MaximumForce3D"
    aliases = ("MaxForce3D",)
    summary = "limit the force between two nodes in 3D"


class MaximumGap2D(_TwoNodes):
    """``constraint MaximumGap2D`` (C++ ``MaximumGap<2>``)."""

    keyword = "MaximumGap2D"
    aliases = ("MaxGap2D",)
    summary = "maximum allowed gap between two nodes in 2D"

    value: float = Field(description="maximum gap")


class MaximumGap3D(MaximumGap2D):
    """``constraint MaximumGap3D`` (C++ ``MaximumGap<3>``)."""

    keyword = "MaximumGap3D"
    aliases = ("MaxGap3D",)
    summary = "maximum allowed gap between two nodes in 3D"


class MinimumGap2D(_TwoNodes):
    """``constraint MinimumGap2D`` (C++ ``MinimumGap<2>``)."""

    keyword = "MinimumGap2D"
    aliases = ("MinGap2D",)
    summary = "minimum allowed gap between two nodes in 2D"

    value: float = Field(description="minimum gap")


class MinimumGap3D(MinimumGap2D):
    """``constraint MinimumGap3D`` (C++ ``MinimumGap<3>``)."""

    keyword = "MinimumGap3D"
    aliases = ("MinGap3D",)
    summary = "minimum allowed gap between two nodes in 3D"


class _SpaceAlpha(Constraint):
    """``constraint <TYPE> <tag> [space] [alpha]`` with defaults of one."""

    sp_abstract = True

    space: float = Field(default=1.0, description="characteristic space (default one)")
    alpha: float = Field(default=1.0, description="alpha parameter (default one)")

    def to_commands(self) -> list[str]:
        parts = ["constraint", self.keyword, *format_value(self.tag)]
        # space/alpha are optional in the parser; export only when meaningful
        if self.space != 1.0 or self.alpha != 1.0:
            parts.append(_f(self.space))
            parts.append(_f(self.alpha))
        return [" ".join(parts)]


class LinearSpring2D(_SpaceAlpha):
    """``constraint LinearSpring2D`` (C++ ``LinearSpring2D``)."""

    keyword = "LinearSpring2D"
    summary = "linear spring between particles in 2D"


class LJPotential2D(_SpaceAlpha):
    """``constraint LJPotential2D`` (C++ ``LJPotential2D``)."""

    keyword = "LJPotential2D"
    summary = "Lennard-Jones potential in 2D"


class ParticleCollision2D(_SpaceAlpha):
    """``constraint ParticleCollision2D`` (C++ ``ParticleCollision2D``)."""

    keyword = "ParticleCollision2D"
    summary = "particle-particle collision in 2D"


class ParticleCollision3D(ParticleCollision2D):
    """``constraint ParticleCollision3D`` (C++ ``ParticleCollision3D``)."""

    keyword = "ParticleCollision3D"
    summary = "particle-particle collision in 3D"


class _MD(Constraint):
    """``constraint MolecularDynamics<2|3>D <tag> [nodes...]``."""

    sp_abstract = True

    node_tags: IntList = Field(
        default_factory=list, description="participating node tags"
    )

    def to_commands(self) -> list[str]:
        parts = ["constraint", self.keyword, *format_value(self.tag)]
        parts += format_value(self.node_tags)
        return [" ".join(parts)]


class MolecularDynamics2D(_MD):
    """``constraint MolecularDynamics2D`` (C++ ``MolecularDynamics2D``)."""

    keyword = "MolecularDynamics2D"
    summary = "molecular dynamics in 2D"


class MolecularDynamics3D(_MD):
    """``constraint MolecularDynamics3D`` (C++ ``MolecularDynamics3D``)."""

    keyword = "MolecularDynamics3D"
    summary = "molecular dynamics in 3D"


class NodeFacet(Constraint):
    """``constraint NodeFacet <tag> <4 node tags>`` (C++ ``NodeFacet``)."""

    keyword = "NodeFacet"
    summary = "constrain a node on a facet of four nodes"

    node_tags: IntList = Field(description="exactly four node tags")

    @field_validator("node_tags")
    @classmethod
    def _check_count(cls, value: IntList) -> IntList:
        if len(value) != 4:
            raise ValueError("NodeFacet requires exactly four node tags")
        return value


class NodeLine(Constraint):
    """``constraint NodeLine <tag> <3 node tags>`` (C++ ``NodeLine``)."""

    keyword = "NodeLine"
    summary = "constrain a node on a line of three nodes"

    node_tags: IntList = Field(description="exactly three node tags")

    @field_validator("node_tags")
    @classmethod
    def _check_count(cls, value: IntList) -> IntList:
        if len(value) != 3:
            raise ValueError("NodeLine requires exactly three node tags")
        return value


class Sleeve2D(Constraint):
    """``constraint Sleeve2D <tag> <i> <j> <min> <max>`` (C++ ``Sleeve<2>``)."""

    keyword = "Sleeve2D"
    summary = "gap range sleeve between two nodes in 2D"

    node_i: int = Field(description="first node tag")
    node_j: int = Field(description="second node tag")
    min_gap: float = Field(description="minimum gap")
    max_gap: float = Field(description="maximum gap")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "constraint",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.node_i),
                    str(self.node_j),
                    _f(self.min_gap),
                    _f(self.max_gap),
                ]
            )
        ]


class Sleeve3D(Sleeve2D):
    """``constraint Sleeve3D`` (C++ ``Sleeve<3>``)."""

    keyword = "Sleeve3D"
    summary = "gap range sleeve between two nodes in 3D"


class MPCNode(BaseModel):
    """One ``(node, dof, weight)`` triple of a multipoint constraint."""

    model_config = {"validate_assignment": True}

    node: int = Field(description="node tag")
    dof: DofToken = Field(description="dof identifier (single dof)")
    weight: float = Field(description="constraint weight")

    @field_validator("dof")
    @classmethod
    def _check_single(cls, value: str) -> str:
        pool = parse_dof(value)
        if len(pool) != 1:
            raise ValueError(f"dof {value!r} must expand to exactly one dof")
        return value

    def to_tokens(self) -> list[str]:
        return [str(self.node), self.dof, format_float(self.weight)]


class MPC(Constraint):
    """``constraint MPC <tag> <amplitude> <magnitude> <triples...>``."""

    keyword = "MPC"
    summary = "multipoint constraint"

    amplitude: int = Field(description="tag of the applied amplitude")
    magnitude: float = Field(description="constraint magnitude")
    nodes: list[MPCNode] = Field(
        default_factory=list, description="repeated (node, dof, weight) triples"
    )

    def to_commands(self) -> list[str]:
        parts = [
            "constraint",
            "MPC",
            *format_value(self.tag),
            str(self.amplitude),
            _f(self.magnitude),
        ]
        for entry in self.nodes:
            parts += entry.to_tokens()
        return [" ".join(parts)]


# --------------------------------------------------------------------------- #
# rigid world walls (variable length)                                         #
# --------------------------------------------------------------------------- #
class _Wall(Constraint):
    """Base of the variable length wall families.

    The C++ parser consumes all remaining floats and selects the wall
    dimension by the parameter count; a trailing penalty/restoration
    factor of ``1E4`` is appended automatically when the raw count is
    ``2/4/6/9`` (rigid walls) or ``3/5/7/10`` (restitution walls).

    ``parameters`` stores the raw user values; the count is validated to
    be either a raw count (auto alpha) or the corresponding final count
    (explicit alpha).  The values are exported verbatim, so re-parsing
    the exported line yields the identical object.
    """

    sp_abstract = True
    #: raw counts triggering the automatic trailing value
    raw_counts: ClassVar[tuple[int, ...]] = ()
    #: corresponding total counts including the trailing value
    final_counts: ClassVar[tuple[int, ...]] = ()

    parameters: FloatList = Field(description="wall parameters (by count)")

    @model_validator(mode="after")
    def check_count(self) -> _Wall:
        count = len(self.parameters)
        if count not in self.raw_counts + self.final_counts:
            raise ValueError(
                f"{type(self).__name__} requires the parameter count to be one of "
                f"{sorted(set(self.raw_counts + self.final_counts))}, got {count}"
            )
        return self

    @property
    def dimension(self) -> int:
        """Inferred wall dimension (1, 2 or 3)."""
        counts = {3: 1, 5: 2, 7: 3, 10: 3, 4: 1, 6: 2, 8: 3, 11: 3, 2: 1, 9: 3}
        return counts[len(self.parameters)]

    def to_commands(self) -> list[str]:
        parts = ["constraint", self.keyword, *format_value(self.tag)]
        parts += [_f(v) for v in self.parameters]
        return [" ".join(parts)]


class RigidWallPenalty(_Wall):
    """``constraint RigidWall`` (C++ ``RigidWallPenalty1D/2D/3D``).

    The 2D five-value form uses the normal vector; the ten-value form
    adds the edge vector.  ``finite`` is false.
    """

    keyword = "RigidWall"
    aliases = ("RigidWallPenalty",)
    summary = "rigid wall penalty by parameter count"
    raw_counts = (2, 4, 6, 9)
    final_counts = (3, 5, 7, 10)


class FiniteRigidWallPenalty(RigidWallPenalty):
    """``constraint FiniteRigidWall`` (C++ ``RigidWallPenalty1D/2D/3D``).

    Same layout; the 2D five-value form uses the edge vector instead of
    the normal vector.  ``finite`` is true.
    """

    keyword = "FiniteRigidWall"
    aliases = ("FiniteRigidWallPenalty",)
    summary = "finite rigid wall penalty by parameter count"


class RigidWallMultiplier(RigidWallPenalty):
    """``constraint RigidWallMultiplier`` (C++ ``RigidWallMultiplier1D/2D/3D``).

    Lagrange multiplier variant of the rigid wall.
    """

    keyword = "RigidWallMultiplier"
    aliases = ()
    summary = "rigid wall multiplier by parameter count"


class FiniteRigidWallMultiplier(FiniteRigidWallPenalty):
    """``constraint FiniteRigidWallMultiplier`` (C++ ``RigidWallMultiplier1D/2D/3D``)."""

    keyword = "FiniteRigidWallMultiplier"
    aliases = ()
    summary = "finite rigid wall multiplier by parameter count"


class RestitutionWallPenalty(_Wall):
    """``constraint RestitutionWall`` (C++ ``RestitutionWallPenalty1D/2D/3D``).

    Restitution coefficient clamped to ``[0, 1]``; usable in dynamic
    analyses only.
    """

    keyword = "RestitutionWall"
    aliases = ("RestitutionWallPenalty",)
    summary = "restitution wall penalty by parameter count"
    raw_counts = (3, 5, 7, 10)
    final_counts = (4, 6, 8, 11)

    @model_validator(mode="after")
    def clamp_rc(self) -> RestitutionWallPenalty:
        # RC is the second to last value when alpha is explicit, else the
        # last (auto appended).  Clamp the value to [0, 1] in both cases.
        if self.parameters:
            index = -2 if len(self.parameters) in self.final_counts else -1
            rc = self.parameters[index]
            if not 0.0 <= rc <= 1.0:
                values = list(self.parameters)
                values[index] = max(0.0, min(1.0, rc))
                self.parameters = values
        return self


class FiniteRestitutionWallPenalty(RestitutionWallPenalty):
    """``constraint FiniteRestitutionWall`` (C++ ``RestitutionWallPenalty1D/2D/3D``)."""

    keyword = "FiniteRestitutionWall"
    aliases = ("FiniteRestitutionWallPenalty",)
    summary = "finite restitution wall penalty by parameter count"


# --------------------------------------------------------------------------- #
# criteria                                                                    #
# --------------------------------------------------------------------------- #
class LogicCriteriaAll(Criterion):
    """``criterion LogicAll`` (C++ ``LogicCriterionAll``)."""

    keyword = "LogicAll"
    aliases = ("LogicCriterionAll",)
    summary = "criterion satisfied when all listed criteria are met"

    criterion_tags: IntList = Field(
        description="tags of the criteria to combine (at least one)"
    )

    @field_validator("criterion_tags")
    @classmethod
    def _check_tags(cls, value: IntList) -> IntList:
        if not value:
            raise ValueError("LogicAll requires at least one criterion tag")
        return value

    def to_commands(self) -> list[str]:
        parts = ["criterion", self.keyword, *format_value(self.tag)]
        parts += format_value(self.criterion_tags)
        return [" ".join(parts)]


class LogicCriteriaAny(Criterion):
    """``criterion LogicAny`` (C++ ``LogicCriterionAny``)."""

    keyword = "LogicAny"
    aliases = ("LogicCriterionAny",)
    summary = "criterion satisfied when any listed criterion is met"

    criterion_tags: IntList = Field(
        description="tags of the criteria to combine (at least one)"
    )

    @field_validator("criterion_tags")
    @classmethod
    def _check_tags(cls, value: IntList) -> IntList:
        if not value:
            raise ValueError("LogicAny requires at least one criterion tag")
        return value

    def to_commands(self) -> list[str]:
        parts = ["criterion", self.keyword, *format_value(self.tag)]
        parts += format_value(self.criterion_tags)
        return [" ".join(parts)]


class StrainEnergyEvolution(Criterion):
    """``criterion StrainEnergyEvolution`` (phase field fracture)."""

    keyword = "StrainEnergyEvolution"
    summary = "strain energy evolution criterion"

    incre_level: int = Field(description="increment level")
    final_level: int = Field(description="final level")
    weight: float = Field(default=1.0, description="weight of central element")
    iteration: int = Field(default=2, description="number of iterations")
    reactivation: int = Field(default=10, description="reactivation ratio")
    propagation: float = Field(default=0.5, description="propagation factor")
    tolerance: float = Field(default=1e-5, description="tolerance")

    def to_commands(self) -> list[str]:
        parts = [
            "criterion",
            self.keyword,
            *format_value(self.tag),
            str(self.incre_level),
            str(self.final_level),
        ]
        optional = (
            self.weight,
            self.iteration,
            self.reactivation,
            self.propagation,
            self.tolerance,
        )
        defaults = (1.0, 2, 10, 0.5, 1e-5)
        # export trailing optional parameters while they deviate from / or
        # precede a non-default value
        last = 0
        for index, (value, default) in enumerate(zip(optional, defaults, strict=True)):
            if value != default:
                last = index + 1
        for value in optional[:last]:
            parts.append(_f(value))
        return [" ".join(parts)]


class _HistoryCriterion(Criterion):
    """Base of ``MaxHistory``/``MinHistory``."""

    sp_abstract = True

    variable: str = Field(description="recorder variable token, see OutputType")
    limit: float = Field(description="limit of the recorded quantity")
    element_tags: IntList = Field(default_factory=list, description="element tags")

    @field_validator("variable")
    @classmethod
    def _check_variable(cls, value: str) -> str:
        return validate_output_token(value)

    def to_commands(self) -> list[str]:
        parts = [
            "criterion",
            type(self).keyword,
            *format_value(self.tag),
            self.variable,
            _f(self.limit),
        ]
        parts += format_value(self.element_tags)
        return [" ".join(parts)]


class MaxHistory(_HistoryCriterion):
    """``criterion MaxHistory`` (C++ ``MaxHistory``)."""

    keyword = "MaxHistory"
    summary = "disable elements exceeding a recorded maximum"


class MinHistory(_HistoryCriterion):
    """``criterion MinHistory`` (C++ ``MinHistory``)."""

    keyword = "MinHistory"
    summary = "disable elements falling below a recorded minimum"


class _NodeLimitCriterion(Criterion):
    """``criterion <TYPE> <tag> <node> <dof> <limit>`` (single dof)."""

    sp_abstract = True

    node: int = Field(description="observed node tag")
    dof: DofToken = Field(description="dof identifier (single dof)")
    limit: float = Field(description="limiting value")

    @field_validator("dof")
    @classmethod
    def _check_single(cls, value: str) -> str:
        pool = parse_dof(value)
        if len(pool) != 1:
            raise ValueError(f"dof {value!r} must expand to exactly one dof")
        return value

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    "criterion",
                    type(self).keyword,
                    *format_value(self.tag),
                    str(self.node),
                    self.dof,
                    _f(self.limit),
                ]
            )
        ]


class MaxDisplacement(_NodeLimitCriterion):
    """``criterion MaxDisplacement`` (C++ ``MaxDisplacement``)."""

    keyword = "MaxDisplacement"
    summary = "disable analysis when displacement exceeds the limit"


class MinDisplacement(_NodeLimitCriterion):
    """``criterion MinDisplacement`` (C++ ``MinDisplacement``)."""

    keyword = "MinDisplacement"
    summary = "disable analysis when displacement falls below the limit"


class MaxResistance(_NodeLimitCriterion):
    """``criterion MaxResistance`` (C++ ``MaxResistance``)."""

    keyword = "MaxResistance"
    summary = "disable analysis when resistance exceeds the limit"


class MinResistance(_NodeLimitCriterion):
    """``criterion MinResistance`` (C++ ``MinResistance``)."""

    keyword = "MinResistance"
    summary = "disable analysis when resistance falls below the limit"


# --------------------------------------------------------------------------- #
# interactions                                                                #
# --------------------------------------------------------------------------- #
class Hertzian(Interaction):
    """``interaction Hertzian <tag>`` (C++ ``Hertzian``)."""

    keyword = "Hertzian"
    summary = "Hertzian contact interaction"

    def to_commands(self) -> list[str]:
        return [" ".join(["interaction", "Hertzian", *format_value(self.tag)])]


class FixedParticle(Interaction):
    """``interaction FixedParticle <tag> <multiplier> [nodes...]``."""

    keyword = "FixedParticle"
    summary = "fix a set of particles with a multiplier"

    multiplier: float = Field(description="constraint multiplier")
    node_tags: IntList = Field(default_factory=list, description="particle node tags")

    def to_commands(self) -> list[str]:
        parts = [
            "interaction",
            "FixedParticle",
            *format_value(self.tag),
            _f(self.multiplier),
        ]
        parts += format_value(self.node_tags)
        return [" ".join(parts)]
