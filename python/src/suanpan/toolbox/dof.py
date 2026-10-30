"""Nodal degrees of freedom, mirroring ``Domain/Node.h`` and the DOF token
parsing of ``Domain/ConditionalModifier.cpp`` (``parse_dof``)."""

from __future__ import annotations

from enum import IntEnum
from typing import Annotated

from pydantic import AfterValidator

__all__ = ["DOF", "DOF_TOKENS", "DofToken", "dof_token_validator", "parse_dof"]


class DOF(IntEnum):
    """Nodal degree of freedom identifiers (``Node::DOF``)."""

    NONE = 0
    U1 = 1  # displacement in x direction
    U2 = 2  # displacement in y direction
    U3 = 3  # displacement in z direction
    UR1 = 4  # rotation in x direction
    UR2 = 5  # rotation in y direction
    UR3 = 6  # rotation in z direction
    FU1 = 7  # fluid displacement
    FU2 = 8  # fluid displacement
    FU3 = 9  # fluid displacement
    FUR1 = 10  # fluid rotation
    FUR2 = 11  # fluid rotation
    FUR3 = 12  # fluid rotation
    RADIAL = 13  # radius direction in axis-symmetric problems
    AXIAL = 14  # axial direction in axis-symmetric / single section elements
    RS = 15  # strong axis rotation
    RW = 16  # weak axis rotation
    DAMAGE = 17  # damage
    PRESSURE = 18  # pressure
    TEMPERATURE = 19  # temperature
    WARP = 20  # warping
    NL1 = 21  # nonlocal 1


#: token -> list of DOF, mirroring ``parse_dof`` in ConditionalModifier.cpp
_TOKEN_MAP: dict[str, tuple[DOF, ...]] = {
    "pinned": (DOF.U1, DOF.U2, DOF.U3),
    "p": (DOF.U1, DOF.U2, DOF.U3),
    "encastre": (DOF.U1, DOF.U2, DOF.U3, DOF.UR1, DOF.UR2, DOF.UR3),
    "e": (DOF.U1, DOF.U2, DOF.U3, DOF.UR1, DOF.UR2, DOF.UR3),
    "xsymm": (DOF.U1, DOF.UR2, DOF.UR3),
    "x": (DOF.U1, DOF.UR2, DOF.UR3),
    "ysymm": (DOF.UR1, DOF.U2, DOF.UR3),
    "y": (DOF.UR1, DOF.U2, DOF.UR3),
    "zsymm": (DOF.UR1, DOF.UR2, DOF.U3),
    "z": (DOF.UR1, DOF.UR2, DOF.U3),
    "1": (DOF.U1,),
    "u1": (DOF.U1,),
    "2": (DOF.U2,),
    "u2": (DOF.U2,),
    "3": (DOF.U3,),
    "u3": (DOF.U3,),
    "4": (DOF.UR1,),
    "u4": (DOF.UR1,),
    "ur1": (DOF.UR1,),
    "5": (DOF.UR2,),
    "u5": (DOF.UR2,),
    "ur2": (DOF.UR2,),
    "6": (DOF.UR3,),
    "u6": (DOF.UR3,),
    "ur3": (DOF.UR3,),
    "fu1": (DOF.FU1,),
    "fu2": (DOF.FU2,),
    "fu3": (DOF.FU3,),
    "fur1": (DOF.FUR1,),
    "fur2": (DOF.FUR2,),
    "fur3": (DOF.FUR3,),
    "radial": (DOF.RADIAL,),
    "axial": (DOF.AXIAL,),
    "rs": (DOF.RS,),
    "rw": (DOF.RW,),
    "damage": (DOF.DAMAGE,),
    "pressure": (DOF.PRESSURE,),
    "temperature": (DOF.TEMPERATURE,),
    "warp": (DOF.WARP,),
}

#: every valid DOF token, sorted by length so the display order is stable
DOF_TOKENS: tuple[str, ...] = tuple(
    token for token, _ in sorted(_TOKEN_MAP.items(), key=lambda kv: (len(kv[0]), kv[0]))
)


def parse_dof(token: str) -> tuple[DOF, ...]:
    """Expand a DOF token into its DOF identifiers (mirrors the C++ parser).

    The token ``E`` for example expands to all six translational and
    rotational DOFs; an empty tuple means the token is invalid.
    """
    return _TOKEN_MAP.get(token.strip().lower(), ())


def validate_dof_token(value: str) -> str:
    """Pydantic validator keeping DOF tokens well formed."""
    token = value.strip()
    if not parse_dof(token):
        raise ValueError(
            f"invalid DOF token {value!r}; expected one of {', '.join(DOF_TOKENS)}"
        )
    return token


#: annotated string type validating a DOF token
DofToken = Annotated[str, AfterValidator(validate_dof_token)]

dof_token_validator = validate_dof_token
