# suanPan

[🧮 **suanPan**](https://tlcfem.github.io/suanPan/) is an open source, parallel and heterogeneous finite element analysis framework.

This extension provides editing support for `suanPan` model files: syntax highlighting, context aware completion, documentation, diagnostics and navigation.

> [!IMPORTANT]
> If you're using autocomplete tools such as Copilot, it’s advisable to turn the feature off to prevent potential conflicts.
>
> ```json
> "github.copilot.enable": {
>     "suanPan": false
> }
> ```

## Quick Start

1. download `suanPan`
2. install this extension `ext install tlc.suanpan`
3. enable tab completion (`Settings` -> `Editor: Tab Completion` -> `On`)
4. set path to the `suanPan` executable (`Settings` -> `suanPan` -> `Path`)
5. open a model file and edit
6. perform the analysis via `Ctrl+Shift+P` -> `suanPan: Run this model in suanPan`

## Features

### Completion

- first-level commands at the beginning of a line,
- type keywords after `element`, `material`, `section`, `step`, `solver`, ...,
- named section designations such as `section NZ2D 1000WB215 ...`,
- properties after `set`,
- known tags for arguments documented as `material tag`, `node i`, `section tag`, ...,
- boolean literals and `$variables`.

Selecting a type also inserts the documented argument template, so the
arguments can be filled in with `Tab`.

### Documentation

Hover over a command, a type or an argument to see its summary, syntax and
argument description. Hovering over a tag shows where it is defined.

Signature help (shown while typing arguments) highlights the active argument.

### Diagnostics

The extension reports unknown commands, unknown type keywords, dangling line
continuations and, optionally, references to tags that are not defined in the
same file. Unknown type and reference checks can be turned off for models that
load objects from other files or external modules.

### Navigation

- outline of all defined objects,
- go to definition for material/section/node/... tags,
- find all references to a tag,
- folding of comment blocks, line continuations and object groups.

### Command palette

- `suanPan: Insert a command template` — search all commands of the current
  suanPan version and insert a template.
- `suanPan: Show the command database version`.
- `suanPan: Set the executable path`.

## Settings

| Setting | Default | Description |
| --- | --- | --- |
| `suanpan.color` | `true` | Enable colorized output. |
| `suanpan.cpus` | `0` | Logical cores used in docker (0 = all). |
| `suanpan.directory` | `""` | Working directory (empty = folder of the model). |
| `suanpan.docker` | `false` | Run the model in a docker container. |
| `suanpan.image` | `tlcfem/suanpan` | Docker image. |
| `suanpan.path` | `""` | Path to the suanPan executable. |
| `suanpan.verbose` | `false` | Enable verbose output. |
| `suanpan.diagnostics.enable` | `true` | Enable model diagnostics. |
| `suanpan.diagnostics.unknownType` | `true` | Report unknown type keywords. |
| `suanpan.diagnostics.unknownReference` | `false` | Report tags not defined in the same file. |

## How it works

The command database in `data/database.json` is generated from the suanPan C++
parser, which is the single source of truth. Argument templates and their
documentation come from the bundled syntax files, which follow the manual.

```bash
python scripts/generate_database.py --source ../suanPan
```

See [docs/DESIGN.md](docs/DESIGN.md) for the architecture and the list of
implemented and deliberately omitted features.

## Demo

![demo](images/example.gif)
