import json
import re


if __name__ == "__main__":
    a = r"""
group GroupGroup (1) (2...)
# (1) int, unique group tag
# (2...) int, tags of groups to be included
"""

    b = [x for x in a.split("\n") if x.strip() != ""]

    for i in range(len(b)):
        if b[i].startswith("#"):
            continue
        b[i] = re.sub(r"\((\d+)\)", r"${\1:(\1)}", b[i])
        b[i] = re.sub(r"\[(\d+)\]", r"${\1:[\1]}", b[i])

    print(json.dumps(b, indent=2))
