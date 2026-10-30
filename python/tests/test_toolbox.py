"""Tests of the toolbox helpers: dof tokens and list coercion."""

import pytest
from pydantic import BaseModel

from suanpan.toolbox.dof import DOF, parse_dof
from suanpan.toolbox.format import (
    FloatList,
    IntList,
    StrList,
    as_float_list,
    as_int_list,
    as_str_list,
)


class _Holder(BaseModel):
    ints: IntList
    floats: FloatList
    strings: StrList


class TestDof:
    """The token map mirrors ``parse_dof`` in Domain/ConditionalModifier.cpp."""

    def test_single_translation(self):
        assert list(parse_dof("1")) == [DOF.U1]
        assert list(parse_dof("U2")) == [DOF.U2]

    def test_encastre_expansion(self):
        assert list(parse_dof("E")) == [
            DOF.U1,
            DOF.U2,
            DOF.U3,
            DOF.UR1,
            DOF.UR2,
            DOF.UR3,
        ]

    def test_pinned_expansion(self):
        assert list(parse_dof("P")) == [DOF.U1, DOF.U2, DOF.U3]

    def test_symmetry_expansions(self):
        assert list(parse_dof("X")) == [DOF.U1, DOF.UR2, DOF.UR3]
        assert list(parse_dof("Y")) == [DOF.UR1, DOF.U2, DOF.UR3]
        assert list(parse_dof("Z")) == [DOF.UR1, DOF.UR2, DOF.U3]

    def test_rotation_aliases(self):
        assert list(parse_dof("4")) == [DOF.UR1]
        assert list(parse_dof("UR1")) == [DOF.UR1]

    def test_unknown(self):
        assert list(parse_dof("bogus")) == []
        assert list(parse_dof("r")) == []

    def test_case_insensitive(self):
        assert parse_dof("e") == parse_dof("E")


class TestLists:
    """Input files are whitespace separated, mirroring the C++ tokenizer."""

    def test_int_list(self):
        assert as_int_list("1 2 3") == [1, 2, 3]
        assert as_int_list([1, "2"]) == [1, 2]

    def test_float_list(self):
        assert as_float_list("1 2.5 3.") == [1.0, 2.5, 3.0]

    def test_str_list(self):
        assert as_str_list("a b c") == ["a", "b", "c"]

    def test_pydantic_coercion(self):
        holder = _Holder(ints="1 2 3", floats=[4, 5.5], strings="x y")
        assert holder.ints == [1, 2, 3]
        assert holder.floats == [4.0, 5.5]
        assert holder.strings == ["x", "y"]

    def test_empty(self):
        assert as_int_list("") == []
        assert as_int_list(None) == []

    def test_is_true(self):
        from suanpan.toolbox.format import is_true

        assert is_true("true") and is_true("1") and is_true(True)
        assert not is_true("false") and not is_true("0") and not is_true(False)

    def test_commas_not_separators(self):
        # suanPan tokens are whitespace separated; commas stay part of tokens
        with pytest.raises(ValueError):
            as_int_list("1, 2 ,3")
