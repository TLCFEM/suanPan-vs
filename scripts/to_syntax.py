import json
from pathlib import Path
import yaml


def convert_textmate_to_sublime(tm_json_str: str) -> dict:
    tm = json.loads(tm_json_str)

    sublime = {
        "file_extensions": ["supan", "sp"],
        "name": tm.get("name", "Unknown Language"),
        "scope": tm.get("scopeName", "source.unknown"),
        "contexts": {},
    }

    def process_captures(captures_dict):
        if not captures_dict:
            return None
        new_captures = {}
        for key, val in captures_dict.items():
            if "name" in val:
                new_captures[int(key)] = val["name"]
        return new_captures

    def convert_patterns(patterns):
        sublime_patterns = []
        for p in patterns:
            rule = {}

            if "include" in p:
                inc = p["include"]
                if inc.startswith("#"):
                    rule["include"] = inc[1:]
                elif inc == "$self":
                    rule["include"] = "main"
                else:
                    rule["include"] = inc
                sublime_patterns.append(rule)
                continue

            if "match" in p:
                rule["match"] = p["match"]
                if "name" in p:
                    rule["scope"] = p["name"]
                captures = process_captures(p.get("captures") or p.get("matchCaptures"))
                if captures:
                    rule["captures"] = captures
                sublime_patterns.append(rule)
                continue

            if "begin" in p:
                rule["match"] = p["begin"]
                if "name" in p:
                    rule["embed"] = (
                        "scope:" + sublime["scope"] if "patterns" in p else "main"
                    )

                push_context = []
                if "end" in p:
                    end_rule = {"match": p["end"], "pop": True}
                    end_caps = process_captures(p.get("endCaptures"))
                    if end_caps:
                        end_rule["captures"] = end_caps
                    push_context.append(end_rule)

                if "patterns" in p:
                    push_context.extend(convert_patterns(p["patterns"]))

                rule["push"] = push_context

                begin_caps = process_captures(p.get("beginCaptures"))
                if begin_caps:
                    rule["captures"] = begin_caps
                elif "name" in p:
                    rule["scope"] = p["name"]

                sublime_patterns.append(rule)

        return sublime_patterns

    if "patterns" in tm:
        sublime["contexts"]["main"] = convert_patterns(tm["patterns"])

    if "repository" in tm:
        for key, repo_item in tm["repository"].items():
            if "patterns" in repo_item:
                sublime["contexts"][key] = convert_patterns(repo_item["patterns"])
            elif "match" in repo_item or "begin" in repo_item:
                sublime["contexts"][key] = convert_patterns([repo_item])

    return sublime


if __name__ == "__main__":
    parent = Path(__file__).parent.parent / "syntaxes"

    sublime = convert_textmate_to_sublime((parent / "syntax.json").read_text())
    (parent / "suanPan.sublime-syntax").write_text(
        """%YAML 1.2
---
"""
        + yaml.dump(
            sublime,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    )
