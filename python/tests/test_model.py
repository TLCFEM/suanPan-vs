"""Tests of the Model container: pools, builder helpers, validation and
export."""

import pytest

from suanpan.base import SuanpanObject
from suanpan.constraint import Fix
from suanpan.converger import RelIncreDisp
from suanpan.domain import InitialDisplacement, Node
from suanpan.element import T2D2S
from suanpan.load import Cload
from suanpan.material import Bilinear1D
from suanpan.model import Model
from suanpan.recorder import NodeRecorder
from suanpan.section import TrussSection
from suanpan.solver import Newton
from suanpan.step import StaticStep


def _bilin_model() -> Model:
    """Rebuild `Example/Material/Bilinear1D.supan` as a Model."""
    model = Model(title="Bilinear1D example")
    model.add(Node(tag=1, coordinate=[0, 0]))
    model.add(Node(tag=2, coordinate=[1, 0]))
    model.add(
        Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2)
    )
    model.add(TrussSection(tag=1, area=10, material_tag=1))
    model.add(T2D2S(tag=1, node_tags=[1, 2], section_tag=1))
    model.add(Fix(tag=1, dof="E", node_tags=[1]))
    step = StaticStep(tag=1)
    step.solver = Newton(tag=1)
    step.convergers = [
        RelIncreDisp(tag=1, tolerance=1e-4, max_iteration=10, print_flag=True)
    ]
    model.add(Cload(tag=1, amplitude_tag=0, magnitude=100, dof="2", object_tags=[2]))
    model.add(NodeRecorder(tag=1, variable="U", object_tags=[2]))
    model.add(step)
    return model


class TestPools:
    def test_add_routes_by_type(self):
        model = Model()
        node = model.add(Node(tag=1, coordinate=[0, 0]))
        mat = model.add(Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5))
        step = model.add(StaticStep(tag=1))
        assert model.nodes == [node]
        assert model.materials == [mat]
        assert model.steps == [step]
        assert isinstance(node, SuanpanObject)

    def test_add_rejects_unknown(self):
        with pytest.raises(TypeError):
            Model().add("bogus")

    def test_step_helper(self):
        model = Model()
        step = model.step(StaticStep(tag=2))
        assert model.steps == [step]

    def test_step_children_dispatched(self):
        # constraints attached to a step land in the step, not a global pool
        model = Model()
        step = StaticStep(tag=1)
        step.constraints = [Fix(tag=1, dof="E", node_tags=[1])]
        model.add(step)
        assert model.constraints == []
        assert model.steps[0].constraints == [step.constraints[0]]


class TestValidation:
    def test_duplicate_node_tag(self):
        with pytest.raises(ValueError, match="duplicate node tag"):
            Model(
                nodes=[Node(tag=1, coordinate=[0, 0]), Node(tag=1, coordinate=[1, 0])]
            )

    def test_duplicate_step_tag(self):
        with pytest.raises(ValueError, match="duplicate step tag"):
            Model(steps=[StaticStep(tag=1), StaticStep(tag=1)])

    def test_missing_material(self):
        with pytest.raises(ValueError, match="missing material 9"):
            Model(
                materials=[Bilinear1D(tag=1, elastic_modulus=1, yield_stress=1)],
                sections=[TrussSection(tag=1, area=10, material_tag=9)],
            )

    def test_missing_section(self):
        with pytest.raises(ValueError, match="missing section 9"):
            Model(
                materials=[Bilinear1D(tag=1, elastic_modulus=1, yield_stress=1)],
                sections=[TrussSection(tag=1, area=10, material_tag=1)],
                elements=[T2D2S(tag=1, node_tags=[1, 2], section_tag=9)],
            )

    def test_missing_amplitude(self):
        with pytest.raises(ValueError, match="missing amplitude 5"):
            Model(
                loads=[
                    Cload(tag=1, amplitude_tag=5, magnitude=1, dof="1", object_tags=[1])
                ]
            )

    def test_amplitude_zero_is_global(self):
        # amplitude 0 is the built-in constant ramp
        Model(
            loads=[Cload(tag=1, amplitude_tag=0, magnitude=1, dof="1", object_tags=[1])]
        )

    def test_validate_assignment(self):
        model = _bilin_model()
        with pytest.raises(Exception):
            model.nodes = [
                Node(tag=1, coordinate=[0, 0]),
                Node(tag=1, coordinate=[1, 0]),
            ]


class TestExport:
    def test_export_order(self):
        model = Model()
        model.add(Node(tag=1, coordinate=[0, 0]))
        model.add(
            Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2)
        )
        model.add(TrussSection(tag=1, area=10, material_tag=1))
        model.add(T2D2S(tag=1, node_tags=[1, 2], section_tag=1))
        model.add(InitialDisplacement(tag=0, dof=1, magnitude=0.01, node_tags=[1]))
        model.add(Fix(tag=1, dof="E", node_tags=[1]))
        lines = model.to_commands()
        # initials export in the middle of the file, constraints last
        assert lines == [
            "node 1 0 0",
            "Bilinear1D 1 100 5 0.2",
            "TrussSection 1 10 1",
            "T2D2S 1 1 2 1",
            "initial disp 0.01 1 1",
            "constraint Fix 1 E 1",
        ]

    def test_title_comment(self):
        assert Model(title="demo").to_commands() == ["# demo"]

    def test_export_text_ends_with_newline(self):
        text = Model(title="t").export_text()
        assert text == "# t\n"

    def test_save(self, tmp_path):
        path = _bilin_model().save(tmp_path / "model.supan")
        assert path.read_text().splitlines()[0] == "# Bilinear1D example"
        assert "step Static 1" in path.read_text().splitlines()

    def test_step_cell_appended(self):
        # global pools export first; the step cell (step line, solver and
        # its attached converger) closes the file
        model = _bilin_model()
        lines = model.to_commands()
        assert lines[-1] == "converger RelIncreDisp 1 0.0001 10 true"
        assert "step Static 1" in lines
        assert "solver Newton 1" in lines
        assert "load Cload 1 0 100 2 2" in lines
        assert "recorder 1 plain Node U 2" in lines
