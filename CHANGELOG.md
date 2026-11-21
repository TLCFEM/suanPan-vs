# Change Log

## Unreleased

1. sync the command database and Python classes with suanPan 4.3.1, including the adjusted `EU2DA`/`EU3DA`/`NZ2DA`/`NZ3DA`/`US2DA`/`US3DA`/`US2DAC`/`US3DAC` section registries,
2. read coded-section designations from the C++ `TokenRegistry<vec>` tables so completion, hover and diagnostics cover every accepted shape, including the adjusted registries,
3. fix the Python exporters to emit the command word (`section EU2D IPE300 9 ...`) and to place a designation between the keyword and the tag,
4. harden the shared C++ registry reader against signatures and braces in comments and string literals, and add duplicate-keyword validation to the database generator,
5. tolerate UTF-8 BOMs and report dangling continuations that contain no partial token, and keep the language grammar in sync with the registry (missing `DC3D4M`/`DCP4M`/`ExpHoffman`/`NonlocalIsotropicElastic3D` and the `LeeElementalNewmark` spelling).

## v0.2.1

1. allow customising the container runtime executable, so `podman`, `nerdctl` and other Docker-compatible runtimes can be used instead of `docker`.

## v0.2.0

1. generate the command database directly from the suanPan parser,
2. context aware completion for commands, types, section designations, `set` properties, tags and boolean values,
3. hover documentation for commands, types, arguments and referenced tags,
4. signature help,
5. diagnostics for unknown commands, unknown types, undefined references and dangling continuations,
6. document outline, go to definition, find references and folding,
7. command palette helpers and an editor title run button,
8. migrate to the ESLint flat configuration format.

## v0.1.0

1. initial release
