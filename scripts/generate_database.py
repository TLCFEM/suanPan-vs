#  Copyright (C) 2017-2026 Theodore Chang
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Generate the command database used by the suanPan VS Code extension.

The suanPan C++ source code is the single source of truth. This script extracts
the first-level commands and the second-level type keywords directly from the
parser implementation so that the extension never drifts from the interpreter.

Usage::

    python scripts/generate_database.py --source ../suanPan --output data/database.json

The optional ``--snippets`` folder is used to enrich the generated entries with
argument templates and short descriptions that were derived from the manual.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Maps the ``create_new_*`` factory to a logical category.
FACTORY_CATEGORY = {
    "create_new_element": "element",
    "create_new_material": "material",
    "create_new_section": "section",
    "create_new_constraint": "constraint",
    "create_new_criterion": "criterion",
    "create_new_interaction": "interaction",
    "create_new_load": "load",
    "create_new_amplitude": "amplitude",
    "create_new_solver": "solver",
    "create_new_integrator": "integrator",
    "create_new_converger": "converger",
    "create_new_step": "step",
    "create_new_expression": "expression",
    "create_new_group": "group",
    "create_new_modifier": "modifier",
    "create_new_orientation": "orientation",
    "create_new_recorder": "recorder",
    "create_new_initial": "initial",
    "create_new_node": "node",
    "create_new_mass": "mass",
    "create_new_domain": "domain",
    "create_new_external_module": "import",
}

# Which factory function in which source file decides the concrete type keyword.
CATEGORY_TYPES = {
    "element": [("Element/ElementParser.cpp", "create_new_element", "element_id")],
    "material": [("Material/MaterialParser.cpp", "create_new_material", "material_id")],
    "section": [("Section/SectionParser.cpp", "create_new_section", "section_id")],
    "constraint": [
        ("Constraint/ConstraintParser.cpp", "create_new_constraint", "constraint_id")
    ],
    "criterion": [
        ("Constraint/ConstraintParser.cpp", "create_new_criterion", "criterion_type")
    ],
    "interaction": [
        ("Constraint/ConstraintParser.cpp", "create_new_interaction", "criterion_type")
    ],
    "load": [("Load/LoadParser.cpp", "create_new_load", "load_id")],
    "amplitude": [("Load/LoadParser.cpp", "create_new_amplitude", "amplitude_type")],
    "solver": [("Solver/SolverParser.cpp", "create_new_solver", "solver_type")],
    "integrator": [
        ("Solver/SolverParser.cpp", "create_new_integrator", "integrator_type")
    ],
    "converger": [
        ("Converger/ConvergerParser.cpp", "create_new_converger", "converger_id")
    ],
    "step": [("Step/StepParser.cpp", "create_new_step", "step_type")],
    "expression": [
        ("Toolbox/ExpressionParser.cpp", "create_new_expression", "expression_type")
    ],
    "group": [("Domain/Group/GroupParser.cpp", "create_new_group", "group_id")],
    "modifier": [("Element/ElementParser.cpp", "create_new_modifier", "modifier_type")],
    "orientation": [
        ("Element/ElementParser.cpp", "create_new_orientation", "file_type")
    ],
    "recorder": [
        ("Recorder/RecorderParser.cpp", "process_recorder_command", "object_type")
    ],
}

# Commands that do not follow the standard "command type tag ..." layout.
EXTRA_COMMAND_TYPES = {
    "set": [("Toolbox/command.cpp", "set_property", "property_id")],
    "initial": [("Toolbox/command.cpp", "create_new_initial", "variable_type")],
}

SNIPPET_FILES = (
    "snippets.json",
    "nz_sections.json",
    "eu_sections.json",
    "us_sections.json",
)

IS_EQUAL_ANY = re.compile(r"is_equal_any\(\s*{var}\s*,\s*([^)]*)\)")
QUOTED = re.compile(r'"([^"]+)"')


def function_region(text: str, signature: str) -> str:
    """Return the body of the function starting at ``signature``."""
    start = text.find(signature)
    if start < 0:
        return ""
    brace = text.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace : i + 1]
    return text[brace:]


def extract_symbols(text: str, var: str) -> list[list[str]]:
    """Extract ordered alias groups tested against ``var``."""
    is_equal = re.compile(r"is_equal\(\s*" + re.escape(var) + r'\s*,\s*"([^"]+)"\s*\)')
    is_equal_any = re.compile(
        r"is_equal_any\(\s*" + re.escape(var) + r"\s*,\s*([^)]*)\)"
    )

    found: list[tuple[int, list[str]]] = []
    for m in is_equal.finditer(text):
        found.append((m.start(), [m.group(1)]))
    for m in is_equal_any.finditer(text):
        aliases = QUOTED.findall(m.group(1))
        if aliases:
            found.append((m.start(), aliases))
    found.sort(key=lambda x: x[0])

    ordered: list[list[str]] = []
    seen: set[str] = set()
    for _, aliases in found:
        if aliases[0].lower() in seen:
            continue
        seen.update(a.lower() for a in aliases)
        ordered.append(aliases)
    return ordered


def parse_first_level_commands(source: Path) -> dict[str, dict]:
    text = (source / "Toolbox/command.cpp").read_text()

    descriptions: dict[str, str] = {}
    for m in re.finditer(r'suanpan_info\(format,\s*"([^"]+)",\s*"([^"]+)"\)', text):
        for name in re.split(r"[|/]", m.group(1)):
            descriptions[name.strip()] = m.group(2)

    process = function_region(text, "int process_command(")

    # Resolve short lambdas such as ``auto group_handler = [&] { ... return create_new_group(...)``.
    handlers: dict[str, str] = {}
    for m in re.finditer(r"auto\s+(\w+)\s*=\s*\[&\][^{]*\{(.*?)\}", process, re.DOTALL):
        called = re.search(r"return\s+(create_new_\w+)\(", m.group(2))
        if called:
            handlers[m.group(1)] = called.group(1)

    comparisons: list[tuple[int, list[str]]] = []
    for m in re.finditer(r"is_equal(_any)?\(\s*command_id\s*,\s*([^)]*)\)", process):
        names = QUOTED.findall(m.group(2))
        if names:
            comparisons.append((m.start(), names))
    comparisons.sort(key=lambda x: x[0])

    commands: dict[str, dict] = {}
    groups: list[list[str]] = []
    for index, (position, names) in enumerate(comparisons):
        if len(names) > 1:
            groups.append(names)
        end = (
            comparisons[index + 1][0] if index + 1 < len(comparisons) else len(process)
        )
        segment = process[position:end]
        factory = re.search(r"\b(create_new_\w+)\s*\(", segment)
        callee = factory.group(1) if factory else None
        if callee is None:
            handler = re.search(r"return\s+(\w+)\s*\(\s*\)", segment)
            if handler:
                callee = handlers.get(handler.group(1))
        category = FACTORY_CATEGORY.get(callee) if callee else None
        for name in names:
            entry = commands.setdefault(
                name.lower(),
                {"name": name, "aliases": [], "category": category, "summary": ""},
            )
            if category and not entry["category"]:
                entry["category"] = category

    # `is_equal_any(command_id, "a", "b")` makes `b` an alias of `a`.
    for group in groups:
        canonical = commands.get(group[0].lower())
        if canonical is None:
            continue
        for name in group[1:]:
            alias = commands.get(name.lower())
            if alias is None or alias is canonical:
                continue
            if not canonical["category"]:
                canonical["category"] = alias["category"]
            if not canonical["summary"]:
                canonical["summary"] = alias["summary"]
            canonical["aliases"].append(alias["name"])
            if alias["name"].lower() != group[0].lower():
                commands.pop(name.lower(), None)

    for name, entry in commands.items():
        entry["aliases"] = [a for a in entry["aliases"] if a.lower() != name]
        entry["summary"] = descriptions.get(name, entry["summary"])
    return commands


def parse_types(source: Path, mapping) -> list[dict]:
    types: list[dict] = []
    for rel, factory, var in mapping:
        path = source / rel
        if not path.exists():
            continue
        text = function_region(path.read_text(), f"int {factory}(")
        for aliases in extract_symbols(text, var):
            if any(t["name"].lower() == aliases[0].lower() for t in types):
                continue
            types.append({"name": aliases[0], "aliases": aliases[1:]})
    return types


def load_snippets(folders) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for folder in folders:
        for name in SNIPPET_FILES:
            path = folder / name
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            for item in data.values():
                body = item.get("body", [])
                if not body:
                    continue
                prefix = item.get("prefix", "")
                index.setdefault(prefix.lower(), []).append(
                    {
                        "prefix": prefix,
                        "summary": item.get("description", ""),
                        "args": body,
                        "verb": body[0].split(" ", 1)[0].lower(),
                    }
                )
    return index


def attach_snippet(items: list[dict], snippets: dict):
    for item in items:
        names = [item["name"], *item.get("aliases", [])]
        for name in names:
            for candidate in snippets.get(name.lower(), []):
                if not item.get("summary"):
                    item["summary"] = candidate["summary"]
                if item.get("summary"):
                    break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="../suanPan", type=Path)
    parser.add_argument("--output", default="data/database.json", type=Path)
    parser.add_argument("--snippets", default="syntaxes", type=Path)
    args = parser.parse_args()

    source: Path = args.source.resolve()
    if not (source / "Toolbox/command.cpp").exists():
        raise SystemExit(f"cannot locate suanPan source at {source}")

    version_header = (source / "Toolbox/command.h").read_text()

    def const(name: str) -> str:
        m = re.search(rf"constexpr auto {name} = (\d+);", version_header)
        return m.group(1) if m else "0"

    version = (
        f"{const('SUANPAN_MAJOR')}.{const('SUANPAN_MINOR')}.{const('SUANPAN_PATCH')}"
    )

    commands = parse_first_level_commands(source)

    for name, entry in commands.items():
        category = entry.get("category")
        if category and name == category and category in CATEGORY_TYPES:
            entry["types"] = parse_types(source, CATEGORY_TYPES[category])
        elif name in EXTRA_COMMAND_TYPES:
            entry["types"] = parse_types(source, EXTRA_COMMAND_TYPES[name])

    snippets = load_snippets([args.snippets.resolve()])

    attach_snippet(list(commands.values()), snippets)
    for entry in commands.values():
        attach_snippet(entry.get("types", []), snippets)

    payload = {
        "version": version,
        "commands": sorted(commands.values(), key=lambda x: x["name"].lower()),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")
    print(
        f"wrote {payload['commands'].__len__()} commands (suanPan {version}) to {args.output}"
    )


if __name__ == "__main__":
    main()
