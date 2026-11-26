# Routine suanPan sync

This checklist brings `suanPan-vs` up to date with a new upstream
`suanPan` revision. The C++ parser is the single source of truth; most
artefacts below are generated from a sibling `../suanPan` checkout, while a
small amount of manual documentation and grammar metadata still has to be
reviewed by hand.

## What is generated and what is not

| Artefact | Source | Regenerate with |
| --- | --- | --- |
| `data/database.json` | C++ command and `TokenRegistry` tables, plus snippet summaries | `scripts/generate_database.py` |
| `python/src/suanpan/{material,element,section}/_generated.py` | C++ registries plus `python/specs/*.yaml` | `python/tools/generate.py` |
| `syntaxes/syntax.json` | hand-maintained TextMate grammar; keyword alternations must follow the database | manual |
| `syntaxes/snippets.json`, `syntaxes/{eu,nz,us}_sections.json` | hand-maintained argument templates from the manual | manual |
| `python/specs/*.yaml` | hand-maintained handler layouts and defaults | manual |
| Python classes outside material/element/section | hand-written | manual |
| `CHANGELOG.md`, docs, `package.json` version | hand-written | manual |

> Never edit `data/database.json` or the `_generated.py` files by hand. Fix the
> reader/spec instead and regenerate.

## Before starting

1. Check out the target upstream revision and record its version:

   ```bash
   git -C ../suanPan fetch --tags
   git -C ../suanPan checkout <tag-or-commit>
   git -C ../suanPan log -1 --oneline
   grep -nE 'constexpr auto SUANPAN_(MAJOR|MINOR|PATCH)' ../suanPan/Toolbox/command.h
   ```

2. Start a feature branch in this repository:

   ```bash
   git switch -c feature/sync-suanpan-<version>
   git status --short
   ```

3. Install the local development tooling once per environment:

   ```bash
   cd python
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   cd ..
   npm install
   ```

   The CI workflow uses Node 24; the extension tests also need an X server (see
   [Verification](#verification)).

## 1. Regenerate the command database

From the repository root:

```bash
python3 scripts/generate_database.py \
    --source ../suanPan \
    --output data/database.json
```

The generator prints the command count and the detected suanPan version, for
example:

```text
wrote 127 commands (suanPan 4.3.1) to data/database.json
```

Review the result before moving on:

```bash
git diff --stat data/database.json
git diff data/database.json
```

Check in particular:

- the `version` field,
- new or removed first-level commands,
- new, renamed or removed type keywords and aliases,
- changes under `section_designations.tables` and
  `section_designations.containers`,
- no unrelated command changed category.

Notes:

- A duplicate keyword is a hard error in the generator. Do not work around it
  by editing the JSON; inspect the upstream registry or the reader.
- New `create_new_*` dispatchers need a category in `FACTORY_CATEGORY` in
  `scripts/generate_database.py`. If the command category is new to the editor,
  also update `TYPED_CATEGORIES` in `src/core/database.ts`.
- `set` and `initial` still use legacy `is_equal` chains (`EXTRA_COMMAND_TYPES`
  in the generator). If upstream migrates them to `TokenRegistry`, remove the
  fallback and verify their types are read by the registry path.
- Coded-section designations are read automatically from
  `TokenRegistry<vec>` tables. Inspect them with:

  ```bash
  python3 scripts/suanpan_parser.py --source ../suanPan --designations
  ```

  If the table functions or the container-to-table search order change
  upstream, update `read_section_designations()` in
  `scripts/suanpan_parser.py` and its tests.

## 2. Regenerate the Python classes

From `python/`:

```bash
PYTHONPATH=src python tools/generate.py --source ../../suanPan
PYTHONPATH=src python tools/generate.py --source ../../suanPan --check
```

The first command rewrites the three `_generated.py` files; `--check` must then
pass with no changes.

Read the per-family summary and every `skipped:` line:

- `(no spec entry)` means the keyword has no usable layout in
  `python/specs/*.yaml`, so no class is emitted. Add a spec entry, or implement
  a hand-written class and list the keyword in `SPECIALS` in
  `python/tools/generate.py`.
- `(flag options)` means the handler uses flags/option loops that the generic
  positional exporter cannot represent. Implement it in the family's
  `_special.py` and list it in `SPECIALS`, or extend the generator if the
  pattern is reusable.

When adding a spec entry:

- keep `tag` as the first command-line parameter,
- put a coded-section `designation` between the keyword and the tag,
- copy defaults and optional/required rules from the C++ handler,
- do not maintain aliases in the spec; aliases come from the registry,
- refresh the spec file header if it documents a superseded dispatch layout.

## 3. Update the hand-written Python families

Only material, element and section are bulk generated. New or renamed
keywords in `constraint`, `converger`, `criterion`, `interaction`, `load`,
`modifier`, `orientation`, `recorder`, `solver`, `step`, `domain`, and the
top-level commands need hand-written classes and tests in
`python/src/suanpan/`.

Use the database diff as the work list, and test the exact exported command
line, for example:

```python
assert obj.to_commands() == ["section EU2D IPE300 9 1"]
```

## 4. Sync the editor grammar and snippets

The database drives completion, hover and diagnostics, but the TextMate
grammar still contains explicit keyword alternations. Update them when the
database changes:

- `syntaxes/syntax.json` for the enumerated command lists, in particular
  `amplitude`, `converger`, `constraint`, `element`, `initial`, `integrator`,
  `material`, `modifier`, `orientation`, `set`, `solver`, `step`, and the coded
  section containers,
- `syntaxes/snippets.json` for type-level parameter templates; keep argument
  descriptions such as `material tag` or `node i`, because `core/model.ts`
  uses them to resolve references,
- `syntaxes/{eu,nz,us}_sections.json` only when a richer per-designation
  template/documentation is useful; the accepted designation names themselves
  come from the C++ tables, so a missing shape snippet does not disable
  completion,
- `SECTION_PROTOTYPES` in `src/core/database.ts` when a new adjusted coded
  section should reuse a nominal container's template.

`data/database.json` copies snippet descriptions into type summaries, so
rerun `scripts/generate_database.py` after editing snippet descriptions. The
verification step below also catches this drift.

`python/tests/test_syntax_metadata.py` enforces exact agreement for
`amplitude`, `converger`, `element`, `initial`, `integrator`, `material`,
`modifier`, `orientation`, `set`, `solver`, and the coded section containers.
The remaining lists, notably `constraint` and `step`, still need a manual
comparison. Run the test after editing the grammar; it reports the missing or
extra spellings.

Helpers:

```bash
python3 scripts/print_syntax.py <keyword>   # preview a snippet
python3 scripts/sort.py                     # normalise syntax.json/snippets.json
```

`scripts/to_snippet.py` and `scripts/to_syntax.py` build the optional Sublime
artefacts; they write into `../suanPan/Enhancement` when that checkout exists
and are not part of the VS Code runtime. Do not commit their output here.

## 5. Update tests, documentation and changelog

- Add or update tests for new commands, keywords, aliases, coded-section
  designations, and changed tag ownership.
- When upstream retires a keyword or handler mode, regenerate the database and
  remove it from the specs, hand-written classes, tests and grammar.
- Keep `python/tests/test_parser_metadata.py` aligned with the current
  dispatcher layout; `test_current_suanpan_layout` fails when upstream moves
  tag extraction between dispatcher and handler.
- Add a `CHANGELOG.md` entry under `Unreleased`, naming the suanPan version and
  highlighting user-visible grammar/API changes.
- Update `docs/DESIGN.md` and `python/README.md` if the generation pipeline or
  ownership rules changed.
- Do not bump `package.json` or the Python package version for a routine sync;
  both are release-time decisions.

## Verification

Run the full local gate from the repository root. Regenerate the database to a
temporary file first to prove that the committed data is reproducible:

```bash
python3 scripts/generate_database.py --source ../suanPan --output /tmp/database.json
cmp data/database.json /tmp/database.json

cd python
PYTHONPATH=src python tools/generate.py --source ../../suanPan --check
python -m pytest -q
python -m ruff check tools tests
cd ..

npm test
```

`npm test` runs `compile`, `lint`, then the VS Code extension tests. On a
headless Linux host use:

```bash
xvfb-run -a npm test
```

If Electron reports missing shared libraries (`libnspr4.so`, `libnss3.so`,
GTK/X11 libraries), install the distribution packages or run inside a
container that provides a desktop stack. The first run downloads the VS Code
test build into `.vscode-test/`.

Optional packaging check:

```bash
npx vsce package
```

Finally:

```bash
git diff --check
git status --short
```

The current CI workflow only builds the VSIX package. It does not run the
Python suite or the extension tests, so the local gate above is the effective
quality check.

## Commit and push

```bash
git add -A
git diff --cached --check
git commit -m "Sync with suanPan <version>"
git push -u origin feature/sync-suanpan-<version>
```

Open a pull request against `master`. Keep the branch focused on the sync;
unrelated fixes should go to separate branches.

## Troubleshooting

| Symptom | Likely cause / action |
| --- | --- |
| `duplicate <category> keyword` | Upstream registry really contains a conflicting spelling, or the reader mis-parsed the table. Inspect `scripts/suanpan_parser.py` output; do not edit `database.json`. |
| Python generator reports `(no spec entry)` | Add the layout to the matching YAML spec or implement a special class. |
| Python generator reports `(flag options)` | The handler has option flags the generic exporter cannot express; add a special or extend the generator. |
| `test_grammar_keywords_match_the_database` fails | Update the corresponding alternation in `syntaxes/syntax.json`. |
| `test_grammar_covers_every_coded_section_container` fails | Add/remove the container in the coded-section grammar pattern and check `SECTION_PROTOTYPES`. |
| `test_current_suanpan_layout` fails | Tag ownership changed upstream. Update the expectation, generated headers, docs and tests. |
| Designations are missing from completion | Run `scripts/suanpan_parser.py --designations`; check the reader and the container-to-table mapping. |
| `generate.py --check` reports stale files | Regenerate; never hand-edit `_generated.py`. |
| Extension tests fail with `Missing X server or $DISPLAY` | Run `xvfb-run -a npm test`. |
| Extension tests fail with `libnss3.so`/`libgbm.so` errors | Install the Electron/GTK runtime libraries for the distribution. |
