import json


def flatten_json(a):
    if isinstance(a, dict):
        return "".join(a.keys()) + "".join(flatten_json(v) for v in a.values())

    if isinstance(a, list):
        return "".join(flatten_json(v) for v in a)

    return str(a)


def sort_json(a, sort_list: bool):
    if isinstance(a, dict):
        return {k: sort_json(v, sort_list) for k, v in sorted(a.items())}

    if isinstance(a, list):
        transformed = [sort_json(v, sort_list) for v in a]
        if sort_list:
            return sorted(transformed, key=flatten_json)
        return transformed

    return a


def sort_file(file: str, sort_list: bool):
    with open(file, "r") as f:
        data = json.load(f)

    with open(file, "w") as f:
        f.write(json.dumps(sort_json(data, sort_list), indent=2))


if __name__ == "__main__":
    sort_file("syntaxes/syntax.json", True)
    sort_file("syntaxes/snippets.json", False)
