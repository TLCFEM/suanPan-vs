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

Every second-level parser now uses a ``TokenRegistry`` initializer list:

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

Since suanPan #410 most dispatchers also read the object tag before dispatch
and pass it to the handler, which changes the registry value type to

.. code-block:: cpp

    TokenRegistry<void (*)(unique_ptr<Material>&, std::istringstream&, unsigned)>

Sections and groups still let each handler read the tag itself, so their value
type stops at ``std::istringstream&``.  ``registry_tag_in_dispatcher()`` reports
which layout a dispatch table uses; the command line is ``<command> <type>
<tag> ...`` either way.
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

REGISTRY_ENTRY = re.compile(r'\{\s*"([^"]+)"\s*,\s*([^{}]+?)\s*\}')
IDENTIFIER = re.compile(r"[A-Za-z_]")
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


def _matching_brace(text: str, opening: int) -> int:
    """Return the index of the brace matching ``text[opening]``."""
    depth = 0
    quote = ""
    line_comment = False
    block_comment = False
    index = opening
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = ""
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError("unbalanced braces in parser source")


def function_body(text: str, signature: str) -> str:
    """Return the complete body of the function starting at ``signature``."""
    start = text.find(signature)
    if start < 0:
        return ""
    opening = text.find("{", start)
    if opening < 0:
        return ""
    return text[opening : _matching_brace(text, opening) + 1]


def registry_entries(text: str, signature: str) -> list[RegistryEntry]:
    """Extract the ``TokenRegistry`` entries of the given dispatcher."""
    body = function_body(text, signature)
    if not body:
        return []

    declaration = re.search(r"TokenRegistry\s*<[^;]*?>\s*\w+\s*\{", body, re.S)
    if declaration is None:
        return []

    opening = body.find("{", declaration.start())
    block = body[opening + 1 : _matching_brace(body, opening)]

    entries: list[RegistryEntry] = []
    for match in REGISTRY_ENTRY.finditer(block):
        keyword = match.group(1)
        factory = re.sub(r"\s+", " ", match.group(2)).strip()
        # Named section designation tables use TokenRegistry<vec>; their values
        # are brace-enclosed vectors rather than factory functions.
        if not IDENTIFIER.match(factory):
            continue
        entries.append(RegistryEntry(keyword, factory))
    return entries


def registry_tag_in_dispatcher(text: str, signature: str) -> bool:
    """Whether the dispatcher reads the object tag before calling a handler.

    suanPan #410 moved tag extraction out of most handlers into the dispatcher,
    whose ``TokenRegistry`` value type gained a trailing ``unsigned`` parameter.
    Sections and groups keep ``void (*)(..., std::istringstream&)`` and read the
    tag inside each handler.
    """
    body = function_body(text, signature)
    if not body:
        return False

    declaration = re.search(r"TokenRegistry\s*<[^;]*?>\s*\w+\s*\{", body, re.S)
    if declaration is None:
        return False
    return TAG_IN_DISPATCHER.search(declaration.group(0)) is not None


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
) -> "OrderedDict[str, list[RegistryEntry]]":
    """Group entries by identical factory expression (true aliases)."""
    groups: OrderedDict[str, list[RegistryEntry]] = OrderedDict()
    for entry in entries:
        groups.setdefault(entry.factory, []).append(entry)
    return groups


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
    args = parser.parse_args()

    source = args.source.resolve()
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
