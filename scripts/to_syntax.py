import json
from pathlib import Path
import re
import sys
import os


def count_capture_groups(regex_str: str) -> int:
    count = 0
    i = 0
    while i < len(regex_str):
        if regex_str[i] == "\\":
            i += 2
            continue
        if regex_str[i] == "[":
            i += 1
            while i < len(regex_str) and regex_str[i] != "]":
                if regex_str[i] == "\\":
                    i += 2
                else:
                    i += 1
            i += 1
            continue
        if regex_str[i] == "(":
            if i + 1 < len(regex_str) and regex_str[i + 1] == "?":
                if i + 2 < len(regex_str) and regex_str[i + 2] == "P":
                    count += 1
            else:
                count += 1
            i += 1
            continue
        i += 1
    return count


def extract_lookbehind(pattern: str):
    flags = ""
    flag_match = re.match(r"^(\(\?[a-zA-Z]+\))", pattern)
    if flag_match:
        flags = flag_match.group(1)
        pattern = pattern[len(flags) :]

    idx = pattern.find("(?<=")
    if idx == -1:
        return None

    start_lb = idx + 4
    open_count = 1
    end_lb = -1
    i = start_lb

    while i < len(pattern):
        if pattern[i] == "\\":
            i += 2
            continue
        if pattern[i] == "[":
            i += 1
            while i < len(pattern) and pattern[i] != "]":
                if pattern[i] == "\\":
                    i += 2
                else:
                    i += 1
            i += 1
            continue
        if pattern[i] == "(":
            open_count += 1
        elif pattern[i] == ")":
            open_count -= 1
            if open_count == 0:
                end_lb = i
                break
        i += 1

    if end_lb == -1:
        return None

    return flags, pattern[:idx], pattern[start_lb:end_lb], pattern[end_lb + 1 :]


def convert_tm_to_sublime(input_path: Path, output_path: Path):
    tm_data: dict = json.loads(input_path.read_text("utf-8"))

    lines = [
        "%YAML 1.2",
        "---",
        "# Generated from .tmLanguage.json",
        f"name: {tm_data.get('name')}",
        "file_extensions:",
        "  - supan",
        "  - sp",
        f"scope: {tm_data.get('scopeName')}",
        "contexts:",
        "  main:",
    ]

    for pattern in tm_data.get("patterns", []):
        if "include" in pattern:
            lines.append(f"    - include: {pattern['include'].lstrip('#')}")
        elif "match" in pattern and "name" in pattern:
            match_val = pattern["match"]
            scope_val = pattern["name"]
            if lb_info := extract_lookbehind(match_val):
                flags, before_lb, lookbehind_content, after_lb = lb_info
                target_idx = 2 + count_capture_groups(lookbehind_content)
                new_match = (
                    f"{flags}{before_lb}({lookbehind_content})({after_lb})".replace(
                        "'", "''"
                    )
                )
                lines.append(f"    - match: '{new_match}'")
                lines.append("      captures:")
                lines.append(f"        {target_idx}: {scope_val}")
            else:
                lines.append(f"    - match: '{match_val.replace("'", "''")}'")
                lines.append(f"      scope: {scope_val}")

    repo = tm_data.get("repository", {})
    for ctx_name, ctx_data in repo.items():
        lines.append("")
        lines.append(f"  {ctx_name}:")
        for pattern in ctx_data.get("patterns", []):
            if "match" in pattern and "name" in pattern:
                match_val = pattern["match"]
                scope_val = pattern["name"]
                if lb_info := extract_lookbehind(match_val):
                    flags, before_lb, lookbehind_content, after_lb = lb_info
                    target_idx = 2 + count_capture_groups(lookbehind_content)
                    new_match = (
                        f"{flags}{before_lb}({lookbehind_content})({after_lb})".replace(
                            "'", "''"
                        )
                    )
                    lines.append(f"    - match: '{new_match}'")
                    lines.append("      captures:")
                    lines.append(f"        {target_idx}: {scope_val}")
                else:
                    lines.append(f"    - match: '{match_val.replace("'", "''")}'")
                    lines.append(f"      scope: {pattern['name']}")
            elif "include" in pattern:
                lines.append(f"    - include: {pattern['include'].lstrip('#')}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent / "syntaxes")

    input_file = ".tmLanguage.json"
    output_file = "suanPan.sublime-syntax"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    convert_tm_to_sublime(Path(input_file), Path(output_file))
