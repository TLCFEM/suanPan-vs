# Extension architecture

This document describes the design of the extended suanPan VS Code extension.

## Design goals

1. **The suanPan interpreter is the single source of truth.** Command names, type
   keywords and aliases are extracted from the C++ parser rather than maintained
   by hand.
2. **No language server process.** A VS Code language extension is enough for the
   feature set below. Everything runs in the extension host, starts instantly and
   works offline.
3. **One parser, many features.** All providers share a small, tolerant parser and
   a cached document model so diagnostics, hover, completion and navigation agree
   with each other.
4. **Fail softly.** A model file may be incomplete while it is being edited.
   Unknown constructs produce warnings, never crashes.

## Layers

```
suanPan C++ source
        │  scripts/generate_database.py  (build time)
        ▼
data/database.json          syntaxes/*.json (argument templates, snippets)
        │                            │
        └────────────┬───────────────┘
                     ▼
              core/database.ts        CommandDatabase
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
  core/parser.ts            core/snippets.ts
  normalise + tokenise      argument metadata
        │
        ▼
  core/model.ts             symbols, references, variables
        │
        ▼
  core/cache.ts             per-document cache keyed by version
        │
        ├── features/completion.ts     context aware completion
        ├── features/hover.ts          command/type/argument documentation
        ├── features/signature.ts      argument signature help
        ├── features/diagnostics.ts    unknown command/type/reference
        ├── features/symbols.ts        outline
        ├── features/definition.ts     go to tag definition
        ├── features/references.ts     find all references to a tag
        ├── features/folding.ts        comments, continuations, object groups
        ├── features/commands.ts       command palette helpers
        └── features/run.ts            run the model in suanPan
```

### Generated command database

`scripts/generate_database.py` reads `Toolbox/command.cpp` and the parser files
(`Element/ElementParser.cpp`, `Material/MaterialParser.cpp`, ...). It extracts

* first-level commands from every `is_equal(command_id, ...)` check,
* descriptions from `print_command()`,
* second-level type keywords from the `is_equal(<type>, ...)` dispatch inside
  `create_new_*` factories, including `is_equal_any` alias groups,
* the suanPan version from `Toolbox/command.h`.

The result is `data/database.json`. Regenerate it whenever suanPan changes:

```bash
python scripts/generate_database.py --source ../suanPan
```

Argument templates and their documentation stay in `syntaxes/*.json`. They are
derived from the manual, are already shipped with the extension, and are merged
with the generated structure at load time. This avoids duplicating ~1.5 MB of
snippet data in the generated database.

### Document parser

`core/parser.ts` implements the semantics of `normalise_command()`:

* `#` comment lines and `!` inline comments,
* commas and tabs as delimiters,
* trailing `\` continuations,
* case-insensitive keywords (lookups are lower case).

It records original source positions for every token, so all providers can
produce accurate ranges without re-scanning the text.

### Document model

`core/model.ts` builds:

* a symbol table `category -> tag -> definition`,
* variable definitions (`variable`/`var`),
* the list of domains,
* tag references resolved from argument documentation (`material tag`,
  `node i`, ...) and object-management commands (`peek node 3`).

This is the piece that enables understanding *relationships*: an element knows
which material/section/node tags it uses because the manual-derived argument
documentation says so.

## Implemented features

| Feature | What it does |
| --- | --- |
| Completion | Commands at line start; type keywords after `element`, `material`, `section`, `step`, ...; section designations such as `NZ2D 1000WB215`; `set` properties; tag values for arguments documented as `material tag`, `node i`, etc.; boolean literals; `$variables`. Selecting a type inserts the documented argument template. |
| Hover | Command summary and syntax, type summary and argument table, argument description, `$variable` value, and the definition of referenced tags. |
| Signature help | Argument list with the active argument highlighted, using the template stored in the syntax files. |
| Diagnostics | Unknown commands; unknown type keywords (can be disabled for external modules); optional warnings for tags that are not defined in the same file; dangling line continuations. |
| Outline | Every defined object as `category tag` with its type. |
| Go to definition | Material/section/node/... tags resolve to their definition. |
| Find references | All uses of a tag across the document. |
| Folding | Comment blocks, continuation commands and contiguous object groups. |
| Run | The original `suanpan.run` command, now with an editor title button and a dedicated path command. |
| Command palette | `suanPan: Insert a command template` lists every command from the current suanPan version and inserts its template. |
| Version check | `suanPan: Show the command database version`. |

## Deliberately out of scope

* **Full semantic analysis / type checking.** suanPan has a dynamic command
  grammar with optional arguments, repetitions and named designations. Static
  validation beyond the generated keyword lists would produce false positives.
* **A separate language server.** It would add packaging, transport and startup
  cost without enabling any of the features above.
* **Round-trip formatting.** Reflowing commands is risky (backslash continuations,
  `$variables`, file names) and provides little value compared with the above.
* **Editing `suanPan` or `suanPan-manual`.** The extension consumes both as
  read-only sources; the generator lives in this repository.

## Adding a feature

1. Add a provider under `src/features/`.
2. Read documents through `runtime.cache.get(document)`; never parse directly.
3. Register the provider in `src/extension.ts`.
4. Keep behaviour consistent with `core/parser.ts` semantics.
