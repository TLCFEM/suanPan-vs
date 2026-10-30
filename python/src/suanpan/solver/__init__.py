"""Integrators and solvers, mirroring ``Solver/SolverParser.cpp``
(the ``integrator`` and ``solver`` commands).

Both commands attach the created object to the current step (if any) and
remember it as the current integrator/solver of the domain.
"""

from __future__ import annotations

import warnings
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from suanpan.base import SuanpanObject, format_float, format_value

__all__ = [
    "AICN",
    "BFGS",
    "FEAST",
    "GSSE",
    "GSSSSU0",
    "GSSSSV0",
    "ICL",
    "OALTS",
    "WAT2",
    "BatheExplicit",
    "BatheTwoStep",
    "DisplacementControl",
    "GSSSSOptimal",
    "GeneralizedAlpha",
    "GeneralizedAlphaExplicit",
    "Integrator",
    "LeeElementalNewmark",
    "LeeMode",
    "LeeNewmark",
    "LeeNewmarkBase",
    "LeeNewmarkBaseFull",
    "LeeNewmarkFullCurrent",
    "LeeNewmarkFullInitial",
    "LeeNewmarkFullTrial",
    "LeeNewmarkIterative",
    "LeePair",
    "ModifiedNewton",
    "Newmark",
    "NonviscousKernel",
    "NonviscousNewmark",
    "QuadraticFEAST",
    "Ramm",
    "RayleighNewmark",
    "Solver",
    "Tchamwa",
    "UDANewmark",
    "UDDNewmark",
    "WilsonPenzienNewmark",
]


class SolverTypeToken(str):
    """Verbatim string token."""

    __slots__ = ()


# --------------------------------------------------------------------------- #
# valuation helpers                                                           #
# --------------------------------------------------------------------------- #


def _clamp_unit(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Mirror ``suanpan::clamp_unit``."""
    return max(lo, min(hi, value))


# --------------------------------------------------------------------------- #
# integrators                                                                 #
# --------------------------------------------------------------------------- #
class Integrator(SuanpanObject):
    """Base class of time integration schemes (``integrator`` command)."""

    command = "integrator"
    sp_abstract = True


class LeeMode(BaseModel):
    """One ``-typeN`` damping kernel block of Lee integrators."""

    model_config = {"validate_assignment": True}

    #: kernel type, exported as ``-type0``...``-type4``
    type: Literal[0, 1, 2, 3, 4]
    zeta: float = Field(description="damping coefficient")
    omega: float = Field(description="frequency")
    params: list[float] = Field(
        default_factory=list,
        description=(
            "extra parameters: none for type 0, one for types 1 and 3, two "
            "for type 2, five for type 4"
        ),
    )

    _EXTRA_COUNT = {0: 0, 1: 1, 2: 2, 3: 1, 4: 5}

    @model_validator(mode="after")
    def check_params(self) -> LeeMode:
        expected = self._EXTRA_COUNT[self.type]
        if len(self.params) != expected:
            raise ValueError(
                f"Lee kernel -type{self.type} requires {expected} parameters, "
                f"got {len(self.params)}"
            )
        return self

    def to_tokens(self) -> list[str]:
        tokens = [
            f"-type{self.type}",
            format_float(self.zeta),
            format_float(self.omega),
        ]
        tokens += [format_float(v) for v in self.params]
        return tokens


class _NewmarkBase(Integrator):
    """Newmark family sharing the optional ``alpha``/``beta`` pair.

    The pair is exported only when at least one of them is set.
    """

    sp_abstract = True

    alpha: float | None = Field(default=None, description="Newmark alpha (default 1/4)")
    beta: float | None = Field(default=None, description="Newmark beta (default 1/2)")

    @model_validator(mode="after")
    def check_pair(self) -> _NewmarkBase:
        if (self.alpha is None) != (self.beta is None):
            raise ValueError("alpha and beta must both be provided or both omitted")
        return self

    def _line(self) -> list[str]:
        parts = ["integrator", type(self).keyword, *format_value(self.tag)]
        if self.alpha is not None and self.beta is not None:
            parts += [format_float(self.alpha), format_float(self.beta)]
        return parts


class Newmark(_NewmarkBase):
    """``integrator Newmark`` (C++ ``Newmark``), classic scheme."""

    keyword = "Newmark"
    summary = "Newmark integration scheme"

    def to_commands(self) -> list[str]:
        return [" ".join(self._line())]


class RayleighNewmark(Newmark):
    """``integrator RayleighNewmark`` (C++ ``RayleighNewmark``).

    Adds Rayleigh damping with up to four stiffness/mass interpolation
    factors.  As in the C++ parser, a fully zero set of factors is allowed
    but reported as a warning.
    """

    keyword = "RayleighNewmark"
    summary = "Newmark scheme with Rayleigh damping"

    damping_alpha: float = Field(
        default=0.0, description="damping factor (mass, first)"
    )
    damping_beta: float = Field(
        default=0.0, description="damping factor (stiffness, first)"
    )
    damping_zeta: float = Field(
        default=0.0, description="damping factor (mass, second)"
    )
    damping_eta: float = Field(
        default=0.0, description="damping factor (stiffness, second)"
    )

    @model_validator(mode="after")
    def check_damping(self) -> RayleighNewmark:
        values = (
            self.damping_alpha,
            self.damping_beta,
            self.damping_zeta,
            self.damping_eta,
        )
        if all(abs(v) < 1e-10 for v in values):
            warnings.warn(
                "all Rayleigh damping factors are zero, consider plain Newmark",
                UserWarning,
            )
        return self

    def to_commands(self) -> list[str]:
        parts = self._line()
        values = [
            self.damping_alpha,
            self.damping_beta,
            self.damping_zeta,
            self.damping_eta,
        ]
        # values are positional in the command line; trailing (default)
        # zeros may be omitted
        while values and abs(values[-1]) < 1e-12:
            values.pop()
        parts += [format_float(v) for v in values]
        return [" ".join(parts)]


def _check_conjugate(imaginary: list[float]) -> None:
    if imaginary and sum(imaginary) <= 1e-12:
        raise ValueError("Parameters should be conjugate pairs.")


class NonviscousKernel(BaseModel):
    """One (m_r, m_i, s_r, s_i) kernel term of nonviscous integrators."""

    model_config = {"validate_assignment": True}

    m_r: float = Field(description="real part of the mass kernel weight")
    m_i: float = Field(description="imaginary part of the mass kernel weight")
    s_r: float = Field(description="real part of the pole")
    s_i: float = Field(description="imaginary part of the pole")

    def to_tokens(self) -> list[str]:
        return [format_float(v) for v in (self.m_r, self.m_i, self.s_r, self.s_i)]


class _KernelNewmark(Newmark):
    """Nonviscous / UDD / UDA integrators over conjugate kernel terms."""

    sp_abstract = True

    kernels: list[NonviscousKernel] = Field(
        default_factory=list, description="complex conjugate kernel terms"
    )

    @model_validator(mode="after")
    def check_kernels(self) -> _KernelNewmark:
        _check_conjugate([k.m_i for k in self.kernels])
        return self

    def to_commands(self) -> list[str]:
        parts = self._line()
        for kernel in self.kernels:
            parts += kernel.to_tokens()
        return [" ".join(parts)]

    def export_kernels(self) -> list[float]:
        """Flatten kernel terms into the interleaved command line form."""
        return [v for k in self.kernels for v in k.to_tokens()]


class NonviscousNewmark(_KernelNewmark):
    """``integrator NonviscousNewmark`` (C++ ``NonviscousNewmark``)."""

    keyword = "NonviscousNewmark"
    summary = "nonviscous damping via the Newmark scheme"


class UDDNewmark(_KernelNewmark):
    """``integrator UDDNewmark`` (C++ ``UDDNewmark``)."""

    keyword = "UDDNewmark"
    summary = "UDD damping via the Newmark scheme"

    @model_validator(mode="after")
    def check_signs(self) -> UDDNewmark:
        m_negative = any(k.m_r < 0.0 for k in self.kernels)
        s_positive = any(k.s_r > 0.0 for k in self.kernels)
        if m_negative and s_positive:
            raise ValueError(
                "UDD requires both weights (m_j) and poles (s_j) to have "
                "negative real parts."
            )
        return self


class UDANewmark(_KernelNewmark):
    """``integrator UDANewmark`` (C++ ``UDANewmark``)."""

    keyword = "UDANewmark"
    summary = "UDA damping via the Newmark scheme"

    @model_validator(mode="after")
    def check_signs(self) -> UDANewmark:
        m_positive = any(k.m_r < 0.0 for k in self.kernels)
        s_negative = any(k.s_r > 0.0 for k in self.kernels)
        if m_positive and s_negative:
            raise ValueError(
                "UDA requires weights (m_j) to have positive real parts and "
                "poles (s_j) to have negative real parts."
            )
        return self


class WilsonPenzienNewmark(Newmark):
    """``integrator WilsonPenzienNewmark`` (C++ ``WilsonPenzienNewmark``)."""

    keyword = "WilsonPenzienNewmark"
    summary = "Wilson-Penzien integration scheme"

    damping_ratio: list[float] = Field(
        default_factory=list, description="damping ratios of auxiliary SDOF systems"
    )

    def to_commands(self) -> list[str]:
        parts = self._line()
        parts += [format_float(v) for v in self.damping_ratio]
        return [" ".join(parts)]


class LeePair(BaseModel):
    """One (damping coefficient, frequency) pair of Lee integrators."""

    model_config = {"validate_assignment": True}

    damping: float = Field(description="damping coefficient")
    frequency: float = Field(description="frequency")

    def to_tokens(self) -> list[str]:
        return [format_float(self.damping), format_float(self.frequency)]


class LeeNewmark(Newmark):
    """``integrator LeeNewmark`` (C++ ``LeeNewmark``).

    Takes any number of ``(damping coefficient, frequency)`` pairs.
    """

    keyword = "LeeNewmark"
    summary = "modal history damping via the Newmark scheme"

    pairs: list[LeePair] = Field(
        default_factory=list, description="damping/frequency pairs"
    )

    def to_commands(self) -> list[str]:
        parts = self._line()
        for pair in self.pairs:
            parts += pair.to_tokens()
        return [" ".join(parts)]


class LeeElementalNewmark(LeeNewmark):
    """``integrator LeeElementalNewmark`` (C++ ``LeeElementalNewmark``)."""

    keyword = "LeeElementalNewmark"
    summary = "elemental modal history damping via the Newmark scheme"


class LeeNewmarkBase(Newmark):
    """Base of iterative / full Lee--Newmark variants using ``-typeN`` blocks."""

    sp_abstract = True

    modes: list[LeeMode] = Field(
        default_factory=list, description="damping kernel blocks (-type0 ... -type4)"
    )

    def to_commands(self) -> list[str]:
        parts = self._line()
        for mode in self.modes:
            parts += mode.to_tokens()
        return [" ".join(parts)]


class LeeNewmarkIterative(LeeNewmarkBase):
    """``integrator LeeNewmarkIterative`` (C++ ``LeeNewmarkIterative``)."""

    keyword = "LeeNewmarkIterative"
    summary = "iterative Lee damping scheme"


class LeeNewmarkBaseFull(LeeNewmarkBase):
    """Base of the ``LeeNewmarkFull*`` family."""

    sp_abstract = True


class LeeNewmarkFullTrial(LeeNewmarkBaseFull):
    """``integrator LeeNewmarkFullTrial`` (C++ ``LeeNewmarkFull``)."""

    keyword = "LeeNewmarkFullTrial"
    summary = "full Lee damping scheme with trial stiffness"


class LeeNewmarkFullCurrent(LeeNewmarkBaseFull):
    """``integrator LeeNewmarkFull`` (C++ ``LeeNewmarkFull``)."""

    keyword = "LeeNewmarkFull"
    aliases = ("LeeNewmarkFullCurrent",)
    summary = "full Lee damping scheme with current stiffness"


class LeeNewmarkFullInitial(LeeNewmarkBaseFull):
    """``integrator LeeNewmarkFullInitial`` (C++ ``LeeNewmarkFull``)."""

    keyword = "LeeNewmarkFullInitial"
    summary = "full Lee damping scheme with initial stiffness"


class GeneralizedAlpha(Integrator):
    """``integrator GeneralizedAlpha`` (C++ ``GeneralizedAlpha``).

    With no argument, ``alpha_f = 0.5``; one argument sets ``alpha_f``;
    two arguments set ``(alpha_f, alpha_m)``.
    """

    keyword = "GeneralizedAlpha"
    aliases = ("GeneralisedAlpha",)
    summary = "generalized alpha implicit integration"

    alpha_f: float | None = Field(
        default=None, description="alpha_f, clamped to [0, 1]"
    )
    alpha_m: float | None = Field(
        default=None, description="alpha_m, clamped to [0, 1]"
    )

    @model_validator(mode="after")
    def check_pair(self) -> GeneralizedAlpha:
        if self.alpha_m is not None and self.alpha_f is None:
            raise ValueError("alpha_m requires alpha_f")
        return self

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        if self.alpha_f is not None:
            parts.append(format_float(_clamp_unit(self.alpha_f)))
        if self.alpha_m is not None:
            parts.append(format_float(_clamp_unit(self.alpha_m)))
        return [" ".join(parts)]


class _RadiusIntegrator(Integrator):
    """Explicit integrators parameterised by one spectral radius."""

    sp_abstract = True

    radius: float = Field(default=0.5, description="spectral radius, clamped to [0, 1]")

    def to_commands(self) -> list[str]:
        parts = ["integrator", type(self).keyword, *format_value(self.tag)]
        parts.append(format_float(_clamp_unit(self.radius)))
        return [" ".join(parts)]


class GSSSSU0(Integrator):
    """``integrator GSSSSU0`` (C++ ``GSSSSU0``) -- three spectral radii."""

    keyword = "GSSSSU0"
    summary = "GSSSS U0 scheme"

    radii: list[float] = Field(description="exactly three spectral radii")

    @model_validator(mode="after")
    def check_radii(self) -> GSSSSU0:
        if len(self.radii) != 3:
            raise ValueError("GSSSSU0 requires exactly three spectral radii")
        return self

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        parts += [format_float(v) for v in self.radii]
        return [" ".join(parts)]


class GSSSSV0(Integrator):
    """``integrator GSSSSV0`` (C++ ``GSSSSV0``) -- three spectral radii."""

    keyword = "GSSSSV0"
    summary = "GSSSS V0 scheme"

    radii: list[float] = Field(description="exactly three spectral radii")

    @model_validator(mode="after")
    def check_radii(self) -> GSSSSV0:
        if len(self.radii) != 3:
            raise ValueError("GSSSSV0 requires exactly three spectral radii")
        return self

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        parts += [format_float(v) for v in self.radii]
        return [" ".join(parts)]


class GSSSSOptimal(_RadiusIntegrator):
    """``integrator GSSSSOptimal`` (C++ ``GSSSSOptimal``)."""

    keyword = "GSSSSOptimal"
    summary = "optimal GSSSS scheme"


class OALTS(_RadiusIntegrator):
    """``integrator OALTS`` (C++ ``OALTS``)."""

    keyword = "OALTS"
    summary = "optimal alpha-LTS scheme"


class BatheTwoStep(Integrator):
    """``integrator BatheTwoStep`` (C++ ``BatheTwoStep``).

    The radius default is zero (undamped) in the C++ parser.
    """

    keyword = "BatheTwoStep"
    summary = "Bathe two step scheme"

    radius: float = Field(default=0.0, description="damping radius")
    gamma: float = Field(
        default=0.5, description="gamma parameter, reset to 1/2 outside (0, 1)"
    )

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        radius = _clamp_unit(self.radius)
        gamma = self.gamma if 0.0 < self.gamma < 1.0 else 0.5
        parts += [format_float(radius), format_float(gamma)]
        return [" ".join(parts)]


class Tchamwa(_RadiusIntegrator):
    """``integrator Tchamwa`` (C++ ``Tchamwa``)."""

    keyword = "Tchamwa"
    summary = "Tchamwa Wielgosz explicit scheme"


class BatheExplicit(_RadiusIntegrator):
    """``integrator BatheExplicit`` (C++ ``BatheExplicit``)."""

    keyword = "BatheExplicit"
    summary = "Bathe explicit scheme"


class ICL(_RadiusIntegrator):
    """``integrator ICL`` (C++ ``ICL``), radius clamped to [0.5, 1.0]."""

    keyword = "ICL"
    summary = "iterated constant left scheme"

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        parts.append(format_float(_clamp_unit(self.radius, 0.5, 1.0)))
        return [" ".join(parts)]


class GSSE(_RadiusIntegrator):
    """``integrator GSSE`` (C++ ``GSSE``)."""

    keyword = "GSSE"
    summary = "GSSSS explicit scheme"


class WAT2(Integrator):
    """``integrator WAT2`` (C++ ``WAT2``), parameter default 1/3."""

    keyword = "WAT2"
    summary = "WAT2 explicit scheme"

    para: float = Field(default=1.0 / 3.0, description="parameter clamped to [0, 1]")

    def to_commands(self) -> list[str]:
        parts = ["integrator", self.keyword, *format_value(self.tag)]
        parts.append(format_float(_clamp_unit(self.para)))
        return [" ".join(parts)]


class GeneralizedAlphaExplicit(_RadiusIntegrator):
    """``integrator GeneralizedAlphaExplicit`` (C++ ``GeneralizedAlphaExplicit``)."""

    keyword = "GeneralizedAlphaExplicit"
    aliases = ("GeneralisedAlphaExplicit",)
    summary = "generalized alpha explicit integration"


# --------------------------------------------------------------------------- #
# solvers                                                                     #
# --------------------------------------------------------------------------- #
class Solver(SuanpanObject):
    """Base class of nonlinear solvers (``solver`` command)."""

    command = "solver"
    sp_abstract = True


class Newton(Solver):
    """``solver Newton`` (C++ ``Newton``)."""

    keyword = "Newton"
    summary = "full Newton solver"

    def to_commands(self) -> list[str]:
        return [" ".join(["solver", self.keyword, *format_value(self.tag)])]


class ModifiedNewton(Solver):
    """``solver modifiedNewton`` (C++ ``Newton`` with constant stiffness)."""

    keyword = "modifiedNewton"
    aliases = ("mNewton",)
    summary = "modified Newton solver (constant stiffness)"

    def to_commands(self) -> list[str]:
        return [" ".join(["solver", self.keyword, *format_value(self.tag)])]


class AICN(Solver):
    """``solver AICN`` (C++ ``AICN``)."""

    keyword = "AICN"
    summary = "arbitrary point implicit with arc length"

    length: float = Field(default=1.0, description="arc length (default one)")


class BFGS(Solver):
    """``solver BFGS`` (C++ ``BFGS``)."""

    keyword = "BFGS"
    summary = "Broyden-Fletcher-Goldfarb-Shanno solver"


class LBFGS(BFGS):
    """``solver LBFGS`` (C++ ``BFGS`` with history)."""

    keyword = "LBFGS"
    summary = "limited memory BFGS solver"

    max_history: int = Field(
        default=20, ge=1, description="history length (default 20)"
    )


class FEAST(Solver):
    """``solver FEAST`` (C++ ``FEAST``).

    The radius defaults to the centre when omitted.
    """

    keyword = "FEAST"
    summary = "FEAST eigenvalue solver"

    eigen_number: int = Field(ge=1, description="number of frequencies to extract")
    centre: float = Field(description="centre of the search interval")
    radius: float | None = Field(default=None, description="radius of the interval")

    quadratic: bool = Field(default=False, json_schema_extra={"sp_kind": "omit"})

    def to_commands(self) -> list[str]:
        radius = self.radius if self.radius is not None else self.centre
        return [
            " ".join(
                [
                    "solver",
                    self.keyword,
                    *format_value(self.tag),
                    str(self.eigen_number),
                    format_float(self.centre),
                    format_float(radius),
                ]
            )
        ]


class QuadraticFEAST(FEAST):
    """``solver QuadraticFEAST`` (C++ ``FEAST`` in quadratic mode)."""

    keyword = "QuadraticFEAST"
    summary = "quadratic FEAST eigenvalue solver"

    quadratic: bool = Field(default=True, json_schema_extra={"sp_kind": "omit"})


class DisplacementControl(Solver):
    """``solver DisplacementControl`` (C++ ``MPDC``)."""

    keyword = "DisplacementControl"
    aliases = ("MPDC",)
    summary = "modified displacement control (arc length)"


class Ramm(Solver):
    """``solver Ramm`` (C++ ``Ramm``)."""

    keyword = "Ramm"
    summary = "Ramm constant arc length method"
