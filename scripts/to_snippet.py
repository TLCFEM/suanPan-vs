import json
from pathlib import Path


def process(a):
    b = []
    for i in a.values():
        command = "\n".join(i["body"])
        b.append(
            {
                "trigger": i["prefix"],
                "details": i["description"],
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
    return b


if __name__ == "__main__":
    parent_folder = Path(__file__).parent.parent / "syntaxes"

    with open(parent_folder / "snippets.json", "r") as f:
        snippets = json.load(f)
    with open(parent_folder / "nz_sections.json", "r") as f:
        nz_sections = json.load(f)
    with open(parent_folder / "eu_sections.json", "r") as f:
        eu_sections = json.load(f)
    with open(parent_folder / "us_sections.json", "r") as f:
        us_sections = json.load(f)
    all_snippets = (
        process(snippets)
        + process(nz_sections)
        + process(eu_sections)
        + process(us_sections)
    )
    with open(parent_folder / "suanPan.sublime-completions", "w") as f:
        json.dump(
            {
                "completions": all_snippets,
                "scope": ["source.supan"],
            },
            f,
            indent=2,
        )
