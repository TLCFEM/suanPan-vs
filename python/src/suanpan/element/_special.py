"""Hand written element classes for handlers using an option loop with
repeatable value lists (``-node``/``-knotx``/...).
"""

from __future__ import annotations

from pydantic import Field

from suanpan.element._generated import Element
from suanpan.toolbox.format import FloatList, IntList


def _flag_list(tokens: list[str], flag: str, values: list) -> None:
    if not values:
        return
    tokens.append(flag)
    if isinstance(values[0], (list, tuple)):
        for group in values:
            tokens.extend(str(v) for v in group)
    else:
        tokens.extend(str(v) for v in values)


class _Patch(Element):
    """Base of ``PatchQuad``/``PatchCube`` (option loop of the patch
    elements mirroring ``new_patchquad``)."""

    sp_abstract = True

    node_tags: IntList = Field(description="node tags (mandatory)")
    knot_x: FloatList = Field(description="x positions of the control knots")
    knot_y: FloatList = Field(description="y positions of the control knots")
    material_tag: int = Field(description="material tag (mandatory)")


class PatchQuad(_Patch):
    """``element PatchQuad`` (C++ ``PatchQuad``), 2D patch defined by knots."""

    keyword = "PatchQuad"
    summary = "2D patch element"

    thickness: float = Field(default=1.0, description="thickness (default one)")

    def to_commands(self) -> list[str]:
        tokens = [self.command, self.keyword, str(self.tag)]
        entries = [
            ("-node", list(self.node_tags)),
            ("-knotx", list(self.knot_x)),
            ("-knoty", list(self.knot_y)),
            ("-material", [self.material_tag]),
        ]
        if self.thickness != 1.0:
            entries.append(("-thickness", [self.thickness]))
        for flag, values in entries:
            _flag_list(tokens, flag, values)
        return [" ".join(tokens)]


class PatchCube(_Patch):
    """``element PatchCube`` (C++ ``PatchCube``), 3D patch defined by knots."""

    keyword = "PatchCube"
    summary = "3D patch element"

    knot_z: FloatList = Field(description="z positions of the control knots")

    def to_commands(self) -> list[str]:
        tokens = [self.command, self.keyword, str(self.tag)]
        for flag, values in (
            ("-node", list(self.node_tags)),
            ("-knotx", list(self.knot_x)),
            ("-knoty", list(self.knot_y)),
            ("-knotz", list(self.knot_z)),
            ("-material", [self.material_tag]),
        ):
            _flag_list(tokens, flag, values)
        return [" ".join(tokens)]
