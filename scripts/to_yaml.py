from ruamel.yaml import YAML
import json


def rename(a: dict):
    b = dict()
    b["match"] = a["match"]
    print(b["match"])
    b["scope"] = a["name"]
    return b


def to_yaml(a: dict):
    b = list()
    for _, v in a["repository"].items():
        b.extend([rename(x) for x in v["patterns"]])

    return {
        "file_extensions": ["supan", "sp"],
        "scope": "source.supan",
        "contexts": {"main": b},
    }


if __name__ == "__main__":
    with open("syntaxes/.tmLanguage.json", "r") as f:
        data = json.load(f)

    with open("syntaxes/suanPan.sublime-syntax", "w") as f:
        f.write("%YAML 1.2\n---\n")
        yaml = YAML()
        yaml.dump(to_yaml(data), f)
