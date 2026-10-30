"""Analysis steps, mirroring ``Step/StepParser.cpp`` and the properties
the ``set`` command applies to the current step (``Toolbox/command.cpp``).

A step composes the analysis objects that belong to it: integrator,
solver, convergers, criteria, constraints, loads and recorders.  In the
input file they are exported as a step block: first the ``step`` line and
its ``set`` properties, then the attached objects -- exactly the order the
C++ parser expects.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from suanpan.base import SuanpanObject, format_value
from suanpan.constraint import Constraint, Criterion
from suanpan.converger import Converger
from suanpan.load import Load
from suanpan.recorder import Recorder
from suanpan.solver import Integrator, Solver

__all__ = [
    "SYSTEM_SOLVERS",
    "ArcLengthStep",
    "BuckleStep",
    "DynamicStep",
    "ExplicitDynamicStep",
    "FrequencyStep",
    "OptimizationStep",
    "StaticStep",
    "Step",
    "cell_commands",
]

#: accepted ``set system_solver``/``set sub_system_solver`` values; LIS and
#: MUMPS additionally read option strings that are parsed by the C++ side
SYSTEM_SOLVERS: tuple[str, ...] = (
    "LAPACK",
    "SPIKE",
    "SUPERLU",
    "LIS",
    "MUMPS",
    "CUDA",
    "MAGMA",
    "PARDISO",
    "FGMRES",
)

_PRECISIONS: tuple[str, ...] = ("FULL", "SINGLE", "MIXED")


def _f(value: float) -> str:
    from suanpan.base import format_float

    return format_float(value)


class Step(SuanpanObject):
    """Base class of analysis steps (``step`` command)."""

    command = "step"
    sp_abstract = True

    def _step_head(self) -> list[str]:
        raise NotImplementedError(f"{type(self).__name__} is abstract")

    def _time_tokens(self) -> list[str]:
        """Trailing optional time period (omitted at the default one)."""
        return [_f(self.time_period)] if self.time_period != 1.0 else []

    # -- step properties set via the `set` command --------------------------- #
    fixed_step_size: bool | None = Field(
        default=None, description="use fixed step size"
    )
    symm_mat: bool | None = Field(default=None, description="assume symmetric matrices")
    band_mat: bool | None = Field(default=None, description="assume banded matrices")
    sparse_mat: bool | None = Field(default=None, description="assume sparse matrices")
    iterative_refinement: int | None = Field(
        default=None, ge=0, le=255, description="iterative refinement passes"
    )
    system_solver: str | None = Field(
        default=None, description="linear system solver, see SYSTEM_SOLVERS"
    )
    sub_system_solver: str | None = Field(
        default=None, description="sub-linear system solver, see SYSTEM_SOLVERS"
    )
    precision: str | None = Field(
        default=None, description="matrix precision: FULL, SINGLE or MIXED"
    )
    tolerance: float | None = Field(
        default=None, description="solver tolerance (e.g. FGMRES)"
    )
    ini_step_size: float | None = Field(default=None, description="initial step size")
    min_step_size: float | None = Field(default=None, description="minimum step size")
    max_step_size: float | None = Field(default=None, description="maximum step size")
    max_iteration: int | None = Field(
        default=None, ge=1, description="maximum number of substeps"
    )
    linear_system: bool = Field(
        default=False,
        json_schema_extra={"sp_kind": "omit"},
        description="treat the step as linear",
    )

    # -- attached analysis objects ------------------------------------------- #
    integrator: Integrator | None = Field(
        default=None, description="integration scheme"
    )
    solver: Solver | None = Field(default=None, description="nonlinear solver")
    convergers: list[Converger] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    loads: list[Load] = Field(default_factory=list)
    recorders: list[Recorder] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_attributes(self) -> Step:
        if (
            self.system_solver is not None
            and self.system_solver.upper() not in SYSTEM_SOLVERS
        ):
            raise ValueError(
                f"unknown system_solver {self.system_solver!r}; expected one of "
                f"{', '.join(SYSTEM_SOLVERS)}"
            )
        if (
            self.sub_system_solver is not None
            and self.sub_system_solver.upper() not in SYSTEM_SOLVERS
        ):
            raise ValueError(
                f"unknown sub_system_solver {self.sub_system_solver!r}; expected one of "
                f"{', '.join(SYSTEM_SOLVERS)}"
            )
        if self.precision is not None and self.precision.upper() not in _PRECISIONS:
            raise ValueError(
                f"unknown precision {self.precision!r}; expected one of "
                f"{', '.join(_PRECISIONS)}"
            )
        return self

    def to_commands(self) -> list[str]:
        return [" ".join(self._step_head()), *self._set_commands()]

    def _set_commands(self) -> list[str]:
        lines = []
        if self.linear_system:
            lines.append("set linear_system")
        if self.fixed_step_size is not None:
            lines.append(
                f"set fixed_step_size {'true' if self.fixed_step_size else 'false'}"
            )
        if self.symm_mat is not None:
            lines.append(f"set symm_mat {'true' if self.symm_mat else 'false'}")
        if self.band_mat is not None:
            lines.append(f"set band_mat {'true' if self.band_mat else 'false'}")
        if self.sparse_mat is not None:
            lines.append(f"set sparse_mat {'true' if self.sparse_mat else 'false'}")
        if self.iterative_refinement is not None:
            lines.append(f"set iterative_refinement {self.iterative_refinement}")
        if self.precision is not None:
            lines.append(f"set precision {self.precision.upper()}")
        if self.system_solver is not None:
            lines.append(f"set system_solver {self.system_solver.upper()}")
        if self.sub_system_solver is not None:
            lines.append(f"set sub_system_solver {self.sub_system_solver.upper()}")
        if self.tolerance is not None:
            lines.append(f"set tolerance {_f(self.tolerance)}")
        if self.ini_step_size is not None:
            lines.append(f"set ini_step_size {_f(self.ini_step_size)}")
        if self.min_step_size is not None:
            lines.append(f"set min_step_size {_f(self.min_step_size)}")
        if self.max_step_size is not None:
            lines.append(f"set max_step_size {_f(self.max_step_size)}")
        if self.max_iteration is not None:
            lines.append(f"set max_iteration {self.max_iteration}")
        return lines


class FrequencyStep(Step):
    """``step Frequency <tag> <eigen_number> <type>`` (C++ ``Frequency``)."""

    keyword = "Frequency"
    summary = "eigenvalue (frequency) analysis"

    eigen_number: int = Field(default=1, ge=1, description="number of eigenvalues")
    #: eigen solver switch, e.g. 's' for the smallest eigenvalues
    type: str = Field(default="s", description="eigenvalue type identifier")

    def _step_head(self) -> list[str]:
        # the C++ parser reads the eigen number and the type token from the
        # step line itself; there is no `set eigen_number` command
        parts = ["step", "Frequency", *format_value(self.tag), str(self.eigen_number)]
        if self.type != "s":
            parts.append(self.type.upper())
        return parts


class BuckleStep(Step):
    """``step Buckle <tag>`` (C++ ``Buckle``)."""

    keyword = "Buckle"
    aliases = ("Buckling",)
    summary = "buckling analysis"

    def _step_head(self) -> list[str]:
        return ["step", "Buckle", *format_value(self.tag)]


class OptimizationStep(Step):
    """``step Optimization <tag> <time>`` (C++ ``Optimization``)."""

    keyword = "Optimization"
    aliases = ("Optimisation",)
    summary = "topology optimisation analysis"

    time_period: float = Field(default=1.0, description="time period (default one)")

    def _step_head(self) -> list[str]:
        return ["step", "Optimization", *format_value(self.tag), *self._time_tokens()]


class StaticStep(Step):
    """``step Static <tag> <time>`` (C++ ``Static``)."""

    keyword = "Static"
    summary = "static analysis"

    time_period: float = Field(default=1.0, description="time period (default one)")

    def _step_head(self) -> list[str]:
        return ["step", "Static", *format_value(self.tag), *self._time_tokens()]


class DynamicStep(Step):
    """``step Dynamic <tag> <time>`` (C++ ``Dynamic``, implicit)."""

    keyword = "Dynamic"
    aliases = ("ImplicitDynamic",)
    summary = "implicit dynamic analysis"

    time_period: float = Field(default=1.0, description="time period (default one)")

    def _step_head(self) -> list[str]:
        return ["step", "Dynamic", *format_value(self.tag), *self._time_tokens()]


class ExplicitDynamicStep(Step):
    """``step ExplicitDynamic <tag> <time>`` (C++ ``Dynamic``, explicit)."""

    keyword = "ExplicitDynamic"
    summary = "explicit dynamic analysis"

    time_period: float = Field(default=1.0, description="time period (default one)")

    def _step_head(self) -> list[str]:
        return [
            "step",
            "ExplicitDynamic",
            *format_value(self.tag),
            *self._time_tokens(),
        ]


class ArcLengthStep(Step):
    """``step ArcLength <tag>`` (C++ ``ArcLength``)."""

    keyword = "ArcLength"
    summary = "arc length analysis"

    def _step_head(self) -> list[str]:
        return ["step", "ArcLength", *format_value(self.tag)]


def _step_line(step: Step) -> str:
    return " ".join(step._step_head())


def cell_commands(step: Step) -> list[str]:
    """Export a full step cell: the step line, its ``set`` properties and
    then every attached analysis object, in the order the C++ parser
    consumes them."""

    def _collect(objects) -> None:
        for obj in objects:
            lines.extend(obj.to_commands())

    lines = [*step.to_commands()]
    _collect([step.integrator] if step.integrator is not None else [])
    _collect([step.solver] if step.solver is not None else [])
    _collect(step.convergers)
    _collect(step.criteria)
    _collect(step.constraints)
    _collect(step.loads)
    _collect(step.recorders)
    return lines


# resolve the forward references of the composed children
Step.model_rebuild()
