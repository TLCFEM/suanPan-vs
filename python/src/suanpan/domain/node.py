"""Nodal objects, mirroring ``Domain/Node.cpp`` (the ``node`` command)."""

from __future__ import annotations

from pydantic import Field

from suanpan.base import SuanpanObject
from suanpan.toolbox.format import FloatList

__all__ = ["Node"]


class Node(SuanpanObject):
    """A finite element node (C++ ``Domain/Node.h``)."""

    command = "node"
    keyword = "node"
    summary = "finite element node"

    coordinate: FloatList = Field(
        default_factory=list,
        description="nodal coordinates (2 or 3 components)",
    )

    def to_commands(self) -> list[str]:
        # the node command has no keyword: `node <tag> <x> <y> <z>`
        parts = [self.command, str(self.tag)]
        from suanpan.base import format_value

        parts.extend(format_value(self.coordinate))
        return [" ".join(parts)]

    @property
    def dimension(self) -> int:
        """Number of coordinate components."""
        return len(self.coordinate)
