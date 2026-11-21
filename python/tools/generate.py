#!/usr/bin/env python3
"""Generate bulk pydantic classes for materials, elements and sections
from the unified C++ dispatch tables and the machine-readable parser
specs in ``specs/``.

The keyword, alias and factory information is read from the
``TokenRegistry`` initializer lists of ``MaterialParser.cpp``,
``ElementParser.cpp`` and ``SectionParser.cpp`` -- the ground truth of
dispatch.  The parameter layout and defaults of each handler come from
the corresponding YAML spec.

The result is written as real Python sources:

* ``src/suanpan/material/_generated.py``
* ``src/suanpan/element/_generated.py``
* ``src/suanpan/section/_generated.py``

Handlers whose command line cannot be expressed by the generic
positional exporter (flags with values, custom option loops) are
reported as skipped and hand written later in ``<family>/_special.py``.

Usage::

    PYTHONPATH=src python3 tools/generate.py --source ../../suanPan
"""

from __future__ import annotations

import argparse
import keyword as py_keyword
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # suanPan-vs/python/
SPECS = ROOT / "specs"
SRC = ROOT / "src" / "suanpan"
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "scripts"))

from suanpan_parser import (  # noqa: E402
    REGISTRY_FUNCTIONS,
    RegistryEntry,
    grouped_registry,
    read_registry,
    read_registry_tag_in_dispatcher,
)

# elements whose node count equals the keyword suffix (new_csmq(size))
NODE_COUNT: dict[str, int] = {"CSMQ5": 5, "CSMQ6": 6, "CSMQ7": 7, "CSMQ8": 8}

# section handlers reading a fixed size dim vector (vec(6)/vec(4))
DIM_LENGTH: dict[str, int] = {
    "HSection2D": 6,
    "ISection2D": 6,
    "ISection2DC": 6,
    "ISection3D": 6,
    "ISection3DC": 6,
    "TSection2D": 4,
    "TSection2DC": 4,
    "TSection3D": 4,
    "TSection3DC": 4,
}

# hand written classes are not generated
SPECIALS: dict[str, set[str]] = {
    "material": {"Balloon", "Balloon1D", "ConcreteK4", "MultiSubloading1D"},
    "element": {"PatchQuad", "PatchCube"},
    "section": set(),
}


@dataclass
class Param:
    name: str
    type: str
    required: bool
    default: object
    length: int | None
    note: str = ""
    size_note: str = ""


@dataclass
class Entry:
    keyword: str
    aliases: list[str]
    cpp: str
    params: list[Param] = field(default_factory=list)
    flags: list = field(default_factory=list)
    rest: object = None
    notes: str = ""


def parse_scalar(text: object, ptype: str) -> object:
    """Parse a C++ literal, recorded in YAML, into a Python value."""
    if ptype == "expression_tag":
        ptype = "int"
    elif ptype == "enum":
        ptype = "str"
    if text is None:
        return None
    if isinstance(text, (list, tuple)):
        conv = float if ptype == "float_list" else int
        return [conv(v) for v in text]
    if isinstance(text, (int, float)):
        return text
    text = str(text).strip()
    if ptype == "bool":
        return text.lower() in {"true", "1", "yes"}
    if ptype in ("float_list", "int_list"):
        parts = [s for s in re.split(r"[, ]+", text) if s]
        conv = float if ptype == "float_list" else int
        try:
            return [conv(p) for p in parts]
        except ValueError:
            return None
    if ptype == "float":
        try:
            return float(text)
        except ValueError:
            return None
    if ptype == "int":
        try:
            return int(float(text))
        except ValueError:
            return None
    return text


def normalise_params(raw: list) -> list[Param]:
    result: list[Param] = []
    for item in raw or []:
        name = str(item["name"]).strip()
        entry_text = str(item)
        if "dispatch arg" in name or "dispatch arg" in entry_text:
            continue  # dispatcher argument, not a command line token
        ptype = str(item.get("type", "float"))
        required = bool(item.get("req", False))
        default = parse_scalar(item.get("default"), ptype)
        length = item.get("len") or item.get("size")
        note = re.sub(r"\s+", " ", str(item.get("meaning", "")))
        result.append(
            Param(
                name=name,
                type=ptype,
                required=required,
                default=default,
                length=int(length) if length else None,
                note=note,
            )
        )
    return result


def parse_rest(rest: object) -> Param | None:
    """Normalise the ``rest`` field into a trailing Param."""
    if rest is None:
        return None
    if isinstance(rest, dict):
        ptype = str(rest.get("type", "")).strip()
        if ptype not in ("float_list", "int_list", "str_list"):
            return None
        required = bool(rest.get("required", rest.get("req", False)))
        meaning = str(rest.get("meaning") or rest.get("description") or "")
        if "name" in rest:
            name = str(rest["name"])
        elif "tags" in meaning:
            name = "object_tags"
        else:
            name = "rest_values"
        return Param(
            name=name,
            type=ptype,
            required=required,
            default=[],
            length=None,
            note=meaning,
        )
    text = str(rest)
    match = re.match(r"^(float_list|int_list|str)", text)
    if not match:
        return None
    return Param(
        name="rest_values",
        type=match.group(1),
        required=False,
        default=[],
        length=None,
        note=text,
    )


def load_spec(spec_file: str) -> dict[str, Entry]:
    data = yaml.safe_load(SPECS.joinpath(spec_file).read_text())
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                data = value
                break
    entries: dict[str, Entry] = {}
    for item in data:
        kw = str(item.get("keyword", "")).strip()
        if not kw:
            continue
        entries[kw] = Entry(
            keyword=kw,
            aliases=[str(a) for a in item.get("aliases", [])],
            cpp=str(item.get("cpp", kw)),
            params=normalise_params(item.get("params")),
            flags=item.get("flags") or [],
            rest=item.get("rest"),
            notes=str(item.get("notes", "")),
        )
    return entries


def has_real_flags(entry: Entry) -> bool:
    for flag in entry.flags:
        if "dispatch arg" in str(flag):
            continue
        return True
    return False


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", name.strip())
    if not cleaned:
        return "value"
    if cleaned[0].isdigit():
        cleaned = "v" + cleaned
    if py_keyword.iskeyword(cleaned):
        cleaned += "_"
    return cleaned


def class_name(keyword: str) -> str:
    name = re.sub(r"[^0-9A-Za-z_]", "", keyword)
    if name[0].isdigit():
        name = "E" + name
    assert name and not py_keyword.iskeyword(name)
    return name


def field_annotation(ptype: str) -> str:
    return {
        "float_list": "FloatList",
        "int_list": "IntList",
        "str_list": "StrList",
        "expression_tag": "int",  # tag of an expression object
        "enum": "str",
    }.get(ptype, ptype)


def parse_scalar_type(ptype: str, value: object) -> object:
    """Convert a raw YAML scalar into a Python value of the field type."""
    if ptype in ("expression_tag", "int"):
        return None if value is None else int(value)
    return value


def literal(value: object) -> str:
    if value is None:
        return "None"
    return repr(value)


def emit_fields(
    entry: Entry, rest: Param | None, given: dict | None = None
) -> tuple[list[str], list[str]]:
    """Return (field lines, doc lines) excluding the inherited tag."""
    params = entry.params
    doc_names = []
    lines: list[str] = []
    for given_name, given_value in (given or {}).items():
        # constructor-time constant (e.g. a fixed int_pt count)
        lines.append(
            f"    {safe_name(given_name)}: ClassVar[{type(given_value).__name__}] = {given_value!r}"
        )
    for param in params:
        doc_names.append(param.name)
        annotation = field_annotation(param.type)
        field_name = safe_name(param.name)
        try:
            required = param.required and param.default is None
        except Exception:
            required = param.required
        count_note = ""
        if param.length and param.type in ("float_list", "int_list"):
            count_note = f"exactly {param.length} values"
        if param.length:
            note = param.size_note or param.note or count_note
            if count_note and not note:
                note = count_note
            note = count_note
        else:
            note = param.size_note or param.note or ""
        if required:
            assert param.default is None
            description = param.name + (f" ({note})" if note else "")
            lines.append(
                f"    {field_name}: {annotation} = Field(description={description!r})"
            )
        else:
            default_literal = literal(param.default)
            description = param.name + (f" ({note})" if note else "")
            # an eof-guarded optional without a C++ default value: the
            # parser branches on `command.eof()` and omits the parameter
            field_annotation_used = (
                f"{annotation} | None" if param.default is None else annotation
            )
            line = (
                f"    {field_name}: {field_annotation_used} = Field(default={default_literal}, "
                f"description={description!r})"
            )
            lines.append(line)
    if rest is not None:
        doc_names.append(rest.name)
        annotation = field_annotation(rest.type)
        desc = (rest.note or rest.name).strip()
        if len(desc) > 240:
            desc = desc[:237] + "..."
        lines.append(f"    {rest.name}: {annotation} = Field(")
        lines.append(f"        default=[], description={desc!r})")
    return lines, doc_names


def emit_dim_validator(keyword: str) -> str:
    """Fixed length ``dim`` validator for the section families reading
    ``vec(6)``/``vec(4)`` dimension vectors."""
    count = DIM_LENGTH.get(keyword)
    if count is None:
        return ""
    return (
        (
            '    @field_validator("dim")\n'
            "    @classmethod\n"
            "    def _check_dim(cls, value: FloatList) -> FloatList:\n"
            "        if len(value) != 0:\n"
            '            raise ValueError("dim requires exactly 0 values")\n'
            "        return value"
        )
        .replace("!= 0", f"!= {count}")
        .replace("exactly 0", f"exactly {count}")
    )


def emit_validators(entry: Entry, node_count: int | None = None) -> list[str]:
    """Fixed size list validators taken from the note wording."""
    validators: list[str] = []
    for param in entry.params:
        if param.type != "int_list" or param.name.lower() not in (
            "node_tags",
            "tag_nodes",
        ):
            continue
        match = (
            re.search(r"exactly (\d+) node tags", entry.notes)
            if node_count is None
            else None
        )
        if node_count is not None:
            count = node_count
        elif not match:
            continue
        else:
            count = int(match.group(1))
        fname = safe_name(param.name)
        validators.append(
            f'    @field_validator("{fname}")\n'
            "    @classmethod\n"
            f"    def _check_{fname}(cls, value: IntList) -> IntList:\n"
            "        if len(value) != count:\n"
            f'            raise ValueError({param.name!r} + " requires exactly {count} node tags")\n'
            "        return value".replace(" != count:", f" != {count}:")
        )
    return validators


def emit_class(
    entry: Entry,
    keyword: str,
    aliases: list[str],
    family: str,
    rest: Param | None,
    extra: dict | None = None,
    node_count: int | None = None,
    factory: str | None = None,
) -> str:
    params = [p for p in entry.params if p.name.lower() != "tag"]
    designation_first = (
        bool(params)
        and params[0].name == "designation"
        and len(entry.params) > 1
        and entry.params[1].name.lower() == "tag"
    )
    cpp = (factory or entry.cpp or keyword).split("<", 1)[0]
    lines: list[str] = []
    lines.append(f"class {class_name(keyword)}({family}):")
    lines.append(f'    """``{family.lower()} {keyword}`` (C++ ``{cpp}``).')
    if entry.notes:
        notes = re.sub(r"\s+", " ", entry.notes).replace("\\" + '"', "")
        notes = notes.replace('"', "'")
        if len(notes) > 320:
            notes = notes[:317] + "..."
        lines.append("")
        lines.append(f"    {notes}")
    lines.append('    """')
    lines.append("")
    lines.append(f"    keyword = {keyword!r}")
    if aliases:
        lines.append("    aliases = (" + ", ".join(repr(a) for a in aliases) + ",)")
    lines.append(f"    summary = {cpp!r}")
    if designation_first:
        lines.append("    designation_first = True")
    field_lines, doc_names = emit_fields(entry, rest, extra)
    for field_line in field_lines:
        lines.append(field_line)
    if not field_lines:
        lines.append("    pass")
    for validator in emit_validators(entry, node_count):
        lines.append("")
        lines.append(validator)
    dim_validator = emit_dim_validator(keyword)
    if dim_validator:
        lines.append("")
        lines.append(dim_validator)
    lines.append("")
    lines.append("")
    return "\n".join(lines)


TEMPLATE = '''\
"""Bulk generated {family} classes.

DO NOT EDIT BY HAND: generated by ``tools/generate.py`` from the parser
specs in ``specs/``, whose layouts and defaults come from ``{cpp}`` --
the only source of truth.

{tag_note}

The generic export emits ``{word} <keyword> <tag> <required parameters>
<optional parameters up to the last one that differs from its default>
<trailing list>``, mirroring the eof-guarded token consumption of the
C++ handlers.  Coded sections put the designation between the keyword
and the tag: ``section EU2D IPE300 9 ...``.
"""

from __future__ import annotations

from typing import ClassVar

{imports}


class {family}(SuanpanObject):
    """Base class of {plural} (the ``{word}`` command)."""

    command = "{word}"
    sp_abstract = True
    #: whether a leading designation token precedes the tag
    designation_first: ClassVar[bool] = False

    def to_commands(self) -> list[str]:
        fields = self._ordered_fields()
        last = -1
        for index, name in enumerate(fields):
            value, required = self._value_and_required(name)
            if required or self._differs(name, value):
                last = index
        parts = []
        if self.designation_first:
            # C++ command line: ``section EU2D IPE300 9 ...``. The
            # designation follows the keyword and precedes the tag.
            parts += [self.command, self.keyword, self.designation, str(self.tag)]
            fields = [n for n in fields if n != "designation"]
            # indices shift down by one once the designation is removed
            last -= 1
        else:
            parts += [self.command, self.keyword, str(self.tag)]
        for name in fields[: last + 1]:
            parts += self._tokens(name)
        return [" ".join(parts)]

    def _ordered_fields(self) -> list[str]:
        from suanpan.base import sp_kind

        return [name for name, fout in type(self).model_fields.items()
                if name not in ("tag",) and sp_kind(fout) != "omit"]

    def _value_and_required(self, name: str):
        from pydantic.fields import FieldInfo

        fout: FieldInfo = type(self).model_fields[name]
        value = getattr(self, name)
        return value, fout.is_required()

    def _differs(self, name: str, value) -> bool:
        from pydantic.fields import FieldInfo

        fout: FieldInfo = type(self).model_fields[name]
        if fout.is_required():
            return True
        default = fout.get_default(call_default_factory=True)
        if isinstance(value, bool) or isinstance(default, bool):
            if (value or False) == (default or False):
                return False
            return bool(value) != bool(default)
        if isinstance(default, (list, tuple)) and not default:
            return bool(value)
        if default is None:
            return value is not None
        return value != default

    def _tokens(self, name: str) -> list[str]:
        value = getattr(self, name)
        if value is None:
            return []
        if isinstance(value, bool):
            return ["true" if value else "false"]
        return format_value(value)
'''


def format_source(content: str) -> str:
    """Run ``ruff format`` on the generated source when it is available.

    Formatting here keeps ``--check`` deterministic: the committed files
    are produced by exactly the same code path as the comparison input.
    """
    ruff = shutil.which("ruff")
    if ruff is None:
        return content
    try:
        result = subprocess.run(
            [ruff, "format", "--stdin-filename", "generated.py", "-"],
            input=content,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return content
    return result.stdout


def render(family: str, cpp: str, classes: list[str], tag_note: str) -> str:
    word = family.lower()
    body = "\n\n".join(classes)

    pydantic = []
    if re.search(r"\bField\(", body):
        pydantic.append("Field")
    if "@field_validator" in body:
        pydantic.append("field_validator")

    formats = [name for name in ("FloatList", "IntList", "StrList") if name in body]

    imports = []
    if pydantic:
        imports.append("from pydantic import " + ", ".join(pydantic))
        imports.append("")
    imports.append("from suanpan.base import SuanpanObject, format_value")
    if formats:
        imports.append("from suanpan.toolbox.format import " + ", ".join(formats))

    header = TEMPLATE.format(
        family=family,
        cpp=cpp,
        word=word,
        plural=word + "s",
        tag_note=tag_note,
        imports="\n".join(imports),
    )
    return header + "\n\n" + body


def merge_specs(*specs: dict[str, Entry]) -> dict[str, Entry]:
    """Merge spec sets, preferring entries with a richer field list."""
    merged: dict[str, Entry] = {}
    for part in specs:
        for key, entry in part.items():
            if key not in merged or len(entry.params) > len(merged[key].params):
                merged[key] = entry
    return merged


def is_stub(entry: Entry) -> bool:
    """Whether a spec entry only records an out-of-range handler."""
    return not entry.params and not entry.rest and "outside assigned range" in entry.notes


def spec_lookup(specs: dict[str, Entry], keyword: str) -> str | None:
    """Find a spec keyword case-insensitively."""
    if keyword in specs:
        return keyword
    return next((key for key in specs if key.lower() == keyword.lower()), None)


def build_base_layouts(
    groups: dict[str, list[RegistryEntry]], specs: dict[str, Entry]
) -> dict[str, str]:
    """Map a factory name without template arguments to a spec entry.

    Template variants such as ``new_b21<0>``/``new_b21<2>`` and monolithic
    switches such as ``new_dc3d4<false>``/``<true>`` share one command-line
    layout.  The registry groups expose that relation directly.
    """
    layouts: dict[str, str] = {}
    for entries in groups.values():
        base = entries[0].base_factory
        if base in layouts:
            continue

        for entry in entries:
            keyword = spec_lookup(specs, entry.keyword)
            if keyword is not None and not is_stub(specs[keyword]):
                layouts[base] = keyword
                break
        if base in layouts:
            continue

        bare = base[4:] if base.startswith("new_") else base
        for keyword, spec in specs.items():
            if keyword.lower() == bare and not is_stub(spec):
                layouts[base] = keyword
                break
    return layouts


def resolve_spec(
    specs: dict[str, Entry],
    layouts: dict[str, str],
    entries: list[RegistryEntry],
) -> str | None:
    """Resolve the spec entry describing the token stream of a keyword group."""
    for entry in entries:
        keyword = spec_lookup(specs, entry.keyword)
        if keyword is not None and not is_stub(specs[keyword]):
            return keyword
    return layouts.get(entries[0].base_factory)


def emit_alias_class(
    alias: str, canonical: str, family: str, factory: str | None
) -> str:
    """Emit a compatibility spelling that is not registered separately."""
    cpp = (factory or "").split("<", 1)[0]
    lines = [
        f"class {class_name(alias)}({class_name(canonical)}):",
        f'    """Alternative spelling of ``{canonical}`` (C++ ``{cpp}``)."""',
        "",
        f"    keyword = {alias!r}",
        "    aliases = ()",
        "    sp_abstract = True",
        "",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=os.environ.get("SUANPAN_SOURCE", str(REPO.parent / "suanPan")),
        type=Path,
        help="path to the suanPan checkout",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the generated files are out of date instead of writing them",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    for category in ("material", "element", "section"):
        if not (source / REGISTRY_FUNCTIONS[category][0]).exists():
            raise SystemExit(f"cannot locate suanPan parser source at {source}")

    material_specs = merge_specs(
        load_spec("material_a.yaml"), load_spec("material_b.yaml")
    )
    element_specs = merge_specs(
        load_spec("element_a.yaml"), load_spec("element_b.yaml")
    )
    section_specs = load_spec("section.yaml")

    jobs = [
        (
            "Material",
            "material",
            "material",
            material_specs,
            "Material/MaterialParser.cpp",
        ),
        (
            "Element",
            "element",
            "element",
            element_specs,
            "Element/ElementParser.cpp",
        ),
        (
            "Section",
            "section",
            "section",
            section_specs,
            "Section/SectionParser.cpp",
        ),
    ]

    stale: list[Path] = []
    for family, folder, category, specs, cpp in jobs:
        groups = grouped_registry(read_registry(source, category))
        layouts = build_base_layouts(groups, specs)

        special = SPECIALS.get(folder, set())
        emitted: list[str] = []
        handled: set[str] = set()
        skipped: list[str] = []

        for factory, entries in groups.items():
            canonical = entries[0].keyword
            aliases = [entry.keyword for entry in entries[1:]]

            if canonical in special:
                handled.update(entry.keyword for entry in entries)
                continue

            spec_keyword = resolve_spec(specs, layouts, entries)
            if spec_keyword is None:
                skipped.append(f"{canonical} (no spec entry)")
                handled.update(entry.keyword for entry in entries)
                continue

            entry = specs[spec_keyword]
            if has_real_flags(entry):
                skipped.append(f"{canonical} (flag options)")
                handled.update(item.keyword for item in entries)
                continue

            rest = parse_rest(entry.rest)
            if rest is not None and any(
                p.name.lower() == rest.name.lower() and p.name != rest.name
                for p in entry.params
            ):
                # naming collision: rest wins, drop the colliding param
                entry.params = [
                    p for p in entry.params if p.name.lower() != rest.name.lower()
                ]

            emitted.append(
                emit_class(
                    entry,
                    canonical,
                    aliases,
                    family,
                    rest,
                    node_count=NODE_COUNT.get(canonical),
                    factory=factory,
                )
            )
            for alias in aliases:
                emitted.append(emit_alias_class(alias, canonical, family, factory))
            handled.update(item.keyword for item in entries)

        tag_note = (
            "The object tag is read by the C++ dispatcher and passed to the\n"
            "handler (suanPan #410); it is not part of the handler's token stream."
            if read_registry_tag_in_dispatcher(source, category)
            else "Each C++ handler reads the object tag itself (suanPan #410 left\n"
            "groups handler-owned); the tag is the first token of\n"
            "the handler's stream."
        )

        out_dir = SRC / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "_generated.py"
        content = format_source(render(family, cpp, emitted, tag_note))

        if args.check:
            if not out.exists() or out.read_text() != content:
                stale.append(out)
        else:
            out.write_text(content)

        print(
            f"{family}: {len(handled)} keywords, {len(emitted)} emitted, "
            f"{len(skipped)} skipped -> {out}"
        )
        for item in skipped:
            print(f"  skipped: {item}")

    if stale:
        print("generated files are out of date:")
        for path in stale:
            print(f"  {path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
