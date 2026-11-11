"""Recorders, mirroring ``Recorder/RecorderParser.cpp`` and the output
tokens of ``Recorder/OutputType.h`` (the ``recorder`` command family).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from suanpan.base import SuanpanObject, format_value
from suanpan.toolbox.dof import parse_dof
from suanpan.toolbox.format import IntList, StrList

__all__ = [
    "AmplitudeRecorder",
    "EigenRecorder",
    "ElementRecorder",
    "FrameRecorder",
    "GlobalMassRecorder",
    "GlobalRecorder",
    "GlobalStiffnessRecorder",
    "GroupElementRecorder",
    "GroupNodeRecorder",
    "GroupSumRecorder",
    "ModalForceRecorder",
    "ModalRecorder",
    "NodeRecorder",
    "OutputType",
    "Recorder",
    "SumRecorder",
    "VisualisationRecorder",
]


class OutputType(StrEnum):
    """Recorder output tokens, mirroring ``Recorder/OutputType.h``."""

    # stress
    S = "S"
    S11 = "S11"
    S12 = "S12"
    S13 = "S13"
    S22 = "S22"
    S23 = "S23"
    S33 = "S33"
    # strain
    E = "E"
    E11 = "E11"
    E12 = "E12"
    E13 = "E13"
    E22 = "E22"
    E23 = "E23"
    E33 = "E33"
    # elastic strain
    EE = "EE"
    EE11 = "EE11"
    EE12 = "EE12"
    EE13 = "EE13"
    EE22 = "EE22"
    EE23 = "EE23"
    EE33 = "EE33"
    # plastic strain
    PE = "PE"
    PE11 = "PE11"
    PE12 = "PE12"
    PE13 = "PE13"
    PE22 = "PE22"
    PE23 = "PE23"
    PE33 = "PE33"
    # principal stress
    SP = "SP"
    SP1 = "SP1"
    SP2 = "SP2"
    SP3 = "SP3"
    # principal strain
    EP = "EP"
    EP1 = "EP1"
    EP2 = "EP2"
    EP3 = "EP3"
    # principal elastic strain
    EEP = "EEP"
    EEP1 = "EEP1"
    EEP2 = "EEP2"
    EEP3 = "EEP3"
    # principal plastic strain
    PEP = "PEP"
    PEP1 = "PEP1"
    PEP2 = "PEP2"
    PEP3 = "PEP3"
    # displacement / velocity / acceleration
    U = "U"
    U1 = "U1"
    U2 = "U2"
    U3 = "U3"
    U4 = "U4"
    U5 = "U5"
    U6 = "U6"
    UR1 = "UR1"
    UR2 = "UR2"
    UR3 = "UR3"
    V = "V"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"
    V5 = "V5"
    V6 = "V6"
    VR1 = "VR1"
    VR2 = "VR2"
    VR3 = "VR3"
    A = "A"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    AR1 = "AR1"
    AR2 = "AR2"
    AR3 = "AR3"
    # momentum
    MM = "MM"
    MM1 = "MM1"
    MM2 = "MM2"
    MM3 = "MM3"
    MM4 = "MM4"
    MM5 = "MM5"
    MM6 = "MM6"
    MMR1 = "MMR1"
    MMR2 = "MMR2"
    MMR3 = "MMR3"
    # reaction force
    RF = "RF"
    RF1 = "RF1"
    RF2 = "RF2"
    RF3 = "RF3"
    RF4 = "RF4"
    RF5 = "RF5"
    RF6 = "RF6"
    RM1 = "RM1"
    RM2 = "RM2"
    RM3 = "RM3"
    # damping force
    DF = "DF"
    DF1 = "DF1"
    DF2 = "DF2"
    DF3 = "DF3"
    DF4 = "DF4"
    DF5 = "DF5"
    DF6 = "DF6"
    DM1 = "DM1"
    DM2 = "DM2"
    DM3 = "DM3"
    # inertial force
    IF = "IF"
    IF1 = "IF1"
    IF2 = "IF2"
    IF3 = "IF3"
    IF4 = "IF4"
    IF5 = "IF5"
    IF6 = "IF6"
    IM1 = "IM1"
    IM2 = "IM2"
    IM3 = "IM3"
    # global damping / inertial force
    GDF = "GDF"
    GDF1 = "GDF1"
    GDF2 = "GDF2"
    GDF3 = "GDF3"
    GDF4 = "GDF4"
    GDF5 = "GDF5"
    GDF6 = "GDF6"
    GDM1 = "GDM1"
    GDM2 = "GDM2"
    GDM3 = "GDM3"
    GIF = "GIF"
    GIF1 = "GIF1"
    GIF2 = "GIF2"
    GIF3 = "GIF3"
    GIF4 = "GIF4"
    GIF5 = "GIF5"
    GIF6 = "GIF6"
    GIM1 = "GIM1"
    GIM2 = "GIM2"
    GIM3 = "GIM3"
    # hydrostatic pressure / von Mises stress
    HYDRO = "HYDRO"
    MISES = "MISES"
    # equivalent strain / elastic / plastic
    EEQ = "EEQ"
    EEEQ = "EEEQ"
    PEEQ = "PEEQ"
    # energy
    KE = "KE"
    SE = "SE"
    VE = "VE"
    NVE = "NVE"
    # quadratic matrices
    K = "K"
    M = "M"
    # Maxwell/Kelvin model data
    ED = "ED"
    VD = "VD"
    SD = "SD"
    ES = "ES"
    VS = "VS"
    SS = "SS"
    # damage
    DAMAGE = "DAMAGE"
    DT = "DT"
    DC = "DC"
    # nonlocal / pore pressure / volume fraction
    NONLOCAL = "NONLOCAL"
    PP = "PP"
    VF = "VF"
    # history vector
    HIST = "HIST"
    # local iteration in Maxwell models
    LITR = "LITR"
    # yield flag (1 yield, 0 otherwise)
    YF = "YF"
    # beam end deformation / force
    BEAME = "BEAME"
    BEAMS = "BEAMS"
    # amplitude
    AMP = "AMP"
    # unknown token fallback of the C++ parser
    NL = "NL"


def validate_output_token(value: str) -> str:
    """Validate (and normalise) a recorder variable token."""
    token = value.strip().upper()
    try:
        OutputType(token)
    except ValueError:
        raise ValueError(
            f"invalid recorder variable {value!r}; see suanpan.recorder.OutputType"
        ) from None
    return token


class Recorder(SuanpanObject):
    """Base class of recorders (``recorder`` command family).

    All recorders export via the unified form
    ``recorder <tag> <plain|hdf5> <TYPE> ...``; ``hdf5recorder`` and
    ``plainrecorder`` are shortcuts of the same parser.
    """

    command = "recorder"
    sp_abstract = True

    #: whether data is stored in HDF5
    use_hdf5: bool = Field(
        default=False,
        json_schema_extra={"sp_kind": "omit"},
        description="plain text instead of HDF5",
    )
    #: record every ``interval`` steps, exported as ``every <interval>``
    interval: int = Field(
        default=1,
        ge=1,
        description="record every ``interval`` steps (default one)",
    )

    def _head(self) -> list[str]:
        return [
            "recorder",
            *format_value(self.tag),
            "hdf5" if self.use_hdf5 else "plain",
        ]

    def _every(self) -> list[str]:
        return ["every", str(self.interval)] if self.interval != 1 else []


class EigenRecorder(Recorder):
    """``recorder <tag> <plain|hdf5> Eigen`` (C++ ``EigenRecorder``)."""

    keyword = "Eigen"
    summary = "recorder of eigenvalues and eigenvectors"

    def to_commands(self) -> list[str]:
        return [" ".join([*self._head(), "Eigen"])]


class ModalRecorder(Recorder):
    """``recorder <tag> hdf5 Modal <dof...>`` (C++ ``ModalRecorder``).

    Extracts frequencies, mass-normalised mode shapes, modal participation
    factors, effective modal masses and modal force responses from an
    eigenanalysis step.  At least one DoF identifier defining the influence
    directions is required; duplicated directions are removed by suanPan.
    """

    keyword = "Modal"
    summary = "recorder of modal properties"

    use_hdf5: bool = Field(
        default=True,
        json_schema_extra={"sp_kind": "omit"},
        description="the Modal recorder stores its data in HDF5 format",
    )
    directions: StrList = Field(
        min_length=1,
        description="DoF identifiers defining the influence directions",
    )

    @field_validator("directions")
    @classmethod
    def _check_directions(cls, value: list[str]) -> list[str]:
        for token in value:
            if not parse_dof(token):
                raise ValueError(f"invalid DoF identifier {token!r}")
        return value

    def to_commands(self) -> list[str]:
        return [" ".join([*self._head(), "Modal", *format_value(self.directions)])]


class ModalForceRecorder(Recorder):
    """``recorder <tag> hdf5 ModalForce`` (C++ ``ModalForceRecorder``).

    Extracts modal elastic forces from an eigenanalysis step.  The recorder
    writes the assembled nodal force vector and the element force vectors for
    every extracted mode.  No DoF identifiers are required.
    """

    keyword = "ModalForce"
    summary = "recorder of modal elastic forces"

    use_hdf5: bool = Field(
        default=True,
        json_schema_extra={"sp_kind": "omit"},
        description="the ModalForce recorder stores its data in HDF5 format",
    )

    def to_commands(self) -> list[str]:
        return [" ".join([*self._head(), "ModalForce"])]


class _VariableRecorder(Recorder):
    """Recorders taking one variable type token and no object tags."""

    sp_abstract = True

    variable: str = Field(description="recorder variable, see OutputType")

    @field_validator("variable")
    @classmethod
    def _check_variable(cls, value: str) -> str:
        return validate_output_token(value)

    def to_commands(self) -> list[str]:
        return [" ".join([*self._head(), type(self).keyword, self.variable])]


class FrameRecorder(_VariableRecorder):
    """``recorder <tag> <plain|hdf5> Frame <variable> [every N]``.

    Collects element data over the whole domain.
    """

    keyword = "Frame"
    summary = "recorder of element data over the whole domain"


class VisualisationRecorder(_VariableRecorder):
    """``recorder <tag> <plain|hdf5> Visualisation <variable> [every N]
    [Width W] [Scale S]``.

    Requires VTK support in the executable.
    """

    keyword = "Visualisation"
    summary = "recorder for VTK visualisation"

    width: int = Field(default=6, ge=1, description="glyph width (default 6)")
    scale: float = Field(default=1.0, description="deformation scale (default 1.0)")

    def to_commands(self) -> list[str]:
        parts = [*self._head(), "Visualisation", self.variable, *self._every()]
        if self.width != 6:
            parts += ["Width", str(self.width)]
        if self.scale != 1.0:
            parts += ["Scale", *format_value(self.scale)]
        return [" ".join(parts)]


class _ObjectRecorder(Recorder):
    """Recorders taking a variable type and a list of object tags."""

    sp_abstract = True

    variable: str = Field(description="recorder variable, see OutputType")
    object_tags: IntList = Field(
        default_factory=list,
        description="tags of nodes/groups/elements to record",
    )

    @field_validator("variable")
    @classmethod
    def _check_variable(cls, value: str) -> str:
        return validate_output_token(value)

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    *self._head(),
                    type(self).keyword,
                    self.variable,
                    *self._every(),
                    *format_value(self.object_tags),
                ]
            )
        ]


class NodeRecorder(_ObjectRecorder):
    """Recorder of nodal data (C++ ``NodeRecorder``)."""

    keyword = "Node"
    summary = "recorder of nodal data"


class GroupNodeRecorder(_ObjectRecorder):
    """Recorder of nodal data over node groups (C++ ``GroupNodeRecorder``)."""

    keyword = "GroupNode"
    summary = "recorder of nodal data of node groups"


class SumRecorder(_ObjectRecorder):
    """Recorder of summation over nodes (C++ ``SumRecorder``)."""

    keyword = "Sum"
    summary = "recorder of summation of nodal data"


class GroupSumRecorder(_ObjectRecorder):
    """Recorder of summation over node groups (C++ ``GroupSumRecorder``)."""

    keyword = "GroupSum"
    summary = "recorder of summation over node groups"


class ElementRecorder(_ObjectRecorder):
    """Recorder of element data (C++ ``ElementRecorder``)."""

    keyword = "Element"
    summary = "recorder of element data"


class GroupElementRecorder(_ObjectRecorder):
    """Recorder of element data over element groups."""

    keyword = "GroupElement"
    summary = "recorder of element data of element groups"


class GlobalRecorder(_VariableRecorder):
    """``recorder <tag> <plain|hdf5> Global <variable>``.

    Records global quantities such as ``SE`` and ``KE``; the special
    tokens ``K`` and ``M`` map to ``GlobalStiffnessRecorder`` and
    ``GlobalMassRecorder`` respectively in the C++ domain.
    """

    keyword = "Global"
    summary = "recorder of global quantities"


class GlobalStiffnessRecorder(GlobalRecorder):
    """Global stiffness matrix recorder; the variable is fixed to ``K``."""

    summary = "recorder of global quadratic stiffness matrix"
    variable: str = Field(default="K", description="fixed to K")

    @field_validator("variable")
    @classmethod
    def _check_k(cls, value: str) -> str:
        if value.strip().upper() != "K":
            raise ValueError("GlobalStiffnessRecorder requires variable K")
        return "K"


class GlobalMassRecorder(GlobalRecorder):
    """Global mass matrix recorder; the variable is fixed to ``M``."""

    summary = "recorder of global quadratic mass matrix"
    variable: str = Field(default="M", description="fixed to M")

    @field_validator("variable")
    @classmethod
    def _check_m(cls, value: str) -> str:
        if value.strip().upper() != "M":
            raise ValueError("GlobalMassRecorder requires variable M")
        return "M"


class AmplitudeRecorder(Recorder):
    """``recorder <tag> <plain|hdf5> Amplitude <amplitudes...>``.

    Amplitude recorders carry no variable token in the command line.
    """

    keyword = "Amplitude"
    summary = "recorder of amplitude data"

    object_tags: IntList = Field(default_factory=list, description="amplitude tags")

    def to_commands(self) -> list[str]:
        return [
            " ".join(
                [
                    *self._head(),
                    "Amplitude",
                    *self._every(),
                    *format_value(self.object_tags),
                ]
            )
        ]
