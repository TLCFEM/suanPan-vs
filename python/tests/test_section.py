"""Tests of the generated section classes."""

import pytest

from suanpan.section import (
    EU2D,
    NM3D3,
    Box3D,
    Cell2D,
    Cell3D,
    Cell3DOS,
    Circle1D,
    Fibre3D,
    ISection2D,
    ISection3D,
    TrussSection,
)


class TestCells:
    def test_cell3d(self):
        # the optional eccentricities re-parse to zero when omitted
        assert Cell3D(tag=1, area=10.0, material_tag=2).to_commands() == [
            "Cell3D 1 10 2"
        ]

    def test_cell2d_bar_alias(self):
        # Cell2D == Bar2D in the dispatch table
        assert Cell2D.keyword == "Cell2D"

    def test_cell3dos_example(self):
        # `section Cell3DOS 1 10. 1. 1. 1. 2 10. 10.` from the examples
        obj = Cell3DOS(
            tag=1,
            area=10.0,
            omega=1.0,
            py=1.0,
            pz=1.0,
            material_tag=2,
            eccentricity_a=10.0,
            eccentricity_b=10.0,
        )
        assert obj.to_commands() == ["Cell3DOS 1 10 1 1 1 2 10 10"]


class TestIShape:
    def test_isection2d_example(self):
        # `section ISection2D 1 200 25 100 25 150 25 1 6` from the examples
        obj = ISection2D(
            tag=1, dim=[200, 25, 100, 25, 150, 25], material_tag=1, int_pt=8
        )
        assert obj.to_commands() == ["ISection2D 1 200 25 100 25 150 25 1 8"]

    def test_isection3d(self):
        obj = ISection3D(tag=1, dim=[200, 25, 100, 25, 150, 25], material_tag=1)
        assert obj.to_commands() == ["ISection3D 1 200 25 100 25 150 25 1"]

    def test_dim_has_six_components(self):
        # the C++ handler reads vec(6); fewer components are fatal
        with pytest.raises(Exception):
            ISection2D(tag=1, dim=[200, 25], material_tag=1)

    def test_eccentricities(self):
        # eccentricity follows int_pt, so the default int_pt is kept in the
        # prefix up to the last non-default value
        obj = ISection2D(
            tag=1, dim=[200, 25, 100, 25, 150, 25], material_tag=1, eccentricity=5.0
        )
        assert obj.to_commands() == ["ISection2D 1 200 25 100 25 150 25 1 6 5"]


class TestEurocode:
    def test_eu2d_designation_first(self):
        # designation precedes the tag in the C++ parser; the scale (1.),
        # int_pt (6) and eccentricity (0.) defaults are trimmed
        obj = EU2D(tag=9, designation="IPE300", material_tag=1)
        assert obj.to_commands() == ["IPE300 EU2D 9 1"]

    def test_eu2d_scale(self):
        obj = EU2D(tag=9, designation="HEA200", material_tag=1, scale=2.0)
        assert obj.to_commands()[0].split()[:5] == ["HEA200", "EU2D", "9", "1", "2"]


class TestFibre:
    def test_fibre3d(self):
        assert Fibre3D(tag=3, object_tags=[1, 2, 4]).to_commands() == [
            "Fibre3D 3 1 2 4"
        ]


class TestNM:
    def test_nm3d3(self):
        obj = NM3D3(
            tag=1,
            ea=1e6,
            eis=1e5,
            eiw=1e4,
            np=6,
            mps=1.0,
            mpw=1.0,
            c=1.0,
            h1=2.0,
            h2=3.0,
            h3=4.0,
            k1=5.0,
            k2=6.0,
            linear_density=1.0,
        )
        assert obj.to_commands()[0].startswith("NM3D3 1 ")


class TestPrimitives:
    def test_box3d(self):
        assert Box3D(
            tag=1, width=1.0, height=2.0, thickness=0.1, material_tag=2
        ).to_commands() == ["Box3D 1 1 2 0.1 2"]

    def test_circle1d(self):
        assert Circle1D(tag=1, radius=5.0, material_tag=2).to_commands() == [
            "Circle1D 1 5 2"
        ]

    def test_truss_section(self):
        obj = TrussSection(tag=1, area=100.0, material_tag=1)
        assert obj.to_commands()[0].startswith("TrussSection 1 100 1")
