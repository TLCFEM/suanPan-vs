"""Tests of the generated + hand written element classes."""

import pytest

from suanpan.element import (
    B21,
    B21EH,
    B21EL,
    B31,
    B31OS,
    C3D8,
    C3D8R,
    CSMQ5,
    DCP4,
    DCP4M,
    T2D2,
    T2D2S,
    T3D2,
    Mass,
    PatchCube,
    PatchQuad,
)


class TestTruss:
    def test_t2d2_example(self):
        # `element T2D2 1 1 2 1 10` from Example/Material/Bilinear1D.supan
        obj = T2D2(tag=1, node_tags=[1, 2], material_tag=1, area=10)
        assert obj.to_commands() == ["T2D2 1 1 2 1 10"]

    def test_t2d2_switches(self):
        obj = T2D2(tag=1, node_tags=[1, 2], material_tag=1, area=10, nonlinear=True)
        assert obj.to_commands() == ["T2D2 1 1 2 1 10 true"]

    def test_t3d2(self):
        assert T3D2(tag=1, node_tags=[1, 2], material_tag=1, area=1).to_commands() == [
            "T3D2 1 1 2 1 1"
        ]

    def test_t2d2s(self):
        assert T2D2S(tag=1, node_tags=[1, 2], section_tag=3).to_commands() == [
            "T2D2S 1 1 2 3"
        ]


class TestBeam:
    def test_b21(self):
        obj = B21(tag=1, node_tags=[1, 2], section_tag=1, int_pt=8, nonlinear=True)
        assert obj.to_commands() == ["B21 1 1 2 1 8 true"]

    def test_b21_default(self):
        # section_tag is required, so the export keeps it; the int_pt (6)
        # and nonlinear (false) defaults are eof-guarded and trimmed
        assert B21(tag=1, node_tags=[1, 2], section_tag=1).to_commands() == [
            "B21 1 1 2 1"
        ]

    def test_shared_layout(self):
        # B21EH/B21EL share the identical token stream (C++ which argument)
        assert B21EH.model_fields.keys() == B21.model_fields.keys()
        assert B21EL.model_fields.keys() == B21.model_fields.keys()

    def test_b31_os_variant(self):
        assert B31.keyword == "B31" and B31OS.keyword == "B31OS"
        assert B31OS.model_fields.keys() == B31.model_fields.keys()


class TestSolid:
    def test_c3d8_example(self):
        # `element C3D8 1 1 2 3 4 5 6 7 8 1 G` from the examples
        obj = C3D8(
            tag=1, node_tags=list(range(1, 9)), material_tag=1, reduced_scheme="G"
        )
        assert obj.to_commands() == ["C3D8 1 1 2 3 4 5 6 7 8 1 G"]

    def test_c3d8_default_scheme(self):
        # the optional 'I' token re-parses to the default when omitted
        assert C3D8(
            tag=1, node_tags=list(range(1, 9)), material_tag=1
        ).to_commands() == ["C3D8 1 1 2 3 4 5 6 7 8 1"]

    def test_c3d8r_forces_reduced(self):
        obj = C3D8R(tag=1, node_tags=list(range(1, 9)), material_tag=1)
        assert obj.to_commands()[0].startswith("C3D8R ")

    def test_c3d8_node_count_enforced(self):
        with pytest.raises(Exception):
            C3D8(tag=1, node_tags=[1, 2, 3], material_tag=1)

    def test_dcp4_example(self):
        # `element DCP4 1 1 15 205 50 1 5 5 50` from Example/Element/DCP4.supan
        obj = DCP4(
            tag=1,
            node_tags=[1, 15, 205, 50],
            material_tag=1,
            length=5,
            rate=5,
            thickness=50,
        )
        assert obj.to_commands() == ["DCP4 1 1 15 205 50 1 5 5 50"]

    def test_dcp4m_shared_layout(self):
        assert DCP4M.model_fields.keys() == DCP4.model_fields.keys()


class TestCSMQ:
    def test_node_count_by_keyword(self):
        # new_csmq(size): the count equals the keyword suffix
        with pytest.raises(Exception):
            CSMQ5(tag=1, node_tags=[1, 2, 3], material_tag=1)
        assert CSMQ5(
            tag=1, node_tags=[1, 2, 3, 4, 5], material_tag=1
        ).to_commands() == ["CSMQ5 1 1 2 3 4 5 1"]


class TestMass:
    def test_mass_point(self):
        # C++: tag, node, magnitude
        assert (
            Mass(tag=1, node=2, magnitude=10.0).to_commands()[0].startswith("Mass 1 2")
        )


class TestPatches:
    def test_patch_quad(self):
        obj = PatchQuad(
            tag=1,
            node_tags=[1, 2, 3, 4],
            knot_x=[0, 1],
            knot_y=[0, 1],
            material_tag=5,
            thickness=0.5,
        )
        assert obj.to_commands() == [
            "element PatchQuad 1 -node 1 2 3 4 -knotx 0.0 1.0 -knoty 0.0 1.0"
            " -material 5 -thickness 0.5"
        ]

    def test_patch_quad_default_thickness(self):
        obj = PatchQuad(
            tag=1, node_tags=[1, 2, 3, 4], knot_x=[0, 1], knot_y=[0, 1], material_tag=5
        )
        assert "-thickness" not in obj.to_commands()[0]

    def test_patch_cube(self):
        obj = PatchCube(
            tag=1,
            node_tags=[1, 2, 3, 4, 5, 6, 7, 8],
            knot_x=[0, 1],
            knot_y=[0, 1],
            knot_z=[0, 1],
            material_tag=2,
        )
        tokens = obj.to_commands()[0].split()
        assert tokens[:3] == ["element", "PatchCube", "1"]
        assert "-knotz" in tokens and "-thickness" not in tokens
