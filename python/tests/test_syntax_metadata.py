"""The TextMate grammar type lists must match the generated database.

``syntaxes/syntax.json`` hard-codes a few long keyword alternations for
highlighting.  The command database is generated from the C++ registries, so
comparing the two catches spelling drift (for example a missing ``DCP4M`` or a
misspelled ``LeeElementalNewmark``) before it reaches the editor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNTAX = ROOT / "syntaxes" / "syntax.json"
DATABASE = ROOT / "data" / "database.json"

#: categories whose grammar pattern enumerates every keyword
EXACT_CATEGORIES = ("amplitude", "element", "integrator", "material", "modifier")

PATTERN = re.compile(r"\(\?i\)\^\((\w+)\)\\s\+\(([^)]*)\)")


def _matches(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "match" and isinstance(item, str):
                found.append(item)
            else:
                found.extend(_matches(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_matches(item))
    return found


def _keyword_lists() -> tuple[dict[str, list[str]], list[str]]:
    document = json.loads(SYNTAX.read_text())
    documented: dict[str, list[str]] = {}
    patterns = _matches(document)
    for pattern in patterns:
        match = PATTERN.match(pattern)
        if match is None:
            continue
        verb, body = match.group(1).lower(), match.group(2)
        # Skip generic patterns such as ``(?i)^(section)\s+(\w+)\s+(\d+)``.
        if "\\w" in body or "(?:" in body or "\\d" in body:
            continue
        words = [
            word.lower()
            for word in body.split("|")
            if word and not word.startswith("\\$") and not word.startswith("$")
        ]
        if words:
            documented.setdefault(verb, []).extend(words)
    return documented, patterns


@pytest.mark.skipif(not SYNTAX.exists() or not DATABASE.exists(), reason="extension data missing")
def test_grammar_keywords_match_the_database():
    database = json.loads(DATABASE.read_text())
    commands = {command["name"].lower(): command for command in database["commands"]}
    documented, _ = _keyword_lists()

    for category in EXACT_CATEGORIES:
        expected = set(documented[category])
        command = commands[category]
        actual = {item["name"].lower() for item in command.get("types", [])}
        actual.update(
            alias.lower()
            for item in command.get("types", [])
            for alias in item.get("aliases", [])
        )
        assert expected == actual, f"{category}: {sorted(expected ^ actual)}"


@pytest.mark.skipif(not SYNTAX.exists() or not DATABASE.exists(), reason="extension data missing")
def test_grammar_covers_every_coded_section_container():
    database = json.loads(DATABASE.read_text())
    _, patterns = _keyword_lists()
    section = next(
        pattern
        for pattern in patterns
        if "(section)" in pattern and "EU2D" in pattern
    )
    match = PATTERN.match(section)
    assert match is not None
    documented = {
        word.lower()
        for word in match.group(2).split("|")
        if word and not word.startswith("\\$")
    }

    command = next(item for item in database["commands"] if item["name"] == "section")
    coded = {
        item["name"].lower()
        for item in command.get("types", [])
        if item["name"].upper().startswith(("EU", "NZ", "US"))
    }
    assert documented == coded, sorted(documented ^ coded)
    assert {"eu2da", "nz3da", "us2dac", "us3dac"} <= documented
