"""Tests of the Model container: pools, builder helpers, validation and
export."""

import pytest

from suanpan.base import SuanpanObject
from suanpan.constraint import Embed3D, Fix, LogicCriteriaAll
from suanpan.converger import FixedNumber, RelIncreDisp
from suanpan.domain import (
    B3DC,
    ElementalNonviscous,
    InitialDisplacement,
    LumpedSimple,
    NodalMass,
    Node,
    NodeGroup,
    SimpleScalarExpression,
)
from suanpan.element import T2D2S
from suanpan.load import Cload, CustomAmplitude, Ramp
from suanpan.material import Bilinear1D
from suanpan.model import Model
from suanpan.recorder import NodeRecorder
from suanpan.section import TrussSection
from suanpan.solver import Newmark, Newton
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

    def test_add_routes_every_pool(self):
        model = Model()
        objects = [
            (Node(tag=1, coordinate=[0, 0]), "nodes"),
            (Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5), "materials"),
            (
                SimpleScalarExpression(tag=1, variable_list="x", expression="x * 2"),
                "expressions",
            ),
            (TrussSection(tag=1, area=10, material_tag=1), "sections"),
            (T2D2S(tag=1, node_tags=[1, 2], section_tag=1), "elements"),
            (Ramp(tag=1), "amplitudes"),
            (NodeGroup(tag=1, node_tags=[1, 2]), "groups"),
            (B3DC(tag=1, xyz=[0, 0, 1]), "orientations"),
            (LumpedSimple(tag=1, element_tags=[1]), "modifiers"),
            (
                InitialDisplacement(tag=1, dof=1, magnitude=0.1, node_tags=[1]),
                "initials",
            ),
            (NodalMass(tag=1, node_tag=1, magnitude=2, dof="1"), "masses"),
            (LogicCriteriaAll(tag=1, criterion_tags=[1]), "criteria"),
            (FixedNumber(tag=1), "convergers"),
            (
                Cload(
                    tag=1,
                    amplitude_tag=0,
                    magnitude=1,
                    dof="1",
                    object_tags=[1],
                ),
                "loads",
            ),
            (NodeRecorder(tag=1, variable="U", object_tags=[1]), "recorders"),
            (Fix(tag=1, dof="E", node_tags=[1]), "constraints"),
            (StaticStep(tag=1), "steps"),
        ]
        for obj, pool in objects:
            assert model.add(obj) is obj
            assert getattr(model, pool)[-1] is obj


class TestValidation:
    @pytest.mark.parametrize(
        ("field", "kind", "obj"),
        [
            ("nodes", "node", Node(tag=1, coordinate=[0, 0])),
            (
                "materials",
                "material",
                Bilinear1D(tag=1, elastic_modulus=1, yield_stress=1),
            ),
            (
                "expressions",
                "expression",
                SimpleScalarExpression(tag=1, variable_list="x", expression="x"),
            ),
            ("sections", "section", TrussSection(tag=1, area=1, material_tag=1)),
            (
                "elements",
                "element",
                T2D2S(tag=1, node_tags=[1, 2], section_tag=1),
            ),
            ("amplitudes", "amplitude", Ramp(tag=1)),
            ("groups", "group", NodeGroup(tag=1)),
            ("orientations", "orientation", B3DC(tag=1, xyz=[0, 0, 1])),
            ("modifiers", "modifier", LumpedSimple(tag=1)),
            (
                "loads",
                "load",
                Cload(tag=1, amplitude_tag=0, magnitude=1, dof="1", object_tags=[1]),
            ),
            ("recorders", "recorder", NodeRecorder(tag=1, variable="U")),
            ("criteria", "criterion", LogicCriteriaAll(tag=1, criterion_tags=[1])),
            ("convergers", "converger", FixedNumber(tag=1)),
            ("constraints", "constraint", Fix(tag=1, dof="E", node_tags=[1])),
            ("steps", "step", StaticStep(tag=1)),
        ],
    )
    def test_duplicate_tags_are_rejected(self, field, kind, obj):
        with pytest.raises(ValueError, match=f"duplicate {kind} tag 1"):
            Model(**{field: [obj, obj]})

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

    def test_missing_expression(self):
        with pytest.raises(ValueError, match="missing expression 4"):
            Model(amplitudes=[CustomAmplitude(tag=1, expression_tag=4)])

    def test_missing_step_load_amplitude(self):
        step = StaticStep(
            tag=1,
            loads=[
                Cload(tag=1, amplitude_tag=9, magnitude=1, dof="1", object_tags=[1])
            ],
        )
        with pytest.raises(ValueError, match="missing amplitude 9"):
            Model(steps=[step])

    def test_missing_modifier_element(self):
        with pytest.raises(ValueError, match="missing element 3"):
            Model(modifiers=[LumpedSimple(tag=1, element_tags=[3])])
        with pytest.raises(ValueError, match="missing element 3"):
            Model(
                modifiers=[
                    ElementalNonviscous(
                        tag=1,
                        element_tag=3,
                        m_r=[1],
                        m_i=[1],
                        s_r=[1],
                        s_i=[1],
                    )
                ]
            )

    def test_missing_constraint_element(self):
        with pytest.raises(ValueError, match="missing element 6"):
            Model(constraints=[Embed3D(tag=1, element_tag=6, node_tag=1)])

    def test_absent_optional_references_are_ignored(self):
        Model(modifiers=[LumpedSimple(tag=1)])
        Model(amplitudes=[Ramp(tag=1)])
        Model(constraints=[])

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
            "material Bilinear1D 1 100 5 0.2",
            "section TrussSection 1 10 1",
            "element T2D2S 1 1 2 1",
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

    def test_full_export_order(self):
        model = Model()
        model.add(Node(tag=1, coordinate=[0, 0]))
        model.add(Node(tag=2, coordinate=[1, 0]))
        model.add(Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5))
        model.add(SimpleScalarExpression(tag=1, variable_list="x", expression="x"))
        model.add(TrussSection(tag=1, area=10, material_tag=1))
        model.add(T2D2S(tag=1, node_tags=[1, 2], section_tag=1))
        model.add(Ramp(tag=2))
        model.add(NodeGroup(tag=1, node_tags=[1, 2]))
        model.add(B3DC(tag=1, xyz=[0, 0, 1]))
        model.add(LumpedSimple(tag=1, element_tags=[1]))
        model.add(InitialDisplacement(tag=1, dof=1, magnitude=0.1, node_tags=[1]))
        model.add(NodalMass(tag=1, node_tag=1, magnitude=2, dof="1"))
        model.add(LogicCriteriaAll(tag=1, criterion_tags=[1]))
        model.add(FixedNumber(tag=1))
        model.add(
            Cload(tag=1, amplitude_tag=0, magnitude=1, dof="2", object_tags=[2])
        )
        model.add(NodeRecorder(tag=1, variable="U", object_tags=[2]))
        model.add(Fix(tag=1, dof="E", node_tags=[1]))
        step = StaticStep(tag=1, integrator=Newmark(tag=1), solver=Newton(tag=1))
        step.convergers = [
            RelIncreDisp(tag=1, tolerance=1e-4, max_iteration=10, print_flag=True)
        ]
        model.add(step)

        commands = model.to_commands()
        assert [line.split()[0] for line in commands] == [
            "node",
            "node",
            "material",
            "expression",
            "section",
            "element",
            "amplitude",
            "nodegroup",
            "orientation",
            "modifier",
            "initial",
            "mass",
            "criterion",
            "converger",
            "load",
            "recorder",
            "constraint",
            "step",
            "integrator",
            "solver",
            "converger",
        ]
        assert commands == model.export_text().splitlines()

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
