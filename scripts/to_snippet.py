import json


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
    with open("syntaxes/snippets.json", "r") as f:
        snippets = json.load(f)
    with open("syntaxes/sections.json", "r") as f:
        sections = json.load(f)
    all_snippets = process(snippets) + process(sections)
    with open("syntaxes/suanPan.sublime-completions", "w") as f:
        json.dump(
            {
                "completions": all_snippets,
                "scope": ["source.supan"],
            },
            f,
            indent=2,
        )
