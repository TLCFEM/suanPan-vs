import sys
from pathlib import Path

from to_snippet import collect

if __name__ == "__main__":
    parent = Path(__file__).parent.parent
    sys.path.append(parent.as_posix())
    parent /= "syntaxes"

    all_snippets = {x["trigger"]: x for x in collect(parent)}

    for arg in sys.argv[1:]:
        key = arg.strip()
        if key in all_snippets:
            snippet = all_snippets[key]
            print(f"Trigger: {snippet['trigger']}")
            print("-" * 40)
            print(f"```text\n{snippet['contents']}\n```")
            print("-" * 40)
        else:
            print(f"No snippet found for trigger: {key}")
