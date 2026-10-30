"""The whole suanPan model, mirroring the composition of a suanPan
domain: global pools of domain objects plus a sequence of analysis
steps.

Objects are exported in exactly the order the C++ parser consumes
commands:

    node, material, expression, section, element, amplitude, group,
    orientation, modifier, initial, mass, then the step-0 criteria /
    convergers / loads / recorders / constraints, followed by every step
    block (step line, ``set`` properties, then the step children).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from suanpan.base import SuanpanObject
from suanpan.constraint import Constraint, Criterion
from suanpan.converger import Converger
from suanpan.domain import (
    Expression,
    Group,
    InitialCondition,
    Modifier,
    NodalMass,
    Node,
    Orientation,
)
from suanpan.element import Element
from suanpan.load import Amplitude, Load
from suanpan.material import Material
from suanpan.recorder import Recorder
from suanpan.section import Section
from suanpan.step import Step, cell_commands

__all__ = ["Model"]


def _unique(kind: str, objects: list) -> None:
    seen: set[int] = set()
    for obj in objects:
        tag = getattr(obj, "tag", None)
        if tag is None:
            continue
        if tag in seen:
            raise ValueError(f"duplicate {kind} tag {tag}")
        seen.add(tag)


def _iter_all(obj: object):
    """Depth-first walk over pydantic sub-models of ``obj``."""
    if isinstance(obj, BaseModel):
        yield obj
        for name in type(obj).model_fields:
            value = getattr(obj, name, None)
            if isinstance(value, BaseModel):
                yield from _iter_all(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, BaseModel):
                        yield from _iter_all(item)


class Model(BaseModel):
    """A complete suanPan model.

    Every pool corresponds to one group of input commands; steps keep
    their order.  ``Model`` itself is not an input command object -- it
    is the container composing all of them.
    """

    model_config = {"validate_assignment": True, "extra": "forbid"}

    title: str = Field(default="", description="title written as a comment")
    nodes: list[Node] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    expressions: list[Expression] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    amplitudes: list[Amplitude] = Field(default_factory=list)
    groups: list[Group] = Field(default_factory=list)
    orientations: list[Orientation] = Field(default_factory=list)
    modifiers: list[Modifier] = Field(default_factory=list)
    initials: list[InitialCondition] = Field(default_factory=list)
    masses: list[NodalMass] = Field(default_factory=list)
    #: criterion of the ``criterion`` command defined before any step
    criteria: list[Criterion] = Field(default_factory=list)
    #: convergers defined before any step
    convergers: list[Converger] = Field(default_factory=list)
    #: loads defined before any step stay active in every step
    loads: list[Load] = Field(default_factory=list)
    #: recorders defined before any step
    recorders: list[Recorder] = Field(default_factory=list)
    #: constraints defined before any step
    constraints: list[Constraint] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_references(self) -> Model:
        pools = (
            ("node", self.nodes),
            ("material", self.materials),
            ("expression", self.expressions),
            ("section", self.sections),
            ("element", self.elements),
            ("amplitude", self.amplitudes),
            ("group", self.groups),
            ("orientation", self.orientations),
            ("modifier", self.modifiers),
        )
        for kind, pool in pools:
            _unique(kind, pool)
        _unique("step", self.steps)
        for kind, pool in (
            ("load", self.loads),
            ("recorder", self.recorders),
            ("criterion", self.criteria),
            ("converger", self.convergers),
        ):
            _unique(kind, pool)
        _unique("constraint", self.constraints)

        material_tags = {m.tag for m in self.materials}
        section_tags = {s.tag for s in self.sections}
        element_tags = {e.tag for e in self.elements}
        amplitude_tags = {a.tag for a in self.amplitudes} | {0}
        expression_tags = {e.tag for e in self.expressions}

        def check(
            tag_owner: SuanpanObject,
            field_name: str,
            tag: int | None,
            known: set[int],
            kind: str,
        ) -> None:
            if tag is None or tag in known:
                return
            owner = getattr(tag_owner, "tag", "?")
            raise ValueError(
                f"{type(tag_owner).__name__} {owner} references missing {kind} {tag}"
            )

        for section in self.sections:
            check(
                section,
                "material_tag",
                getattr(section, "material_tag", None),
                material_tags,
                "material",
            )
        for element in self.elements:
            check(
                element,
                "material_tag",
                getattr(element, "material_tag", None),
                material_tags,
                "material",
            )
            check(
                element,
                "section_tag",
                getattr(element, "section_tag", None),
                section_tags,
                "section",
            )
        for pool in (
            *self.loads,
            *(load for step in self.steps for load in step.loads),
        ):
            check(
                pool,
                "amplitude_tag",
                getattr(pool, "amplitude_tag", None),
                amplitude_tags,
                "amplitude",
            )
        for amplitude in self.amplitudes:
            check(
                amplitude,
                "expression_tag",
                getattr(amplitude, "expression_tag", None),
                expression_tags,
                "expression",
            )
        for modifier in self.modifiers:
            for tag in getattr(modifier, "element_tags", []):
                if tag not in element_tags:
                    raise ValueError(
                        f"modifier {modifier.tag} references missing element {tag}"
                    )
            ref = getattr(modifier, "element_tag", None)
            if ref is not None and ref not in element_tags:
                raise ValueError(
                    f"modifier {modifier.tag} references missing element {ref}"
                )
        for constraint in self.constraints:
            ref = getattr(constraint, "element_tag", None)
            if ref is not None and ref not in element_tags:
                raise ValueError(
                    f"constraint {constraint.tag} references missing element {ref}"
                )
        return self

    def _all_objects(self) -> list[SuanpanObject]:
        collected: list[SuanpanObject] = []
        for pool in (
            *self.nodes,
            *self.materials,
            *self.expressions,
            *self.sections,
            *self.elements,
            *self.amplitudes,
            *self.groups,
            *self.orientations,
            *self.modifiers,
            *(c for step in self.steps for c in step.constraints),
            *self.constraints,
        ):
            collected.extend(_iter_all(pool))
        return collected

    # ------------------------------------------------------------------ #
    # builder helpers                                                    #
    # ------------------------------------------------------------------ #
    def add(self, obj: SuanpanObject) -> SuanpanObject:
        """Append ``obj`` to the matching pool and return it."""
        pools = (
            ("nodes", Node),
            ("materials", Material),
            ("expressions", Expression),
            ("sections", Section),
            ("elements", Element),
            ("amplitudes", Amplitude),
            ("groups", Group),
            ("orientations", Orientation),
            ("modifiers", Modifier),
            ("initials", InitialCondition),
            ("masses", NodalMass),
            ("criteria", Criterion),
            ("convergers", Converger),
            ("loads", Load),
            ("recorders", Recorder),
            ("constraints", Constraint),
        )
        for name, kind in pools:
            if isinstance(obj, kind):
                getattr(self, name).append(obj)
                return obj
        if isinstance(obj, Step):
            self.steps.append(obj)
            return obj
        raise TypeError(f"cannot add object of type {type(obj).__name__}")

    def step(self, step: Step) -> Step:
        """Append a step and return it."""
        return self.add(step)

    # ------------------------------------------------------------------ #
    # export                                                             #
    # ------------------------------------------------------------------ #
    def to_commands(self) -> list[str]:
        """Export the model as a list of command lines."""
        commands: list[str] = []
        if self.title:
            commands.append(f"# {self.title}")

        def _add(objects) -> None:
            for obj in objects:
                commands.extend(obj.to_commands())

        _add(self.nodes)
        _add(self.materials)
        _add(self.expressions)
        _add(self.sections)
        _add(self.elements)
        _add(self.amplitudes)
        _add(self.groups)
        _add(self.orientations)
        _add(self.modifiers)
        _add(self.initials)
        _add(self.masses)
        _add(self.criteria)
        _add(self.convergers)
        _add(self.loads)
        _add(self.recorders)
        _add(self.constraints)
        for step in self.steps:
            commands.extend(cell_commands(step))
        return commands

    def export_text(self) -> str:
        """Export the model as the text of a ``.supan`` input file."""
        return "\n".join(self.to_commands()) + "\n"

    def save(self, path: str | Path) -> Path:
        """Write the model to an input file and return its path."""
        path = Path(path)
        path.write_text(self.export_text())
        return path
