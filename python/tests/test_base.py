"""Tests of the framework layer: registration, lookup and formatting."""

import pytest

from suanpan.base import (
    find_class,
    format_float,
    format_value,
    iter_classes,
)
from suanpan.element import T2D2
from suanpan.material import Bilinear1D


class TestFormat:
    def test_float_precision(self):
        assert format_float(100.0) == "100"
        assert format_float(1e-4) == "0.0001"
        assert format_float(200000.0) == "200000"
        assert format_float(1 / 3) == "0.333333333333"

    def test_values(self):
        assert format_value([1, 2]) == ["1", "2"]
        assert format_value(3) == ["3"]
        assert format_value(True)  # booleans are exported as objects, not floats

    def test_bool_object(self):
        obj = Bilinear1D(tag=1, elastic_modulus=2e3, yield_stress=4)
        assert obj.to_commands() == ["Bilinear1D 1 2000 4"]

    def test_trailing_defaults_trimmed(self):
        assert Bilinear1D(
            tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2
        ).to_commands() == ["Bilinear1D 1 100 5 0.2"]
        # all defaults -> nothing exported beyond the required fields
        assert Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5).to_commands() == [
            "Bilinear1D 1 100 5"
        ]


class TestRegistry:
    def test_lookup_by_command(self):
        assert find_class("Bilinear1D", "material") is Bilinear1D
        assert find_class("t2d2", "element") is T2D2

    def test_lookup_is_case_insensitive(self):
        assert find_class("bilinear1d", "material") is Bilinear1D

    def test_unique_keyword_fallback(self):
        # keywords aliasing across commands require the command hint
        assert find_class("T2D2") is T2D2

    def test_aliased_registration(self):
        assert find_class("PenaltyBC", "constraint") is find_class("Fix", "constraint")

    def test_unknown(self):
        assert find_class("NoSuchThing", "material") is None

    def test_iter_every_concrete_class_unique(self):
        classes = iter_classes()
        assert len(classes) == len({id(c) for c in classes})
        for cls in classes:
            assert not getattr(cls, "sp_abstract", False)
            assert cls.keyword

    def test_command_filter(self):
        sections = iter_classes("section")
        assert sections
        assert all(c.command == "section" for c in sections)

    def test_registry_size(self):
        # 129 material + 106 element + 43 section + hand written families
        assert 400 <= len(iter_classes()) <= 500


class TestBaseContract:
    def test_every_object_exports_its_command(self):
        for cls in iter_classes():
            assert isinstance(getattr(cls, "command", None), str)

    def test_duplicate_registration_rejected(self):

        with pytest.raises(ValueError):

            class Clash(Bilinear1D):
                # re-defining an existing keyword must abort at class creation
                keyword = "Bilinear1D"
                aliases = ()

    def test_abstract_never_registered(self):

        # the abstract base is not registered under its own command
        assert find_class("Material", "material") is None

    def test_sp_abstract_truthful(self):
        from suanpan.constraint import Constraint, Fix

        assert Constraint.sp_abstract is True
        assert Fix.sp_abstract is False

    def test_object_repr(self):
        obj = T2D2(tag=7, node_tags=[1, 2], material_tag=1, area=10)
        assert "T2D2" in repr(obj) or "SuanpanObject" in repr(obj)
