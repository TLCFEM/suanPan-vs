import json
from pathlib import Path
import sys
import os


def convert_tm_to_sublime(input_path: Path, output_path: Path):
    tm_data: dict = json.loads(input_path.read_text("utf-8"))

    lines = [
        "%YAML 1.2",
        "---",
        "# Generated from .tmLanguage.json",
        f"name: {tm_data.get('name')}",
        f"scope: {tm_data.get('scopeName')}",
        "contexts:",
        "  main:",
    ]

    for pattern in tm_data.get("patterns", []):
        if "include" in pattern:
            inc = pattern["include"].lstrip("#")
            lines.append(f"    - include: {inc}")

    repo = tm_data.get("repository", {})
    for ctx_name, ctx_data in repo.items():
        lines.append("")
        lines.append(f"  {ctx_name}:")
        for pattern in ctx_data.get("patterns", []):
            if "match" in pattern and "name" in pattern:
                lines.append(f"    - match: '{pattern['match'].replace("'", "''")}'")
                lines.append(f"      scope: {pattern['name']}")
            elif "include" in pattern:
                inc = pattern["include"].lstrip("#")
                lines.append(f"    - include: {inc}")

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
