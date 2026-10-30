"""Element modifiers, mirroring ``create_new_modifier`` in
``Element/ElementParser.cpp`` (the ``modifier`` command).

Modifiers apply to the elements listed by tag.
"""

from __future__ import annotations

from pydantic import Field

from suanpan.base import SuanpanObject, format_value
from suanpan.toolbox.format import FloatList, IntList

__all__ = [
    "ElementalLee",
    "ElementalModal",
    "ElementalNonviscous",
    "ElementalNonviscousGroup",
    "LinearViscosity",
    "LumpedScale",
    "LumpedSimple",
    "Modifier",
    "Rayleigh",
]


class Modifier(SuanpanObject):
    """Base class of element modifiers (``modifier`` command).

    Object tags of the modifier are exported last, after all parameters,
    matching the C++ parser order.
    """

    command = "modifier"
    sp_abstract = True

    element_tags: IntList = Field(
        default_factory=list, description="element tags to modify"
    )

    def to_commands(self) -> list[str]:
        model_fields = type(self).model_fields
        parts = [self.command, self.keyword, *format_value(self.tag)]
        for name, field in model_fields.items():
            if name in ("tag", "element_tags"):
                continue
            value = getattr(self, name)
            if value is None or value == []:
                continue
            parts.extend(format_value(value, field))
        if self.element_tags:
            parts.extend(format_value(self.element_tags))
        return [" ".join(parts)]


class LumpedSimple(Modifier):
    """``modifier LumpedSimple`` (C++ ``LumpedSimple``)."""

    keyword = "LumpedSimple"
    summary = "simplify element mass lumping"


class LumpedScale(Modifier):
    """``modifier LumpedScale`` (C++ ``LumpedScale``)."""

    keyword = "LumpedScale"
    summary = "scale element mass lumping"


class Rayleigh(Modifier):
    """``modifier Rayleigh`` (C++ ``Rayleigh``) -- Rayleigh damping."""

    keyword = "Rayleigh"
    summary = "Rayleigh elemental damping coefficients"

    a: float = Field(description="coefficient a (quadratic term)")
    b: float = Field(description="coefficient b (linear term)")
    c: float = Field(description="coefficient c (static term)")
    d: float = Field(description="coefficient d (constant term)")


class ElementalLee(Modifier):
    """``modifier ElementalLee`` (C++ ``ElementalLee``)."""

    keyword = "ElementalLee"
    summary = "elemental Lee damping (modal history damping)"

    damping_ratio: float = Field(
        default=0.02, description="damping ratio (default 0.02)"
    )


class LinearViscosity(Modifier):
    """``modifier LinearViscosity`` (C++ ``LinearViscosity``)."""

    keyword = "LinearViscosity"
    summary = "elemental linear viscosity"

    mu: float = Field(description="viscosity coefficient")


class ElementalModal(Modifier):
    """``modifier ElementalModal`` (C++ ``ElementalModal``)."""

    keyword = "ElementalModal"
    summary = "elemental modal damping via Rayleigh coefficients"

    a: float = Field(description="coefficient a (quadratic term)")
    b: float = Field(description="coefficient b (linear term)")


class ElementalNonviscous(Modifier):
    """``modifier ElementalNonviscous`` (C++ ``ElementalNonviscous``).

    The damping kernel is given by conjugate complex pairs
    ``m_r, m_i, s_r, s_i`` per mode.
    """

    keyword = "ElementalNonviscous"
    summary = "elemental nonviscous damping"

    element_tag: int = Field(description="single element tag")
    m_r: FloatList = Field(
        default_factory=list, description="real parts of mass kernel modes"
    )
    m_i: FloatList = Field(
        default_factory=list, description="imaginary parts of mass kernel modes"
    )
    s_r: FloatList = Field(
        default_factory=list, description="real parts of kernel decay modes"
    )
    s_i: FloatList = Field(
        default_factory=list, description="imaginary parts of kernel decay modes"
    )

    def to_commands(self) -> list[str]:
        parts = [
            "modifier",
            self.keyword,
            *format_value(self.tag),
            str(self.element_tag),
        ]
        for name in ("m_r", "m_i", "s_r", "s_i"):
            parts.extend(format_value(getattr(self, name)))
        return [" ".join(parts)]


class ElementalNonviscousGroup(ElementalNonviscous):
    """``modifier ElementalNonviscousGroup`` (C++ ``ElementalNonviscousGroup``).

    Same kernel syntax, but the tag refers to an element group.
    """

    keyword = "ElementalNonviscousGroup"
    summary = "group elemental nonviscous damping"
    element_tag: int = Field(description="single element group tag")
