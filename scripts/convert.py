import json
import re


if __name__ == "__main__":
    a = r"""
set tolerance (1)
# (1) double, tolerance of the iterative solver
"""

    b = [x for x in a.split("\n") if x.strip() != ""]

    for i in range(len(b)):
        if b[i].startswith("#"):
            continue
        b[i] = re.sub(r"\((\d+)\)", r"${\1:(\1)}", b[i])
        b[i] = re.sub(r"\[(\d+)\]", r"${\1:[\1]}", b[i])

    print(json.dumps(b, indent=2))
