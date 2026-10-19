# suanPan VS Code extension — design and feature plan

This document records the information collected from the suanPan source code and
manual, and plans the structure of a rich language-support framework for
suanPan model files (`.sp` / `.supan`).

It complements:

* `../scripts/extract_schema.py` — the schema generator;
* `../syntaxes/commands.json` — the generated, machine-readable schema;
* `../src/*.ts` — the runtime framework.

---

## 1. Goal

Provide a maintainable, data-driven extension that understands the suanPan
model language, so that editing a model file gives the same quality of
assistance as a compiled language: syntax highlighting (already present),
completion, hover documentation, signature help, diagnostics, document symbols
and navigation — without duplicating knowledge that already lives in the
suanPan source or its manual.

The guiding principle is **one source of truth per fact**:

| Fact | Source of truth |
|------|-----------------|
| Lexing rules (comments, separators, continuation, booleans) | `suanPan/Toolbox/command.cpp`, `utility.h` + `docs/Basic/Syntax.md` |
| Dispatch (which keyword creates what) | `suanPan/Toolbox/command.cpp`, `*Parser.cpp` |
| Argument names/types/defaults | `suanPan-manual/docs/**/*.md` |
| Token vocabularies (DoF, output) | `suanPan/Domain/ConditionalModifier.cpp`, `Recorder/OutputType.h` |
| TextMate scopes | `syntaxes/syntax.json` |

---

## 2. Information collected

### 2.1 The model language

*suanPan* model files are a line-oriented command language:

* **Case-insensitive** commands and arguments.
* One command per line; a trailing `\` (exactly one per line) continues on the
  next line. Leading/trailing whitespace is trimmed.
* Separators: whitespace and commas (tabs, CR, LF and `,` are normalised to
  spaces by `normalise_command`).
* Comments: `#` only when it is the first non-space character of a line; `!`
  starts an inline comment (everything to end of line). There is no block
  comment and no string quoting.
* Inputs: integers, doubles and strings. Math expressions are **not** supported
  at the file level. A double is accepted where an integer is expected only if
  it has no decimal point.
* Booleans are spelled `true yes 1 on t y` / `false no 0 off f n`.
* Argument notation in the manual: `(n)` required, `[n]` optional, `(2...5)`
  fixed-size group, `(2...)` variable-length group, `[(4) (5) (6)...]`
  repeatable optional group. Arguments are positional; an optional argument may
  only be given after all preceding optional arguments.
* Model structure is three-part: model properties (before the first `step`,
  order-independent), analysis properties (first `step` … `analyze`), and
  post-processing (`analyze` … `exit`).
* Variables: `variable NAME <rest of line>`; references are `$NAME` and are
  substituted textually, once, before tokenisation. Unknown variables are left
  untouched.
* Includes: `file <name>` loads another model file (extension resolution tries
  `<name>`, `.supan`, `.sp`, then lower/upper-case variants).
* Version guard: a leading `#!` line may contain `min-version`/`max-version`.

### 2.2 Command catalogue

`process_command` in `suanPan/Toolbox/command.cpp` dispatches the top-level
keywords. They fall into four groups:

1. **Object factories** — `element`, `material`, `section`, `constraint`,
   `load`, `amplitude`, `step`, `solver`, `integrator`, `converger`,
   `criterion`, `recorder`, `group`, `modifier`, `orientation`, `expression`,
   `initial`, `import`, `interaction`, `mass`, plus alias commands that target
   the same objects (`fix`/`fix2`/`mpc`/`rigidwall`… → constraint,
   `cload`/`bodyforce`/`displacement`/`support*`… → load,
   `nodegroup`/`generate*` → group, `plainrecorder`/`hdf5recorder` → recorder).
2. **Object manipulation** — `enable`, `disable`/`mute`, `erase`/`delete`/`remove`,
   `list`, `protect`, `save`, `set`, `suspend`, `use`, `domain`.
3. **Workflow** — `step`, `analyze`/`analyse`, `precheck`, `peek`, `plot`,
   `benchmark`, `summary`, `reset`, `clear`, `terminal`/`t`, `command`,
   `example`, `upsampling`, `response_spectrum`, `sdof_response`, `qrcode`,
   `license`, `version`, `pwd`, `fullname`, `sleep`, `exit`/`quit`.
4. **Testing** — `materialtest*`, `sectiontest*`.

The generated schema currently captures **85 commands** (from the manual plus
the shipped snippet library) and models the alias→category mapping explicitly.

### 2.3 Object type catalogue

The schema holds **411 object types** with their syntax and parameter
documentation, distributed as:

| category | types | category | types |
|---|---:|---|---:|
| material | 131 | criterion | 9 |
| element | 99 | modifier | 8 |
| section | 41 | initial | 4 |
| constraint | 26 | orientation | 4 |
| integrator | 24 | group | 3 |
| converger | 16 | expression | 2 |
| load / amplitude | 12 each | | |
| solver / step | 10 each | | |

Each type carries one or more *forms*; each form lists its parameters with
index, required/optional flag, variadic flag, type, description and default
value. 40 of the 411 types are not yet documented with a syntax block and are
filled in from `syntaxes/snippets.json`, flagged `"origin": "snippet"` so the
gap is visible.

### 2.4 Token vocabularies

* **DoF identifiers** (`parse_dof`): `PINNED`/`P`, `ENCASTRE`/`E`,
  `XSYMM`/`X`, `YSYMM`/`Y`, `ZSYMM`/`Z`, `1`…`6` (≡ `U1 U2 U3 UR1 UR2 UR3`),
  `U1`…`U6`, `UR1`…`UR3`, `FU1`…`FUR3`, `RADIAL`, `AXIAL`, `RS`, `RW`,
  `DAMAGE`, `PRESSURE`, `TEMPERATURE`, `WARP`.
* **Output/recorder tokens** (`OutputType.h`): `U`, `U1`…, `V*`, `A*`, `S`,
  `S11`…, `E`, `E11`…, `RF`, `DF`, `IF`, `GDF`, `GIF`, `HYDRO`, `MISES`,
  `EEQ`, `EEEQ`, `PEEQ`, `KE`, `SE`, `VE`, `NVE`, `K`, `M`, `DAMAGE`, `HIST`,
  `YF`, `NL`, …
* **`set` options**: `system_solver`, `sub_system_solver`, `precision`,
  `color_model`, `linear_system`, `num_threads`, `num_nodes`, step-size and
  tolerance parameters, …

### 2.5 Cross-checks and discoveries

The manual, the C++ dispatch tables and the shipped snippet library disagree in
places. Notable findings, useful for both the extension and the suanPan
maintainers:

* **Manual typo**: `suanPan-manual/docs/Collection/Define/amplitude.md`'s
  snippet-derived entry exposes `amplitutde` as a command — a misspelling of
  `amplitude`. The generator reproduces the manual faithfully, so the
  extension can surface it only after the manual is fixed.
* **Undocumented types**: converger theory pages (e.g. `AbsDisp.md`) have no
  `## Syntax` block; these are recovered from the snippet library.
* **Step pages** (`Static.md`, `Dynamic.md`) use un-titled or nested code
  fences; the extractor tolerates both.
* **Recorder variable tokens** are a separate vocabulary from DoF tokens and
  should not be validated with the DoF rules.
* **`initial`** takes a plain integer DoF *index*, unlike `fix` which takes a
  DoF *token* — an inconsistency worth flagging in diagnostics later.
* **External modules**: any type name is legal at runtime because
  `external_module::object` falls back to `dlopen`; therefore unknown type
  names are reported as warnings, never errors.
* The generic pages (`element <name> …`, `converger (1) …`) use placeholders as
  the second token; the extractor only treats an identifier as a type name.

---

## 3. Architecture

### 3.1 Data pipeline

```
suanPan-manual/docs/**/*.md ─┐
syntaxes/*.json (snippets)  ─┼─► scripts/extract_schema.py ─► syntaxes/commands.json
static vocabularies         ─┘                                      │
                                                                    ▼
                                              src/schema.ts  (Registry, lookup API)
```

`extract_schema.py` parses the manual's regular idiom — a `text` code fence
containing one or more `command Type (…) [ …]` lines followed by
`# (n) type, description[, default: …]` comments — and emits a JSON document
with `commands`, `types`, `categories`, `aliasCategory`, `dofTokens`,
`outputTokens` and `enumOptions`. Documentation wins; snippets only fill gaps.
The script is defensive and skips pages that do not follow the idiom.

Regenerate with `npm run schema` (requires the three-repository layout) and run
`npm run smoke` to validate the result.

### 3.2 Runtime modules

| module | responsibility |
|--------|----------------|
| `src/schema.ts` | Typed schema plus the `Registry` lookup layer (by keyword, by type, by category, alias→category). |
| `src/parser.ts` | The lexer: physical lines → logical commands with positioned tokens, applying the comment/separator/continuation rules. |
| `src/indexer.ts` | Semantic pass: resolves each logical line to a schema entry/form, validates arguments, and builds the object table (category → tag), variable table, references and diagnostics. Also classifies which numeric argument refers to which object category. |
| `src/providers.ts` | VS Code integration: hover, completion, signature help, document symbols, go-to-definition and the diagnostic collection. |
| `src/extension.ts` | Activation: existing `suanPan: Run this model` command and path setup, plus registration of the language features. |

Data flow for a request:

```
TextDocument ─► parser.parseDocument ─► LogicalLine[]
                     │
             indexer.buildIndex(document, registry)
                     │  ModelIndex { objects, variables, refs, issues }
                     ├─► diagnostics collection
                     └─► hover / completion / signature / symbols / definition
```

The index is cached per document version so repeated provider calls are cheap.

### 3.3 Configuration

`suanpan.languageFeatures` (boolean, default `true`) enables or disables the
language framework at activation time.

---

## 4. Feature catalogue

Legend: **done** = implemented in this framework; **planned** = designed and
feasible, not yet implemented; **future** = larger effort / needs more data.

| # | Feature | Status | Mechanism |
|---|---------|--------|-----------|
| 1 | Syntax highlighting | done (pre-existing) | TextMate grammar |
| 2 | Snippet expansion | done (pre-existing) | `syntaxes/*sections.json`, `snippets.json` |
| 3 | Hover for commands, types, category keywords | done | schema summary + syntax + params |
| 4 | Hover for `$variables` and DoF/output tokens | done | indexer + vocabularies |
| 5 | Completion of commands and category keywords | done | registry |
| 6 | Completion of object types per category | done | registry, filtered by keyword |
| 7 | Completion of DoF identifiers | done | schema `dofTokens` |
| 8 | Completion of referenced object tags (nodes, materials, sections…) | done | object table in the index |
| 9 | Completion of `set` properties and enumerated values | done | `enumOptions` + `set` forms |
| 10 | Completion of `$variable` references | done | variable table |
| 11 | Signature help with active parameter and defaults | done | form parameters |
| 12 | Document symbols (outline of objects and variables) | done | index |
| 13 | Go-to-definition for tags and variables | done | index + `referenceCategory` |
| 14 | Diagnostics: unknown command | done | registry / builtin list |
| 15 | Diagnostics: unknown object type (warning, external modules allowed) | done | registry |
| 16 | Diagnostics: duplicate object tags | done | object table |
| 17 | Diagnostics: missing required arguments | done | form arity |
| 18 | Diagnostics: invalid DoF identifier | done | vocabulary |
| 19 | Diagnostics: non-integer tag / non-numeric value | done | form parameter types |
| 20 | Diagnostics: undefined `$variable` reference | done | variable table |
| 21 | Find all references to a tag or variable | planned | reuse index; needs a workspace-wide object model |
| 22 | Rename object tags / variables | planned | WorkspaceEdit over references |
| 23 | Folding by `step` / `analyze` blocks and continuation lines | planned | parser + `foldingRangeProvider` |
| 24 | Semantic tokens for category/type/parameter roles | planned | parser (grammar already classifies most) |
| 25 | Code actions: fix unknown type by closest match, insert missing arguments | planned | registry fuzzy match |
| 26 | Resolve `file` includes across the workspace | planned | follow `file` commands, merge indices |
| 27 | Workspace symbols across model files | planned | reuse document symbols |
| 28 | Documentation links (open the rendered manual page) | planned | `Entry.doc` |
| 29 | CodeLens “Run this model” / “Peek result” | planned | existing task runner + `peek` |
| 30 | Problem matcher for `suanpan -f` output | planned | task/`problemMatchers` contribution |
| 31 | Formatting / normalisation (align columns, wrap long lines) | future | formatter needs style decisions |
| 32 | Type checking of full expressions and `set` interactions | future | needs a richer semantic model |
| 33 | Validation of recorder output tokens per object type | future | needs per-object output-type tables from the manual |

---

## 5. Diagnostics rules (current)

All diagnostics are produced by `src/indexer.ts`, are scoped to the document
and are emitted with source `suanPan`. Unknown type names are warnings because
external modules are legal; genuine syntax problems are also warnings to avoid
false positives while the model is being typed.

1. Unknown top-level command.
2. Unknown `<category>` type (mentions external modules).
3. Duplicate `<category>` tag, with the line of the first definition.
4. Fewer arguments than the selected form requires.
5. Unknown DoF identifier in a parameter documented as a DoF.
6. Non-integer value in an integer “tag” parameter; non-numeric value in a
   parameter documented as a magnitude/length/ratio/etc.
7. `$variable` reference that is not defined in the file.

---

## 6. Roadmap

1. **Workspace model** — resolve `file` includes and index the whole workspace
   so references, rename and cross-file definition become possible.
2. **Manual links and richer docs** — surface `Entry.doc` as a command to open
   the corresponding manual page; enrich hover with parameter tables.
3. **Semantic tokens** — move beyond the TextMate grammar for precise roles
   (category, type, parameter name, reference tag).
4. **Code actions** — suggest the closest known type name, insert the missing
   required arguments, or convert a numeric DoF to a token.
5. **Task integration** — a problem matcher for the compiler output and a
   CodeLens to run the active model.
6. **Keep the schema honest** — regenerate in CI and fail when the manual and
   the generated schema drift unexpectedly, and report manual typos upstream.

---

## 7. Regenerating and extending

```bash
npm run schema   # regenerate syntaxes/commands.json from the manual
npm run compile  # type-check and build out/
npm run smoke    # run the offline framework tests
```

To add support for a new command or object type, prefer updating the manual
(it is the source of truth) and re-running the generator. If a fact cannot be
expressed in the manual yet, extend the appropriate static vocabulary in
`extract_schema.py` (`DOF_TOKENS`, `OUTPUT_TOKENS`, `ENUM_OPTIONS`,
`ALIAS_CATEGORY`) and regenerate.

---

## 8. Testing

`scripts/smoke.js` stubs the `vscode` API, loads the compiled modules and
exercises the parser, indexer and every provider with assertions. It runs
without an editor (`npm run smoke`) and is suitable for CI. The existing
`@vscode/test-electron` harness remains available for end-to-end tests.
