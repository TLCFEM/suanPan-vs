#!/usr/bin/env python3
"""Extract a machine-readable suanPan command/object schema from the manual.

The suanPan manual (../suanPan-manual/docs) documents every command and every
concrete object type using a very regular idiom::

    ## Syntax

    ```text title="EB21"
    element EB21 (1) (2) (3) (4) (5) (6) [7]
    # (1) int, unique element tag
    # (2) int, node i
    ...
    # [7] bool string, nonlinear geometry switch, default: false
    ```

This script walks the documentation, parses those fenced blocks and emits a
single JSON file consumed by the extension at runtime.  It is intentionally
defensive: a page that does not follow the idiom is skipped rather than
aborted so that the schema can always be regenerated.

Usage::

    python3 scripts/extract_schema.py [--manual PATH] [--output PATH]

The default manual location is ``../../suanPan-manual/docs`` relative to this
repository, which matches the three-repository layout used during development.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# static vocabulary (kept in sync with the C++ source, see DESIGN.md)
# --------------------------------------------------------------------------

#: category keyword -> (section, description)
CATEGORIES: dict[str, tuple[str, str]] = {
    "element": ("Library/Element", "finite elements"),
    "mass": ("Library/Element", "point/body masses"),
    "modifier": ("Library/Element", "element modifiers"),
    "orientation": ("Library/Element", "orientations"),
    "material": ("Library/Material", "material models"),
    "section": ("Library/Section", "sections"),
    "constraint": ("Library/Constraint", "constraints / boundary conditions"),
    "load": ("Library/Constraint", "loads"),
    "amplitude": ("Library/Amplitude", "amplitudes"),
    "step": ("Library/Step", "analysis steps"),
    "solver": ("Library/Solver", "nonlinear solvers"),
    "integrator": ("Library/Integrator", "time integrators"),
    "converger": ("Library/Converger", "convergence criteria"),
    "criterion": ("Library/Criterion", "stopping criteria"),
    "recorder": ("Library/Recorder", "recorders"),
    "group": ("Library/Group", "node/element groups"),
    "expression": ("Library", "expressions"),
    "interaction": ("Library", "interactions"),
    "initial": ("Collection/Define", "initial conditions"),
    "import": ("Collection/Define", "external modules"),
}

#: top-level commands that are not object factories.  Populated from the
#: command collection pages plus the dispatch table in Toolbox/command.cpp.
TOP_LEVEL: set[str] = {
    "exit", "quit", "overview", "file", "var", "variable", "domain",
    "enable", "disable", "mute", "erase", "delete", "remove", "list",
    "protect", "save", "set", "suspend", "use", "command", "example",
    "precheck", "analyze", "analyse", "fullname", "pwd", "sleep",
    "benchmark", "clear", "reset", "summary", "terminal", "t", "upsampling",
    "response_spectrum", "sdof_response", "license", "version", "plot",
    "peek", "qrcode", "help", "domain",
    "recorder", "hdf5recorder", "plainrecorder",
    "fix", "fix2", "multiplierbc", "penaltybc", "groupmultiplierbc",
    "grouppenaltybc", "mpc", "nodefacet", "nodeline", "embed2d", "embed3d",
    "fixedlength2d", "fixedlength3d", "r2d2", "r3d2", "sleeve2d", "sleeve3d",
    "particlecollision2d", "particlecollision3d", "moleculardynamics2d",
    "moleculardynamics3d", "lmpotential2d" if False else "ljpotential2d",
    "acceleration", "bodyforce", "cload", "disp", "displacement", "dispload",
    "groupbodyforce", "groupcload", "groupdisp", "groupdisplacement",
    "groupdispload", "lineudl2d", "lineudl3d", "referenceload", "refforce",
    "refload", "groupreferenceload", "grouprefforce", "grouprefload",
    "supportacceleration", "supportdisplacement", "supportvelocity",
    "generate", "generatebyplane", "generatebypoint", "generatebyrule",
    "groupgroup", "customnodegroup", "nodegroup", "elementgroup",
    "materialtest1d", "materialtest2d", "materialtest3d",
    "materialtestbyload1d", "materialtestbyload2d", "materialtestbyload3d",
    "materialtestbystrainhistory", "materialtestbystresshistory",
    "materialtestwithbase3d", "materialtestbyloadwithbase3d",
    "sectiontest1d", "sectiontest2d", "sectiontest3d",
    "sectiontestbydeformationhistory", "materialtest1d",
}

#: recognised DoF identifiers, mirroring parse_dof() in
#: Domain/ConditionalModifier.cpp and Recorder/OutputType.h.
DOF_TOKENS = [
    "PINNED", "P", "ENCASTRE", "E", "XSYMM", "X", "YSYMM", "Y", "ZSYMM", "Z",
    "1", "2", "3", "4", "5", "6", "U1", "U2", "U3", "U4", "U5", "U6",
    "UR1", "UR2", "UR3", "FU1", "FU2", "FU3", "FUR1", "FUR2", "FUR3",
    "RADIAL", "AXIAL", "RS", "RW", "DAMAGE", "PRESSURE", "TEMPERATURE", "WARP",
]

#: recorder/output tokens, mirroring Recorder/OutputType.h.
OUTPUT_TOKENS = [
    "U", "U1", "U2", "U3", "UR1", "UR2", "UR3", "V", "V1", "V2", "V3",
    "VR1", "VR2", "VR3", "A", "A1", "A2", "A3", "AR1", "AR2", "AR3",
    "S", "S11", "S22", "S33", "S12", "S23", "S13", "SP", "E", "E11", "E22",
    "E33", "E12", "E23", "E13", "EE", "PE", "HIST", "YF", "KE", "SE", "VE",
    "NVE", "K", "M", "RF", "DF", "IF", "GDF", "GIF", "HYDRO", "MISES",
    "EEQ", "EEEQ", "PEEQ", "DAMAGE", "DT", "DC", "NONLOCAL", "PP", "VF",
    "LITR", "BEAME", "BEAMS", "AMP", "NL",
]

#: alias command -> owning object category, mirroring the dispatch in
#: Toolbox/command.cpp (loads, constraints, groups, recorders).
ALIAS_CATEGORY: dict[str, str] = {}
for _name in (
    "fix", "fix2", "penaltybc", "multiplierbc", "groupmultiplierbc",
    "grouppenaltybc", "mpc", "nodefacet", "nodeline", "embed2d", "embed3d",
    "fixedlength2d", "fixedlength3d", "r2d2", "r3d2", "sleeve2d", "sleeve3d",
    "particlecollision2d", "particlecollision3d", "moleculardynamics2d",
    "moleculardynamics3d", "ljpotential2d", "rigidwall", "rigidwallpenalty",
    "rigidwallmultiplier", "restitutionwall", "restitutionwallpenalty",
    "finiterestitutionwall", "finiterestitutionwallpenalty",
    "finiterestitutionwallmultiplier", "finiterigidwall",
    "finiterigidwallpenalty", "finiterigidwallmultiplier", "maxforce2d",
    "maxforce3d", "maxgap2d", "maxgap3d", "mingap2d", "mingap3d",
    "maximumgap2d", "maximumgap3d", "minimumgap2d", "minimumgap3d",
):
    ALIAS_CATEGORY[_name] = "constraint"
for _name in (
    "acceleration", "bodyforce", "cload", "disp", "displacement", "dispload",
    "groupbodyforce", "groupcload", "groupdisp", "groupdisplacement",
    "groupdispload", "lineudl2d", "lineudl3d", "referenceload", "refforce",
    "refload", "groupreferenceload", "grouprefforce", "grouprefload",
    "supportacceleration", "supportdisplacement", "supportvelocity",
):
    ALIAS_CATEGORY[_name] = "load"
for _name in (
    "group", "customnodegroup", "elementgroup", "groupgroup", "nodegroup",
    "generate", "generatebyplane", "generatebypoint", "generatebyrule",
):
    ALIAS_CATEGORY[_name] = "group"
for _name in ("recorder", "plainrecorder", "hdf5recorder"):
    ALIAS_CATEGORY[_name] = "recorder"
# `node` is a top-level command but carries the tag namespace of node objects
ALIAS_CATEGORY["node"] = "node"

#: enumerated string options used by the `set` command and solver options.
ENUM_OPTIONS: dict[str, list[str]] = {
    "color_model": ["WP", "MIS", "OFF"],
    "linear_system": ["LAPACK", "SPIKE", "SUPERLU", "LIS", "MUMPS", "CUDA",
                      "PARDISO", "FGMRES", "MAGMA"],
    "system_solver": ["LAPACK", "SPIKE", "SUPERLU", "LIS", "MUMPS", "CUDA",
                      "PARDISO", "FGMRES", "MAGMA"],
    "sub_system_solver": ["LAPACK", "SPIKE", "SUPERLU", "LIS", "MUMPS", "CUDA",
                          "PARDISO", "FGMRES", "MAGMA"],
    "precision": ["DOUBLE", "FULL", "SINGLE", "MIXED"],
    "bool": ["true", "false", "yes", "no", "on", "off", "1", "0", "t", "f",
             "y", "n"],
}

# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------

TITLE_RE = re.compile(r"^#\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^```+\s*([A-Za-z0-9_+-]*)\s*(.*)$")
TITLE_ATTR_RE = re.compile(r'title\s*=\s*"([^"]*)"')
# a syntax line uses the manual's placeholder notation, e.g. `node (1) [2...]`
PLACEHOLDER_RE = re.compile(r"[\(\[]\s*\d")
PARAM_RE = re.compile(
    r"^#\s*[\(\[]\s*(\d+)\s*(?:\.\.\.\s*(\d+)?|\s*\.\.\.)?\s*[\)\]]\s*"
    r"([^,]+?)\s*(?:,\s*(.*))?$"
)
DEFAULT_RE = re.compile(r",?\s*default\s*:\s*(.*)\s*$", re.IGNORECASE)

TYPE_ALIASES = {
    "int": "integer",
    "integer": "integer",
    "unsigned": "integer",
    "uword": "integer",
    "uint": "integer",
    "double": "number",
    "real": "number",
    "float": "number",
    "string": "string",
    "str": "string",
    "bool string": "boolean",
    "bool": "boolean",
    "boolean": "boolean",
    "double/int": "number/string",
    "int/double": "number/string",
    "any": "string",
}

CATEGORY_TOKENS = set(CATEGORIES)


def normalise_type(raw: str) -> str:
    key = raw.strip().lower().replace(",", " ")
    key = re.sub(r"\s+", " ", key)
    return TYPE_ALIASES.get(key, key or "string")


@dataclass
class Param:
    index: int
    required: bool
    variadic: bool
    end: int | None
    type: str
    description: str
    default: str | None
    optional_group: bool = False

    def to_json(self) -> dict:
        out: dict = {
            "index": self.index,
            "required": self.required,
            "variadic": self.variadic,
            "type": self.type,
            "description": self.description,
        }
        if self.end is not None:
            out["end"] = self.end
        if self.default is not None:
            out["default"] = self.default
        if self.optional_group:
            out["optionalGroup"] = True
        return out


@dataclass
class Form:
    syntax: str
    keyword: str
    object_type: str | None
    invoke: str

    def params_json(self, params: list[Param]) -> dict:
        return {
            "syntax": self.syntax,
            "keyword": self.keyword,
            "invoke": self.invoke,
            "params": [p.to_json() for p in params],
        }


@dataclass
class Entry:
    name: str
    kind: str  # "command" | "type"
    category: str | None
    summary: str
    doc: str
    forms: list[dict] = field(default_factory=list)


def parse_param(line: str) -> Param | None:
    m = PARAM_RE.match(line)
    if not m:
        return None
    index = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else None
    raw_type = m.group(3)
    desc = (m.group(4) or "").strip()
    default = None
    dm = DEFAULT_RE.search(desc)
    if dm:
        default = dm.group(1).strip()
        desc = DEFAULT_RE.sub("", desc).strip().rstrip(",").strip()
    # group notation like (2...5) / [(4) (5) (6)...]
    variadic = "..." in line.split(",")[0] or end is not None or "..." in line[:line.find(",") if "," in line else len(line)]
    return Param(
        index=index,
        required="(" in line[: line.find(")") + 1] if ")" in line else False,
        variadic=variadic,
        end=end,
        type=normalise_type(raw_type),
        description=desc,
        default=default,
    )


def split_syntax_params(block_lines: list[str]) -> list[tuple[str, list[str]]]:
    """Pair each syntax line with its parameter comments.

    A run of consecutive syntax lines followed by one parameter block shares
    that block (e.g. ``fix`` / ``fix2`` / ``multiplierbc`` in ``bc.md``), while
    alternating syntax/parameter pairs keep their own parameters.
    """
    pairs: list[tuple[str, list[str]]] = []
    pending: list[tuple[str, list[str]]] = []
    buffer: list[str] = []

    def flush() -> None:
        # close the current run only once parameters have been seen; a run of
        # consecutive syntax lines accumulates in `pending` until then
        if pending and buffer:
            for _, params in pending:
                params.extend(buffer)
            pending.clear()
        buffer.clear()

    for raw in block_lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            if PARAM_RE.match(line.strip()):
                buffer.append(line.strip())
            else:
                # a descriptive comment ends the current syntax/parameter run
                flush()
        else:
            flush()
            pair: tuple[str, list[str]] = (line.strip(), [])
            pairs.append(pair)
            pending.append(pair)
    flush()
    return pairs


def parse_form(syntax: str) -> tuple[str, str | None, str] | None:
    tokens = syntax.split()
    if not tokens:
        return None
    keyword = tokens[0].lower()
    object_type: str | None = None
    invoke = tokens[0]
    # the second token is only an object type when it is a plain identifier;
    # generic pages write placeholders such as `(1)` or `<name>` instead.
    if (keyword in CATEGORY_TOKENS and len(tokens) >= 2
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tokens[1])):
        object_type = tokens[1]
        invoke = f"{tokens[0]} {tokens[1]}"
    return keyword, object_type, invoke


def parse_markdown(path: Path, rel: str) -> Entry | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    name = path.stem
    summary = ""
    for line in lines:
        tm = TITLE_RE.match(line)
        if tm:
            name = tm.group(1).strip()
            break
    # first prose line after the heading
    seen_heading = False
    for line in lines:
        if TITLE_RE.match(line):
            seen_heading = True
            continue
        if not seen_heading:
            continue
        s = line.strip()
        if not s or s.startswith(("#", "*", "!", "[", ">", "`", "|", "-")):
            continue
        summary = s
        break

    forms: list[dict] = []
    i = 0
    while i < len(lines):
        fm = FENCE_RE.match(lines[i])
        if not fm:
            i += 1
            continue
        lang = fm.group(1)
        info = fm.group(2)
        # collect block until closing fence
        j = i + 1
        block: list[str] = []
        while j < len(lines) and not lines[j].lstrip().startswith("```"):
            block.append(lines[j])
            j += 1
        # A syntax block is a `text` fence, or an untyped fence that carries
        # the `# (n) ...` parameter convention.  Everything else is an example.
        params_present = any(l.lstrip().startswith("#") for l in block)
        if lang == "text" or (lang == "" and params_present):
            # Only treat a block as a syntax specification when it uses the
            # manual's placeholder notation.  Plain `text` blocks are examples
            # and are ignored.
            for syntax, param_lines in split_syntax_params(block):
                if not PLACEHOLDER_RE.search(syntax):
                    continue
                parsed = parse_form(syntax)
                if not parsed:
                    continue
                keyword, object_type, invoke = parsed
                params = [
                    p for p in (parse_param(l) for l in param_lines)
                    if p is not None
                ]
                forms.append(
                    {
                        "syntax": syntax,
                        "keyword": keyword,
                        "objectType": object_type,
                        "invoke": invoke,
                        "params": [p.to_json() for p in params],
                    }
                )
        i = j + 1

    if not forms:
        return None

    return Entry(name=name, kind="type", category=None, summary=summary,
                 doc=rel, forms=forms)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def build(manual: Path, snippet_files: list[Path] | None = None) -> dict:
    commands: dict[str, Entry] = {}
    types: dict[str, Entry] = {}
    seen_forms: set[tuple[str, str]] = set()

    # Library pages are the canonical, parameter-complete source; process them
    # first so their summaries/docs win over the terser Collection pages.
    paths = sorted(
        (p for p in manual.rglob("*.md")
         if (p.relative_to(manual).as_posix().startswith("Library/")
             or p.relative_to(manual).as_posix().startswith("Collection/"))),
        key=lambda p: (not p.relative_to(manual).as_posix().startswith("Library/"),
                       p.relative_to(manual).as_posix()),
    )

    for path in paths:
        rel = path.relative_to(manual).as_posix()
        entry = parse_markdown(path, rel)
        if entry is None:
            continue
        for form in entry.forms:
            dedupe_key = (form["invoke"].lower(), form["syntax"].lower())
            if dedupe_key in seen_forms:
                continue
            seen_forms.add(dedupe_key)
            kw = form["keyword"]
            obj = form["objectType"]
            if obj:
                # object type page; prefer the page title's casing (e.g. the
                # syntax writes `step static` while the page is titled `Static`)
                display = entry.name if entry.name.lower() == obj.lower() else obj
                key = obj.lower()
                t = types.setdefault(
                    key,
                    Entry(name=display, kind="type", category=kw,
                          summary=entry.summary, doc=rel),
                )
                if entry.summary and not t.summary:
                    t.summary = entry.summary
                t.forms.append(form)
            else:
                key = kw
                c = commands.setdefault(
                    key,
                    Entry(name=kw, kind="command", category=None,
                          summary=entry.summary, doc=rel),
                )
                if entry.summary and not c.summary:
                    c.summary = entry.summary
                c.forms.append(form)

    # keep only object types that map onto a real category keyword
    types = {k: v for k, v in types.items() if v.category in CATEGORY_TOKENS}

    def dump(entries: dict[str, Entry]) -> dict:
        out = {}
        for k, e in sorted(entries.items()):
            out[k] = {
                "name": e.name,
                "kind": e.kind,
                "category": e.category,
                "summary": e.summary,
                "doc": e.doc,
                "forms": e.forms,
            }
        return out

    schema = {
        "version": 1,
        "categories": {k: {"path": v[0], "description": v[1]}
                       for k, v in CATEGORIES.items()},
        "commands": dump(commands),
        "types": dump(types),
        "aliasCategory": ALIAS_CATEGORY,
        "dofTokens": DOF_TOKENS,
        "outputTokens": OUTPUT_TOKENS,
        "enumOptions": ENUM_OPTIONS,
    }

    if snippet_files:
        new_commands, new_types = ingest_snippets(schema, snippet_files)
        print(f"  snippet fill-in: +{new_commands} commands, +{new_types} types")

    return schema


def ingest_snippets(schema: dict, snippet_files: list[Path]) -> tuple[int, int]:
    """Merge entries from the shipped snippet JSON files.

    The snippet library enumerates object types that the manual may not yet
    document (or document on a theory-only page).  Documentation entries win;
    snippets only fill the gaps.  Returns (new_commands, new_types).
    """
    # `${1:(1)}` -> `(1)`, `${3:[3]}` -> `[3]`
    slot_re = re.compile(r"\$\{\d+:([\(\[])(\d+(?:\.\.\.\d+)?)[\)\]]\}")

    def normalise_syntax(line: str) -> str:
        return slot_re.sub(lambda m: f"{m.group(1)}{m.group(2)}"
                           + ("]" if m.group(1) == "[" else ")"), line)

    new_commands = new_types = 0
    for path in snippet_files:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, item in data.items():
            body = item.get("body") or []
            if not body:
                continue
            syntax = normalise_syntax(body[0]).strip()
            if not PLACEHOLDER_RE.search(syntax):
                continue
            parsed = parse_form(syntax)
            if not parsed:
                continue
            keyword, object_type, invoke = parsed
            params = [
                p for p in (parse_param(l.strip()) for l in body[1:])
                if p is not None
            ]
            form = {
                "syntax": syntax,
                "keyword": keyword,
                "objectType": object_type,
                "invoke": invoke,
                "params": [p.to_json() for p in params],
            }
            summary = item.get("description", "")
            if object_type and object_type.lower() not in schema["types"]:
                schema["types"][object_type.lower()] = {
                    "name": object_type,
                    "kind": "type",
                    "category": keyword if keyword in schema["categories"] else None,
                    "summary": summary,
                    "doc": f"snippet:{key}",
                    "origin": "snippet",
                    "forms": [form],
                }
                new_types += 1
            elif not object_type and keyword not in schema["commands"]:
                schema["commands"][keyword] = {
                    "name": keyword,
                    "kind": "command",
                    "category": None,
                    "summary": summary,
                    "doc": f"snippet:{key}",
                    "origin": "snippet",
                    "forms": [form],
                }
                new_commands += 1
    return new_commands, new_types


def default_manual() -> Path:
    here = Path(__file__).resolve().parent
    candidate = here.parent.parent / "suanPan-manual" / "docs"
    return candidate


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", type=Path, default=default_manual())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "syntaxes"
        / "commands.json",
    )
    args = parser.parse_args(argv)

    if not args.manual.is_dir():
        print(f"manual directory not found: {args.manual}", file=sys.stderr)
        return 1

    syntax_dir = Path(__file__).resolve().parent.parent / "syntaxes"
    snippet_files = [
        syntax_dir / "snippets.json",
        syntax_dir / "nz_sections.json",
        syntax_dir / "eu_sections.json",
        syntax_dir / "us_sections.json",
    ]

    schema = build(args.manual, snippet_files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, indent=2, sort_keys=False) + "\n",
                           encoding="utf-8")

    print(
        f"wrote {args.output} "
        f"({len(schema['commands'])} commands, {len(schema['types'])} types)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
