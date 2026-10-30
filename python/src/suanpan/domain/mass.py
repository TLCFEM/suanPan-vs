"""Nodal masses, mirroring ``create_new_mass`` in ``Element/ElementParser.cpp``
(the ``mass`` command always builds a ``Mass3D`` element)."""

from __future__ import annotations

from pydantic import Field

from suanpan.base import SuanpanObject
from suanpan.toolbox.dof import DofToken

__all__ = ["NodalMass"]


class NodalMass(SuanpanObject):
    """The ``mass`` command (C++ class ``Mass3D``)."""

    command = "mass"
    keyword = "mass"
    summary = "nodal point mass"

    node_tag: int = Field(description="node tag")
    magnitude: float = Field(description="mass magnitude")
    dof: DofToken = Field(description="degree of freedom identifier")

    def to_commands(self) -> list[str]:
        # `mass <tag> <node> <magnitude> <dof>`
        return [f"mass {self.tag} {self.node_tag} {self.magnitude:.12g} {self.dof}"]
