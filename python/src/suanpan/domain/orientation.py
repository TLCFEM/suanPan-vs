"""Reference orientations, mirroring ``create_new_orientation`` in
``Element/ElementParser.cpp`` (the ``orientation`` command).

The exported line is ``orientation <type> <tag> <x> <y> <z>``.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from suanpan.base import SuanpanObject, format_value
from suanpan.toolbox.format import FloatList

__all__ = ["B3DC", "B3DL", "B3DOSC", "B3DOSL", "Orientation"]


class Orientation(SuanpanObject):
    """Base class of 3D beam orientations (``orientation`` command)."""

    command = "orientation"
    sp_abstract = True

    xyz: FloatList = Field(description="orientation reference vector (3 components)")

    @field_validator("xyz")
    @classmethod
    def _check_xyz(cls, value: FloatList) -> FloatList:
        if len(value) != 3:
            raise ValueError("orientation requires exactly three components")
        return value

    def to_commands(self) -> list[str]:
        if not self.keyword:
            # the C++ parser requires a type token; the base class is abstract
            raise NotImplementedError(
                f"{type(self).__name__} is abstract; use B3DL, B3DC, B3DOSL or B3DOSC"
            )
        parts = [
            "orientation",
            self.keyword,
            *format_value(self.tag),
            *format_value(self.xyz),
        ]
        return [" ".join(parts)]


class B3DL(Orientation):
    """Local orientation ``orientation B3DL`` (C++ ``B3DL``)."""

    keyword = "B3DL"
    summary = "3D beam local orientation"


class B3DC(Orientation):
    """Global orientation ``orientation B3DC`` (C++ ``B3DC``)."""

    keyword = "B3DC"
    summary = "3D beam global orientation"


class B3DOSL(Orientation):
    """Local orientation of beam with open section ``orientation B3DOSL``."""

    keyword = "B3DOSL"
    summary = "3D beam local orientation (open section)"


class B3DOSC(Orientation):
    """Global orientation of beam with open section ``orientation B3DOSC``."""

    keyword = "B3DOSC"
    summary = "3D beam global orientation (open section)"
