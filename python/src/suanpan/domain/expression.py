"""Expressions, mirroring ``Toolbox/ExpressionParser.cpp``
(the ``expression`` command).

Expressions implement node/element DAMP, CDP and other user hooks.
"""

from __future__ import annotations

from pydantic import Field

from suanpan.base import SuanpanObject, format_value

__all__ = ["Expression", "SimpleScalarExpression", "SimpleVectorExpression"]


class Expression(SuanpanObject):
    """Base class of expressions (``expression`` command)."""

    command = "expression"
    sp_abstract = True


class SimpleScalarExpression(Expression):
    """``expression SimpleScalar`` (C++ ``SimpleScalarExpression``).

    The source string is a single token; expressions containing spaces
    must be given as a file path (the C++ parser substitutes the file
    contents when the string points to an existing file).
    """

    keyword = "SimpleScalar"
    summary = "simple scalar expression"

    variable_list: str = Field(
        description="vertical bar separated input variable names"
    )
    expression: str = Field(
        description="expression source text or path to an expression file"
    )

    def to_commands(self) -> list[str]:
        parts = ["expression", self.keyword, *format_value(self.tag)]
        parts += [self.variable_list, self.expression]
        return [" ".join(parts)]


class SimpleVectorExpression(Expression):
    """``expression SimpleVector`` (C++ ``SimpleVectorExpression``)."""

    keyword = "SimpleVector"
    summary = "simple vector expression"

    input_list: str = Field(description="vertical bar separated input variable names")
    output_list: str = Field(description="vertical bar separated output variable names")
    expression: str = Field(
        description="expression source text or path to an expression file"
    )

    def to_commands(self) -> list[str]:
        parts = ["expression", self.keyword, *format_value(self.tag)]
        parts += [self.input_list, self.output_list, self.expression]
        return [" ".join(parts)]
