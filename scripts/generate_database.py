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
the first-level commands from ``Toolbox/command.cpp`` and the second-level type
keywords from the unified ``TokenRegistry`` dispatch tables of the parser
files. Keywords that share the identical factory expression are emitted as
aliases; the registry itself is the authority, so no ``is_equal`` heuristics or
hand-maintained alias lists are involved.

A few commands (``set`` and ``initial``) still use the legacy ``is_equal``
chains and are read with the fallback extractor.

Coded section commands (``EU2D``, ``NZ2D``, ``US2DA``, ...) additionally accept
a designation before the tag.  Their designation tables are read from
``Section/SectionParser.cpp`` and stored once, with a container-to-table map, so
the editor can complete and validate designations without a hand-maintained
list.

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

from suanpan_parser import (
    REGISTRY_FUNCTIONS,
    grouped_registry,
    read_section_designations,
    registry_entries,
)

# Factories whose logical category is not the suffix of ``create_new_*``.
CATEGORY_OVERRIDES = {"create_new_external_module": "import"}

# First string token of a legacy dispatch, e.g. ``std::string property_id;
# if(!get_input(command, property_id))``.
LEGACY_TYPE_VAR = re.compile(
    r"std::string\s+(\w+)\s*;\s*if\s*\(\s*!get_input\(command,\s*\1"
)

FACTORY_CALL = re.compile(r"\b((?:create_new_|set_)\w*)\s*\(")
QUOTED = re.compile(r'"([^"]+)"')


def category_from_factory(factory: str | None) -> str | None:
    """Return the command category implied by a C++ factory name."""
    if not factory or not factory.startswith("create_new_"):
        return None
    name = factory.removeprefix("create_new_")
    return CATEGORY_OVERRIDES.get(factory, name)


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
        # Each dispatch is a single statement. Stop at the end of the line so
        # that lambdas declared for the *next* command family are not mistaken
        # for this command's factory.
        line_end = process.find("\n", position)
        if line_end < 0:
            line_end = len(process)
        next_position = (
            comparisons[index + 1][0] if index + 1 < len(comparisons) else len(process)
        )
        end = min(line_end, next_position)
        segment = process[position:end]
        factory = FACTORY_CALL.search(segment)
        callee = factory.group(1) if factory else None
        if callee is None:
            handler = re.search(r"return\s+(\w+)\s*\(\s*\)", segment)
            if handler:
                callee = handlers.get(handler.group(1))
        category = category_from_factory(callee)
        for name in names:
            entry = commands.setdefault(
                name.lower(),
                {
                    "name": name,
                    "aliases": [],
                    "category": category,
                    "summary": "",
                    "factory": callee,
                },
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
            if not canonical["factory"]:
                canonical["factory"] = alias["factory"]
            if not canonical["summary"]:
                canonical["summary"] = alias["summary"]
            canonical["aliases"].append(alias["name"])
            if alias["name"].lower() != group[0].lower():
                commands.pop(name.lower(), None)

    for name, entry in commands.items():
        entry["aliases"] = [a for a in entry["aliases"] if a.lower() != name]
        entry["summary"] = descriptions.get(name, entry["summary"])
    return commands


def parse_registry_types(source: Path, category: str) -> list[dict]:
    """Extract canonical keywords and exact aliases from the dispatch table."""
    relative, signature = REGISTRY_FUNCTIONS[category]
    text = (source / relative).read_text()
    groups = grouped_registry(registry_entries(text, signature))
    return [
        {
            "name": entries[0].keyword,
            "aliases": [entry.keyword for entry in entries[1:]],
            "factory": factory,
        }
        for factory, entries in groups.items()
    ]


def parse_legacy_types(source: Path, factory: str) -> list[dict]:
    """Read type keywords from a legacy ``is_equal`` dispatch handler."""
    text = (source / "Toolbox/command.cpp").read_text()
    body = function_region(text, f"int {factory}(")
    match = LEGACY_TYPE_VAR.search(body)
    if match is None:
        return []
    types: list[dict] = []
    for aliases in extract_symbols(body, match.group(1)):
        if any(t["name"].lower() == aliases[0].lower() for t in types):
            continue
        types.append({"name": aliases[0], "aliases": aliases[1:]})
    return types


def load_snippets(folders) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                continue
            for item in data.values():
                if not isinstance(item, dict) or "body" not in item:
                    continue
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


def validate_types(entry: dict) -> None:
    """Reject a dispatch table that accepts the same spelling twice.

    The registry groups aliases by factory expression.  A keyword repeated with
    a different factory would make lookup order dependent, so treat it as a
    parser source error instead of silently keeping the first entry.
    """
    spellings: dict[str, str] = {}
    for type_info in entry.get("types", []):
        for spelling in (type_info["name"], *type_info.get("aliases", [])):
            key = spelling.lower()
            previous = spellings.get(key)
            if previous is not None:
                raise SystemExit(
                    f"duplicate {entry['name']} keyword {spelling!r} "
                    f"({previous} / {type_info['name']})"
                )
            spellings[key] = type_info["name"]


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
        if category and name == category and category in REGISTRY_FUNCTIONS:
            entry["types"] = parse_registry_types(source, category)
        elif entry.get("factory"):
            types = parse_legacy_types(source, entry["factory"])
            if types:
                entry["types"] = types
        entry.pop("factory", None)

    snippets = load_snippets([args.snippets.resolve()])

    attach_snippet(list(commands.values()), snippets)
    for entry in commands.values():
        attach_snippet(entry.get("types", []), snippets)
        validate_types(entry)

    payload = {
        "version": version,
        "commands": sorted(commands.values(), key=lambda x: x["name"].lower()),
        # Coded sections (`EU2D`, `US2DA`, ...) take a designation between the
        # type and the tag. The tables are shared, so store them once and let
        # each container name the tables it searches.
        "section_designations": read_section_designations(source),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")
    print(
        f"wrote {payload['commands'].__len__()} commands (suanPan {version}) to {args.output}"
    )


if __name__ == "__main__":
    main()
