"""Tests of the framework layer: registration, lookup and formatting."""

from __future__ import annotations

import json
import types
import typing
import warnings
from pathlib import Path

import pytest
from pydantic import BaseModel

from suanpan.base import (
    SuanpanObject,
    find_class,
    format_float,
    format_value,
    iter_classes,
)
from suanpan.element import T2D2
from suanpan.material import Bilinear1D

DATABASE = Path(__file__).resolve().parents[2] / "data" / "database.json"


def _sample_value(annotation: object) -> object:
    """Build a minimal value for a field annotation.

    The value only has to keep ``to_commands`` working: the registry test
    constructs objects with ``model_construct`` so that validators requiring
    a particular node count or DOF token do not obscure export problems.
    """
    origin = typing.get_origin(annotation)
    arguments = typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType):
        for argument in arguments:
            if argument is not type(None):
                return _sample_value(argument)
        return None
    if origin is typing.Literal:
        return arguments[0] if arguments else None
    if origin in (list, tuple):
        return []
    if origin is dict:
        return {}
    if annotation is int:
        return 1
    if annotation is float:
        return 1.0
    if annotation is bool:
        return True
    if annotation is str:
        return "x"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        values = {
            name: (1 if name == "tag" else _sample_value(field.annotation))
            for name, field in annotation.model_fields.items()
            if field.is_required()
        }
        return annotation.model_construct(**values)
    return None


def _minimal_instance(cls: type[SuanpanObject]) -> SuanpanObject:
    """Construct an instance with a dummy value for every required field."""
    values = {
        name: (1 if name == "tag" else _sample_value(field.annotation))
        for name, field in cls.model_fields.items()
        if field.is_required()
    }
    return cls.model_construct(**values)


def _database() -> dict[str, dict]:
    document = json.loads(DATABASE.read_text())
    commands = {command["name"].lower(): command for command in document["commands"]}
    for command in document["commands"]:
        for alias in command.get("aliases", []):
            commands.setdefault(alias.lower(), command)
    return commands


def _has_spelling(commands: dict[str, dict], command: str, spelling: str) -> bool:
    spec = commands.get(command)
    if spec is None:
        return False
    token = spelling.lower()
    for item in spec.get("types") or []:
        if item["name"].lower() == token:
            return True
        if any(alias.lower() == token for alias in item.get("aliases", [])):
            return True
    other = commands.get(token)
    return other is not None and other.get("category") == spec.get("category")


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
        assert obj.to_commands() == ["material Bilinear1D 1 2000 4"]

    def test_trailing_defaults_trimmed(self):
        assert Bilinear1D(
            tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2
        ).to_commands() == ["material Bilinear1D 1 100 5 0.2"]
        # all defaults -> nothing exported beyond the required fields
        assert Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5).to_commands() == [
            "material Bilinear1D 1 100 5"
        ]

    def test_negative_zero_and_scientific(self):
        assert format_float(0) == "0"
        assert format_float(-0.0) == "-0"
        assert format_float(-1.25) == "-1.25"
        assert format_float(1.5e-7) == "1.5e-07"

    def test_non_finite_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError):
                format_float(value)

    def test_bool_values(self):
        assert format_value(True) == ["true"]
        assert format_value(False) == ["false"]

    def test_mixed_list(self):
        assert format_value([1, 2.5, True, "x"]) == ["1", "2.5", "true", "x"]

    def test_suanpan_object_exports_its_tag(self):
        assert format_value(T2D2(tag=7, node_tags=[1, 2], material_tag=1, area=1)) == [
            "7"
        ]

    def test_unsupported_value_rejected(self):
        with pytest.raises(TypeError):
            format_value(object())

    def test_to_line_requires_a_single_command(self):
        from suanpan.step import StaticStep

        assert Bilinear1D(tag=1, elastic_modulus=1, yield_stress=1).to_line() == (
            "material Bilinear1D 1 1 1"
        )
        with pytest.raises(ValueError):
            StaticStep(tag=1, fixed_step_size=True).to_line()


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

    def test_every_keyword_and_alias_resolves(self):
        for cls in iter_classes():
            assert cls.command, cls.__name__
            assert cls.keyword, cls.__name__
            for spelling in (cls.keyword, *cls.aliases):
                assert find_class(spelling, cls.command) is cls, (
                    f"{cls.__name__}: {spelling}"
                )

    def test_iter_classes_is_sorted_and_unique(self):
        classes = iter_classes()
        assert classes == sorted(
            classes, key=lambda cls: (cls.command, cls.keyword.lower())
        )
        assert len(classes) == len({id(cls) for cls in classes})

    def test_command_filter_partitions_the_registry(self):
        commands = {cls.command for cls in iter_classes()}
        assert commands
        total = 0
        for command in commands:
            filtered = iter_classes(command)
            assert filtered
            assert all(cls.command == command for cls in filtered)
            total += len(filtered)
        assert total == len(iter_classes())

    def test_default_constructible_classes_export(self):
        checked = 0
        for cls in iter_classes():
            required = [
                name
                for name, field in cls.model_fields.items()
                if name != "tag" and field.is_required()
            ]
            if required:
                continue
            # this generator deliberately rejects an empty plane description
            if cls.__name__ == "NodeGroupGenerateByPlane":
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                obj = cls(tag=1)
            commands = obj.to_commands()
            assert commands, cls.__name__
            assert cls.keyword.lower() in "\n".join(commands).lower() or (
                cls.command.lower() in "\n".join(commands).lower()
            )
            checked += 1
        assert checked > 100, f"only checked {checked} classes"

    def test_every_registered_class_exports_a_valid_script(self):
        for cls in iter_classes():
            obj = _minimal_instance(cls)
            commands = obj.to_commands()
            assert commands, cls.__name__
            assert all(isinstance(line, str) and line for line in commands)
            text = "\n".join(commands)
            assert cls.keyword.lower() in text.lower() or cls.command.lower() in text.lower()
            for line in commands:
                assert "\n" not in line, f"{cls.__name__}: {line!r}"
                assert line == line.strip(), f"{cls.__name__}: {line!r}"
                assert "  " not in line, f"{cls.__name__}: {line!r}"
                assert "\t" not in line, f"{cls.__name__}: {line!r}"


class TestDatabaseConsistency:
    """Keep the Python registry and the generated TypeScript database in sync."""

    def test_every_python_class_has_a_database_spelling(self):
        commands = _database()
        for cls in iter_classes():
            assert cls.command.lower() in commands, cls.__name__
            for spelling in (cls.keyword, *cls.aliases):
                assert _has_spelling(commands, cls.command, spelling), (
                    f"{cls.command} {spelling} ({cls.__name__})"
                )

    def test_every_database_type_has_a_python_class(self):
        commands = _database()
        missing: list[str] = []
        for name, command in commands.items():
            if name != command["name"].lower():
                continue
            category = command.get("category")
            if not category:
                continue
            for item in command.get("types") or []:
                if find_class(item["name"], category) is None:
                    missing.append(f"{category} {item['name']}")
                for alias in item.get("aliases", []):
                    if find_class(alias, category) is None:
                        missing.append(f"{category} {alias}")
        assert not missing, missing


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
