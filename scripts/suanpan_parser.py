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

"""Read suanPan's unified parser dispatch tables.

Every object-defining second-level parser uses a ``TokenRegistry`` initializer
list:

.. code-block:: cpp

    int create_new_material(const shared_ptr<DomainBase>& domain, std::istringstream& command) {
        ...
        static const TokenRegistry<void (*)(unique_ptr<Material>&, std::istringstream&)> registry{
            {"AbaqusCDP", new_tablecdp<true>},
            {"AFC", new_afc01},
            {"AFC01", new_afc01},
            ...
        };
        ...
    }

The registry is the authoritative list of accepted keywords, their aliases
(keywords sharing the identical factory expression) and the C++ handler that
parses the remaining tokens.  Both the VS Code database generator and the
Python class generator consume this module, so neither has to infer dispatch
from ``is_equal`` chains or hand-maintained temporary files.

Since suanPan #410 the dispatchers read the object tag before dispatch and pass
it to the handler, which changes the registry value type to

.. code-block:: cpp

    TokenRegistry<void (*)(unique_ptr<Material>&, std::istringstream&, unsigned)>

Groups still let each handler read the tag itself, so their value type stops at
``std::istringstream&``.  ``registry_tag_in_dispatcher()`` reports which layout
a dispatch table uses; the command line is ``<command> <type> <tag> ...``
either way.

Coded sections (``EU2D``, ``NZ3D``, ``US2DA``, ...) take a designation between
the type and the tag.  Their accepted designations live in ``TokenRegistry<vec>``
tables in ``Section/SectionParser.cpp``.  ``read_section_designations()`` reads
those tables so completion and diagnostics never have to rely on a hand-copied
list.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

#: category -> (source file relative to the suanPan root, function signature)
REGISTRY_FUNCTIONS: dict[str, tuple[str, str]] = {
    "element": ("Element/ElementParser.cpp", "int create_new_element("),
    "modifier": ("Element/ElementParser.cpp", "int create_new_modifier("),
    "orientation": ("Element/ElementParser.cpp", "int create_new_orientation("),
    "material": ("Material/MaterialParser.cpp", "int create_new_material("),
    "section": ("Section/SectionParser.cpp", "int create_new_section("),
    "constraint": ("Constraint/ConstraintParser.cpp", "int create_new_constraint("),
    "criterion": ("Constraint/ConstraintParser.cpp", "int create_new_criterion("),
    "interaction": ("Constraint/ConstraintParser.cpp", "int create_new_interaction("),
    "load": ("Load/LoadParser.cpp", "int create_new_load("),
    "amplitude": ("Load/LoadParser.cpp", "int create_new_amplitude("),
    "solver": ("Solver/SolverParser.cpp", "int create_new_solver("),
    "integrator": ("Solver/SolverParser.cpp", "int create_new_integrator("),
    "converger": ("Converger/ConvergerParser.cpp", "int create_new_converger("),
    "step": ("Step/StepParser.cpp", "int create_new_step("),
    "expression": ("Toolbox/ExpressionParser.cpp", "int create_new_expression("),
    "group": ("Domain/Group/GroupParser.cpp", "int create_new_group("),
    "recorder": ("Recorder/RecorderParser.cpp", "int dispatch_new_recorder("),
}

SECTION_SOURCE = "Section/SectionParser.cpp"
SECTION_DISPATCH = "int create_new_section("

IDENTIFIER = re.compile(r"[A-Za-z_]")
QUOTED = re.compile(r'"([^"]+)"')
DESIGNATION_TABLE = re.compile(r"vec\s+(\w+)\s*\(\s*const std::string_view")
DESIGNATION_INPUT = re.compile(r"is_equal_any\(\s*section_id\s*,\s*([^)]*)\)")
TERNARY_CALL = re.compile(
    r"(\w+)\s*\?\s*(\w+)\s*\(\s*type\s*\)\s*:\s*(\w+)\s*\(\s*type\s*\)"
)
TABLE_CALL = re.compile(r"\b(\w+)\s*\(\s*type\s*\)")
BOOL_PARAM = re.compile(r"bool\s+(\w+)")
EARLY_RETURN = re.compile(r"if\s*\(\s*(\w+)\s*\)\s*\{")
#: registry value type that consumes the object tag before dispatch (#410)
TAG_IN_DISPATCHER = re.compile(r"istringstream\s*&\s*,\s*(?:const\s+)?unsigned\b")


@dataclass(frozen=True)
class RegistryEntry:
    """One keyword/factory pair of a ``TokenRegistry`` initializer list."""

    keyword: str
    factory: str

    @property
    def base_factory(self) -> str:
        """The factory name without explicit template arguments."""
        return self.factory.split("<", 1)[0].strip()


def _code_mask(text: str) -> bytearray:
    """Return a mask marking characters that are C++ code.

    Comments and the contents of string/character literals are zeroed, so
    brace matching, signature lookup and registry parsing never get confused
    by braces or keywords inside comments or strings.  The quotes themselves
    stay marked so that string literals can still be located.
    """
    mask = bytearray(b"\x01") * len(text)
    length = len(text)
    index = 0
    while index < length:
        char = text[index]
        following = text[index + 1] if index + 1 < length else ""

        if char == "/" and following == "/":
            while index < length and text[index] != "\n":
                mask[index] = 0
                index += 1
            continue

        if char == "/" and following == "*":
            while index < length:
                mask[index] = 0
                if text[index] == "*" and index + 1 < length and text[index + 1] == "/":
                    mask[index + 1] = 0
                    index += 2
                    break
                index += 1
            continue

        if char in "\"'":
            quote = char
            index += 1
            while index < length:
                if text[index] == "\\":
                    mask[index] = 0
                    if index + 1 < length:
                        mask[index + 1] = 0
                    index += 2
                    continue
                if text[index] == quote:
                    index += 1
                    break
                mask[index] = 0
                index += 1
            continue

        index += 1
    return mask


def _find_code(text: str, needle: str, start: int = 0, mask: bytearray | None = None) -> int:
    """Find ``needle`` at a position where every character is code."""
    if mask is None:
        mask = _code_mask(text)
    index = start
    while True:
        found = text.find(needle, index)
        if found < 0:
            return -1
        if all(mask[found + offset] for offset in range(len(needle))):
            return found
        index = found + 1


def _matching_brace(text: str, opening: int, mask: bytearray | None = None) -> int:
    """Return the index of the code brace matching ``text[opening]``."""
    if mask is None:
        mask = _code_mask(text)
    depth = 0
    for index in range(opening, len(text)):
        if not mask[index]:
            continue
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced braces in parser source")


def function_body(text: str, signature: str) -> str:
    """Return the complete body of the function starting at ``signature``.

    Signatures inside comments are ignored, and a forward declaration (the
    signature followed by ``;`` before the opening brace) yields an empty body.
    """
    mask = _code_mask(text)
    start = _find_code(text, signature, 0, mask)
    if start < 0:
        return ""
    opening = _find_code(text, "{", start + len(signature), mask)
    if opening < 0:
        return ""
    if ";" in text[start + len(signature) : opening]:
        return ""
    return text[opening : _matching_brace(text, opening, mask) + 1]


def registry_pairs(text: str, signature: str) -> list[tuple[str, str]]:
    """Extract ``(keyword, value)`` pairs from the ``TokenRegistry`` table.

    Works for both factory tables (values are function names) and the
    ``TokenRegistry<vec>`` designation tables (values are brace-enclosed
    vectors).  Entries may contain nested braces, comments and line breaks.
    """
    body = function_body(text, signature)
    if not body:
        return []

    mask = _code_mask(body)
    start = _find_code(body, "TokenRegistry", 0, mask)
    if start < 0:
        return []
    opening = _find_code(body, "{", start, mask)
    if opening < 0:
        return []
    closing = _matching_brace(body, opening, mask)

    pairs: list[tuple[str, str]] = []
    index = opening + 1
    while index < closing:
        entry_open = _find_code(body, "{", index, mask)
        if entry_open < 0 or entry_open >= closing:
            break
        entry_close = _matching_brace(body, entry_open, mask)
        entry = body[entry_open + 1 : entry_close]
        entry_mask = mask[entry_open + 1 : entry_close]

        key = None
        key_end = 0
        for position, char in enumerate(entry):
            if char != '"' or not entry_mask[position]:
                continue
            end = position + 1
            while end < len(entry) and not (entry[end] == '"' and entry_mask[end]):
                end += 1
            key = entry[position + 1 : end]
            key_end = end + 1
            break

        if key is not None:
            comma = next(
                (
                    position
                    for position in range(key_end, len(entry))
                    if entry[position] == "," and entry_mask[position]
                ),
                -1,
            )
            value = entry[comma + 1 :].strip() if comma >= 0 else ""
            pairs.append((key, value))
        index = entry_close + 1
    return pairs


def registry_entries(text: str, signature: str) -> list[RegistryEntry]:
    """Extract the factory entries of the given dispatcher."""
    entries: list[RegistryEntry] = []
    for keyword, value in registry_pairs(text, signature):
        factory = re.sub(r"\s+", " ", value).strip()
        # Named section designation tables use TokenRegistry<vec>; their values
        # are brace-enclosed vectors rather than factory functions.
        if not IDENTIFIER.match(factory):
            continue
        entries.append(RegistryEntry(keyword, factory))
    return entries


def registry_keywords(text: str, signature: str) -> list[str]:
    """Extract the keywords of a ``TokenRegistry<vec>`` designation table."""
    return [
        keyword
        for keyword, value in registry_pairs(text, signature)
        if value.startswith("{")
    ]


def registry_tag_in_dispatcher(text: str, signature: str) -> bool:
    """Whether the dispatcher reads the object tag before calling a handler.

    suanPan #410 moved tag extraction out of most handlers into the dispatcher,
    whose ``TokenRegistry`` value type gained a trailing ``unsigned`` parameter.
    Groups keep ``void (*)(..., std::istringstream&)`` and read the tag inside
    each handler.
    """
    body = function_body(text, signature)
    if not body:
        return False

    mask = _code_mask(body)
    start = _find_code(body, "TokenRegistry", 0, mask)
    if start < 0:
        return False
    opening = _find_code(body, "{", start, mask)
    if opening < 0:
        return False
    return TAG_IN_DISPATCHER.search(body[start:opening]) is not None


def read_registry(source: Path, category: str) -> list[RegistryEntry]:
    """Read the dispatch table of ``category`` from a suanPan checkout."""
    relative, signature = REGISTRY_FUNCTIONS[category]
    path = source / relative
    if not path.exists():
        raise FileNotFoundError(f"cannot locate suanPan parser source at {path}")
    return registry_entries(path.read_text(), signature)


def read_registry_tag_in_dispatcher(source: Path, category: str) -> bool:
    """Report the tag ownership of ``category`` in a suanPan checkout."""
    relative, signature = REGISTRY_FUNCTIONS[category]
    path = source / relative
    if not path.exists():
        raise FileNotFoundError(f"cannot locate suanPan parser source at {path}")
    return registry_tag_in_dispatcher(path.read_text(), signature)


def grouped_registry(
    entries: list[RegistryEntry],
) -> OrderedDict[str, list[RegistryEntry]]:
    """Group entries by identical factory expression (true aliases)."""
    groups: OrderedDict[str, list[RegistryEntry]] = OrderedDict()
    for entry in entries:
        groups.setdefault(entry.factory, []).append(entry)
    return groups


def _template_flags(text: str, factory: str) -> dict[str, bool]:
    """Resolve the boolean template arguments of a section handler."""
    base, _, arguments = factory.partition("<")
    signature = re.search(
        r"template\s*<([^>]*)>\s*void\s+" + re.escape(base) + r"\s*\(", text
    )
    if signature is None:
        return {}
    values = [
        argument.strip() == "true"
        for argument in arguments.rstrip(">").split(",")
        if argument.strip()
    ]
    return dict(zip(BOOL_PARAM.findall(signature.group(1)), values, strict=False))


def _block(text: str, opening: int) -> tuple[int, int]:
    """Return the span of the brace block starting at ``opening``."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return opening, index + 1
    return opening, len(text)


def _handler_tables(body: str, tables: set[str], flags: dict[str, bool]) -> list[str]:
    """List the designation tables a handler consults, in source order."""
    selected: list[str] = []
    seen: set[str] = set()
    ternary_spans: list[tuple[int, int]] = []

    for match in TERNARY_CALL.finditer(body):
        ternary_spans.append(match.span())
        condition, yes, no = match.groups()
        if condition not in flags:
            continue
        chosen = yes if flags[condition] else no
        if chosen in tables and chosen not in seen:
            seen.add(chosen)
            selected.append(chosen)

    early_spans: list[tuple[int, int, bool]] = []
    taken = False
    for match in EARLY_RETURN.finditer(body):
        condition = match.group(1)
        if condition not in flags:
            continue
        opening = body.find("{", match.end() - 1)
        start, end = _block(body, opening)
        if "return;" not in body[start:end]:
            continue
        early_spans.append((start, end, flags[condition]))
        if flags[condition]:
            taken = True

    for match in TABLE_CALL.finditer(body):
        position = match.start()
        if any(start <= position < end for start, end in ternary_spans):
            continue
        inside = [
            flag for start, end, flag in early_spans if start <= position < end
        ]
        if inside and not any(inside):
            continue
        name = match.group(1)
        if name in tables and name not in seen and (any(inside) or not taken):
            seen.add(name)
            selected.append(name)
    return selected


def read_section_designations(source: Path) -> dict[str, object]:
    """Read coded-section designation tables and their per-command lookup order.

    Returns ``{"tables": {table: [designation, ...]}, "containers":
    {section: [table, ...]}}``.  Both the table contents and the container
    mapping come from ``Section/SectionParser.cpp``.
    """
    path = source / SECTION_SOURCE
    if not path.exists():
        raise FileNotFoundError(f"cannot locate suanPan parser source at {path}")
    text = path.read_text()

    tables = {
        name: registry_keywords(text, f"vec {name}(")
        for name in sorted(set(DESIGNATION_TABLE.findall(text)))
    }
    for name, keywords in tables.items():
        if not keywords:
            raise ValueError(f"no designations found in {SECTION_SOURCE}:{name}")

    dispatch = function_body(text, SECTION_DISPATCH)
    match = DESIGNATION_INPUT.search(dispatch)
    if match is None:
        raise ValueError(f"no coded sections found in {SECTION_SOURCE}")
    factories = {
        entry.keyword: entry.factory for entry in registry_entries(text, SECTION_DISPATCH)
    }

    containers: dict[str, list[str]] = {}
    for container in QUOTED.findall(match.group(1)):
        factory = factories.get(container)
        if factory is None:
            raise ValueError(f"no handler found for coded section {container}")
        body = function_body(text, f"void {factory.partition('<')[0]}(")
        if not body:
            raise ValueError(f"no handler body found for coded section {container}")
        containers[container] = _handler_tables(
            body, set(tables), _template_flags(text, factory)
        )
    return {"tables": tables, "containers": containers}


def read_all(source: Path) -> dict[str, list[RegistryEntry]]:
    """Read every known second-level dispatch table."""
    return {category: read_registry(source, category) for category in REGISTRY_FUNCTIONS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default="../suanPan", type=Path, help="path to the suanPan checkout"
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=sorted(REGISTRY_FUNCTIONS),
        help="limit the dump to one or more categories",
    )
    parser.add_argument(
        "--designations",
        action="store_true",
        help="dump the coded-section designation tables instead of dispatch types",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if args.designations:
        print(json.dumps(read_section_designations(source), indent=1))
        return

    categories = args.category or list(REGISTRY_FUNCTIONS)
    payload = {}
    for category in categories:
        groups = grouped_registry(read_registry(source, category))
        payload[category] = {
            "tag_in_dispatcher": read_registry_tag_in_dispatcher(source, category),
            "types": [
                {
                    "name": entries[0].keyword,
                    "aliases": [entry.keyword for entry in entries[1:]],
                    "factory": factory,
                }
                for factory, entries in groups.items()
            ],
        }
    print(json.dumps(payload, indent=1))


if __name__ == "__main__":
    main()
