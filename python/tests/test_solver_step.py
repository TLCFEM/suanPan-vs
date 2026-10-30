"""Tests of the solver module (integrators + solvers) and the step module
(step commands, step cells)."""

import pytest

from suanpan.base import find_class
from suanpan.converger import RelIncreDisp
from suanpan.load import Cload
from suanpan.recorder import NodeRecorder
from suanpan.solver import (
    AICN,
    BFGS,
    FEAST,
    GSSSSU0,
    LBFGS,
    DisplacementControl,
    GeneralizedAlpha,
    Integrator,
    ModifiedNewton,
    Newmark,
    Newton,
    QuadraticFEAST,
    Ramm,
    Solver,
    Tchamwa,
)
from suanpan.step import (
    ArcLengthStep,
    BuckleStep,
    DynamicStep,
    ExplicitDynamicStep,
    FrequencyStep,
    OptimizationStep,
    StaticStep,
    Step,
    cell_commands,
)


class TestIntegrators:
    def test_newmark_default(self):
        # the alpha/beta pair is exported only when at least one is set
        assert Newmark(tag=1).to_commands() == ["integrator Newmark 1"]

    def test_newmark_pair(self):
        assert Newmark(tag=1, alpha=0.25, beta=0.5).to_commands() == [
            "integrator Newmark 1 0.25 0.5"
        ]

    def test_pair_validation(self):
        with pytest.raises(Exception):
            Newmark(tag=1, alpha=0.25)

    def test_generalized_alpha(self):
        # no argument: alpha_f = 0.5 (C++ default)
        assert GeneralizedAlpha(tag=1).to_commands() == [
            "integrator GeneralizedAlpha 1"
        ]
        assert GeneralizedAlpha(tag=1, alpha_f=0.3).to_commands() == [
            "integrator GeneralizedAlpha 1 0.3"
        ]
        assert GeneralizedAlpha(tag=1, alpha_f=0.3, alpha_m=0.2).to_commands() == [
            "integrator GeneralizedAlpha 1 0.3 0.2"
        ]

    def test_alpha_m_requires_alpha_f(self):
        with pytest.raises(Exception):
            GeneralizedAlpha(tag=1, alpha_m=0.2)

    def test_radius_clamped(self):
        assert Tchamwa(tag=1, radius=1.5).to_commands() == ["integrator Tchamwa 1 1"]

    def test_gssssu0_three_radii(self):
        with pytest.raises(Exception):
            GSSSSU0(tag=1, radii=[1.0, 1.0])
        assert GSSSSU0(tag=1, radii=[1.0, 1.0, 1.0]).to_commands() == [
            "integrator GSSSSU0 1 1 1 1"
        ]

    def test_integrator_base_is_abstract(self):
        assert Integrator.sp_abstract is True


class TestSolvers:
    def test_newton(self):
        assert Newton(tag=1).to_commands() == ["solver Newton 1"]

    def test_modified_newton(self):
        # the C++ dispatch keyword is `modifiedNewton`
        assert ModifiedNewton(tag=1).to_commands() == ["solver modifiedNewton 1"]

    def test_bfgs(self):
        assert BFGS(tag=1).to_commands() == ["solver BFGS 1"]

    def test_lbfgs(self):
        # max_history is a default-20 trailing optional -> trimmed
        assert LBFGS(tag=1).to_commands() == ["solver LBFGS 1"]

    def test_ramm_and_mpdc(self):
        assert Ramm(tag=1).to_commands() == ["solver Ramm 1"]
        assert DisplacementControl(tag=1).to_commands() == [
            "solver DisplacementControl 1"
        ]

    def test_aicn(self):
        assert AICN(tag=1).to_commands() == ["solver AICN 1"]

    def test_feast(self):
        # the radius defaults to the centre when omitted
        assert FEAST(tag=1, eigen_number=5, centre=100).to_commands() == [
            "solver FEAST 1 5 100 100"
        ]

    def test_quadratic_feast(self):
        assert QuadraticFEAST(tag=1, eigen_number=5, centre=100).to_commands() == [
            "solver QuadraticFEAST 1 5 100 100"
        ]

    def test_solver_base_is_abstract(self):
        assert Solver.sp_abstract is True

    def test_solver_registered(self):
        assert find_class("Newton", "solver") is Newton
        assert find_class("modifiedNewton", "solver") is ModifiedNewton


class TestSteps:
    def test_static_default(self):
        # the time period is omitted at the default one
        assert StaticStep(tag=1).to_commands() == ["step Static 1"]

    def test_static_time_period(self):
        assert StaticStep(tag=1, time_period=2.5).to_commands() == ["step Static 1 2.5"]

    def test_dynamic(self):
        assert DynamicStep(tag=1, time_period=0.01).to_commands() == [
            "step Dynamic 1 0.01"
        ]

    def test_explicit_dynamic(self):
        assert ExplicitDynamicStep(tag=2).to_commands() == ["step ExplicitDynamic 2"]

    def test_frequency(self):
        assert FrequencyStep(tag=1).to_commands() == ["step Frequency 1 1"]
        assert FrequencyStep(tag=1, eigen_number=10).to_commands() == [
            "step Frequency 1 10"
        ]

    def test_buckle(self):
        assert BuckleStep(tag=1).to_commands() == ["step Buckle 1"]

    def test_arc_length(self):
        assert ArcLengthStep(tag=1).to_commands() == ["step ArcLength 1"]

    def test_optimization(self):
        assert OptimizationStep(tag=1, time_period=3).to_commands() == [
            "step Optimization 1 3"
        ]

    def test_step_base_is_abstract(self):
        assert Step.sp_abstract is True

    def test_set_commands(self):
        step = StaticStep(
            tag=1,
            fixed_step_size=True,
            symm_mat=False,
            system_solver="mumps",
            max_iteration=5,
        )
        assert step.to_commands() == [
            "step Static 1",
            "set fixed_step_size true",
            "set symm_mat false",
            "set system_solver MUMPS",
            "set max_iteration 5",
        ]

    def test_unknown_system_solver_rejected(self):
        with pytest.raises(Exception):
            StaticStep(tag=1, system_solver="bogus")

    def test_linear_system(self):
        step = StaticStep(tag=1, linear_system=True)
        assert step.to_commands() == ["step Static 1", "set linear_system"]


class TestStepCell:
    def test_cell_order(self):
        """The cell exports the step, its sets and every attached object in
        the order the C++ parser consumes them."""
        step = StaticStep(
            tag=1,
            integrator=Newmark(tag=1),
            solver=Newton(tag=2),
            convergers=[
                RelIncreDisp(tag=3, tolerance=1e-4, max_iteration=10, print_flag=True)
            ],
            loads=[
                Cload(tag=4, amplitude_tag=0, magnitude=100, dof="2", object_tags=[2])
            ],
            recorders=[NodeRecorder(tag=5, variable="U", object_tags=[1, 2])],
        )
        lines = cell_commands(step)
        assert lines == [
            "step Static 1",
            "integrator Newmark 1",
            "solver Newton 2",
            "converger RelIncreDisp 3 0.0001 10 true",
            "load Cload 4 0 100 2 2",
            "recorder 5 plain Node U 1 2",
        ]

    def test_cell_empty(self):
        assert cell_commands(StaticStep(tag=1)) == ["step Static 1"]
