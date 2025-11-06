import json
from pathlib import Path


def process(file: Path):
    with open(file, "r") as f:
        data = json.load(f)

    item_list = []
    for item in data.values():
        command = "\n".join(item["body"])
        item_list.append(
            {
                "trigger": item["prefix"],
                "details": item["description"],
                "kind": "type"
                if command.startswith(
                    (
                        "element",
                        "material",
                        "constraint",
                        "load",
                        "modifier",
                        "solver",
                        "step",
                        "section",
                        "criterion",
                        "amplitude",
                        "expression",
                    )
                )
                else "keyword",
                "contents": command,
            }
        )
    return item_list


def collect(folder: Path):
    all_snippets = []
    all_snippets.extend(process(folder / "snippets.json"))
    all_snippets.extend(process(folder / "nz_sections.json"))
    all_snippets.extend(process(folder / "eu_sections.json"))
    all_snippets.extend(process(folder / "us_sections.json"))
    return all_snippets


if __name__ == "__main__":
    parent_folder = Path(__file__).parent.parent / "syntaxes"

    with open(parent_folder / "suanPan.sublime-completions", "w") as f:
        json.dump(
            {
                "completions": collect(parent_folder),
                "scope": ["source.supan"],
            },
            f,
            indent=2,
        )
