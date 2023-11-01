import json


def process(a: list):
    b = dict()
    s = dict()
    for x in a:
        if any(i in x["details"] for i in ("NZ", "EU", "US")) and any(
            i in x["details"] for i in ("3D", "2D")
        ):
            s[x["trigger"]] = {
                "prefix": x["trigger"],
                "body": list(x["contents"].split("\n")),
                "description": x["details"],
            }
        else:
            b[x["trigger"]] = {
                "prefix": x["trigger"],
                "body": list(x["contents"].split("\n")),
                "description": x["details"],
            }
    return b, s


if __name__ == "__main__":
    with open("syntaxes/suanPan.sublime-completions", "r") as f:
        data = json.load(f)

    b, s = process(data["completions"])

    with open("syntaxes/snippets.json", "w") as f:
        json.dump(b, f, indent=4)

    with open("syntaxes/sections.json", "w") as f:
        json.dump(s, f, indent=4)
