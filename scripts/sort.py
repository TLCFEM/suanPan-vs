import json

def flatten_json(a):
    if isinstance(a, dict):
        return "".join(a.keys()) + "".join(flatten_json(v) for v in a.values())

    if isinstance(a, list):
        return "".join(flatten_json(v) for v in a)

    return str(a)


def sort_json(a):
    if isinstance(a, dict):
        return {k: sort_json(v) for k, v in sorted(a.items())}

    if isinstance(a, list):
        return sorted((sort_json(v) for v in a), key=flatten_json)

    return a


if __name__ == "__main__":
    with open("syntaxes/syntax.json", "r") as f:
        data = json.load(f)

    with open("syntaxes/syntax.json", "w") as f:
        f.write(json.dumps(sort_json(data), indent=2))
