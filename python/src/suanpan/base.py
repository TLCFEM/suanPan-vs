"""Core object model shared by every suanPan Python class.

The suanPan input language is a line based command language.  Every line
starts with a *command* (``material``, ``element``, ``node``, ...) followed
by a *keyword* (``Bilinear1D``, ``T2D2``, ...) and a list of space separated
arguments.  ``SuanpanObject`` models that relationship with pydantic:

* ``command``  -- the top level command word,
* ``keyword``  -- the object keyword (also called type in the C++ parser),
* ``aliases``  -- alternative spellings accepted by the C++ parser,
* ``tag``      -- the object tag, always the first argument.

Field definition order == command line argument order.  Optional arguments
are simply ``None`` (or carry a default) and are omitted when exporting.
The C++ source of truth for every keyword is the corresponding
``*Parser.cpp`` file; the machine readable extraction lives in
``suanpan-py/specs``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

__all__ = [
    "FLAG",
    "GROUP",
    "OMIT",
    "POSITIONAL",
    "SP_KIND",
    "SuanpanObject",
    "find_class",
    "flag_field",
    "format_float",
    "format_value",
    "group_field",
    "iter_classes",
    "omit_field",
    "sp_group",
    "sp_kind",
]


# --------------------------------------------------------------------------- #
# field metadata                                                              #
# --------------------------------------------------------------------------- #
#: key used in ``json_schema_extra`` to mark the export behaviour of a field
SP_KIND = "sp_kind"

#: positional arguments are exported in field definition order (default)
POSITIONAL = "positional"
#: keyword options such as ``-type0`` are exported after positional arguments
FLAG = "flag"
#: fields sharing a group are exported together or not at all
GROUP = "group"
#: fields that never appear in the exported file
OMIT = "omit"


def _field(kind: str, group: str | None = None, **kwargs: Any) -> Any:
    """Build a ``Field`` carrying suanPan export metadata."""
    extra = dict(kwargs.pop("json_schema_extra", {}) or {})
    extra[SP_KIND] = kind
    if group is not None:
        extra["sp_group"] = group
    return Field(json_schema_extra=extra, **kwargs)


def flag_field(group: str | None = None, **kwargs: Any) -> Any:
    """A field exported as a keyword option, e.g. ``-memory``."""
    return _field(FLAG, group, **kwargs)


def group_field(group: str, **kwargs: Any) -> Any:
    """A positional field belonging to an all-or-nothing group."""
    return _field(GROUP, group, **kwargs)


def omit_field(**kwargs: Any) -> Any:
    """A field that participates in validation but is never exported."""
    return _field(OMIT, **kwargs)


def sp_extra(field: Any) -> dict[str, Any]:
    """Return the suanPan metadata attached to a field definition."""
    extra = field.json_schema_extra
    return extra if isinstance(extra, dict) else {}


def sp_kind(field: Any) -> str:
    """Return the export kind of a field definition."""
    return str(sp_extra(field).get(SP_KIND, POSITIONAL))


def sp_group(field: Any) -> str | None:
    """Return the export group of a field definition."""
    group = sp_extra(field).get("sp_group")
    return str(group) if group is not None else None


# --------------------------------------------------------------------------- #
# value formatting                                                            #
# --------------------------------------------------------------------------- #


def format_float(value: float) -> str:
    """Format a float the way the suanPan parser expects it."""
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        raise ValueError(f"cannot export non-finite float {value!r}")
    return format(value, ".12g")


def format_value(value: Any, field: Any = None) -> list[str]:
    """Format a single field value into the tokens it exports to."""
    if value is None:
        return []
    if isinstance(value, bool):
        return ["true" if value else "false"]
    if isinstance(value, (int, float)):
        return [format_float(value)]
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        tokens: list[str] = []
        for item in value:
            if isinstance(item, bool):
                tokens.append("true" if item else "false")
            elif isinstance(item, (int, float)):
                tokens.append(format_float(item))
            elif isinstance(item, str):
                tokens.append(item)
            else:
                tokens.append(str(item))
        return tokens
    if isinstance(value, SuanpanObject):
        return [str(value.tag)]
    raise TypeError(f"cannot export value {value!r}")


def register_class(cls: type[SuanpanObject]) -> type[SuanpanObject]:
    """Explicitly register a class."""
    if not cls.sp_abstract:
        _register(cls)
    return cls


# --------------------------------------------------------------------------- #
# the base object                                                             #
# --------------------------------------------------------------------------- #


class SuanpanObject(BaseModel):
    """Base class of every object representable in a suanPan input file."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )

    #: top level command word, e.g. ``material``
    command: ClassVar[str] = ""
    #: object keyword, e.g. ``Bilinear1D``
    keyword: ClassVar[str] = ""
    #: alternative keywords accepted by the C++ parser
    aliases: ClassVar[tuple[str, ...]] = ()
    #: short description shown in listings
    summary: ClassVar[str] = ""
    #: mark intermediate base classes so they stay out of the registry
    sp_abstract: ClassVar[bool] = False

    tag: PositiveInt

    # -- export ------------------------------------------------------------- #
    def to_commands(self) -> list[str]:
        """Return the suanPan command lines this object represents."""
        fields = type(self).model_fields

        # collect all-or-nothing groups: group name -> member names
        group_members: dict[str, list[str]] = {}
        for name, field in fields.items():
            if sp_kind(field) == GROUP:
                group_members.setdefault(sp_group(field) or name, []).append(name)
        active_groups = {
            group
            for group, members in group_members.items()
            if any(getattr(self, name) is not None for name in members)
        }

        parts = [self.command, self.keyword, *format_value(self.tag)]
        # (name, value, field, tokens) of the positional (non flag) fields
        positional: list[tuple[str, Any, Any, list[str]]] = []
        for name, field in fields.items():
            if name == "tag":
                continue
            kind = sp_kind(field)
            if kind in (OMIT, FLAG):
                continue
            if kind == GROUP:
                group = sp_group(field) or name
                if group not in active_groups or group_members[group][0] != name:
                    continue
                tokens: list[str] = []
                for member in group_members[group]:
                    tokens.extend(format_value(getattr(self, member), fields[member]))
                positional.append((name, None, field, tokens))
                continue
            value = getattr(self, name)
            if value is None or value == [] or value == {}:
                continue
            positional.append((name, value, field, format_value(value, field)))
        # trim the trailing run of eof-guarded defaults (tokens are
        # positional in the C++ parser, mirroring `get_optional_input`)
        while positional:
            name, value, field, tokens = positional[-1]
            if (
                value is None
                or field.is_required()
                or value != field.get_default(call_default_factory=True)
            ):
                break
            positional.pop()
        for entry in positional:
            parts.extend(entry[3])
        for name, field in fields.items():
            if sp_kind(field) != FLAG:
                continue
            value = getattr(self, name)
            if value is None or value == [] or value == {}:
                continue
            parts.append(name)
            parts.extend(format_value(value, field))
        return [" ".join(parts)]

    def to_line(self) -> str:
        """Return the single command line this object represents."""
        commands = self.to_commands()
        if len(commands) != 1:
            raise ValueError(f"{type(self).__name__} exports {len(commands)} commands")
        return commands[0]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register every concrete subclass in the keyword registry."""
        super().__init_subclass__(**kwargs)
        # make ``sp_abstract`` truthful on every class: without an explicit
        # declaration it would be inherited from an abstract base
        declared = cls.__dict__.get("sp_abstract", False)
        cls.sp_abstract = declared
        if not declared and cls.__dict__.get("keyword", ""):
            _register(cls)

    def __str__(self) -> str:
        try:
            return self.to_line()
        except Exception:
            return super().__str__()


# --------------------------------------------------------------------------- #
# keyword registry                                                            #
# --------------------------------------------------------------------------- #

#: (command, keyword) (lowercase) -> class
_REGISTRY: dict[tuple[str, str], type[SuanpanObject]] = {}


def _register(cls: type[SuanpanObject]) -> None:
    if not cls.keyword:
        return
    command = cls.command.lower()
    for key in (cls.keyword, *cls.aliases):
        key = key.lower()
        registry_key = (command, key)
        existing = _REGISTRY.get(registry_key)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"keyword {key!r} of command {command!r} "
                f"already registered by {existing.__name__}"
            )
        _REGISTRY[registry_key] = cls


def find_class(keyword: str, command: str | None = None) -> type[SuanpanObject] | None:
    """Look up the class registered for ``keyword`` (case-insensitive).

    Without ``command`` the match must be unique across all commands.
    """
    key = keyword.lower()
    if command is not None:
        return _REGISTRY.get((command.lower(), key))
    matches = [cls for (cmd, kw), cls in _REGISTRY.items() if kw == key]
    return matches[0] if len(matches) == 1 else None


def iter_classes(command: str | None = None) -> list[type[SuanpanObject]]:
    """List registered classes, optionally filtered by command word."""
    seen: dict[int, type[SuanpanObject]] = {}
    for (cmd, key), cls in _REGISTRY.items():
        if command is not None and cmd != command.lower():
            continue
        seen[id(cls)] = cls
    return sorted(seen.values(), key=lambda c: (c.command, c.keyword.lower()))
