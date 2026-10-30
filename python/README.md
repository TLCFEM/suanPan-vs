# suanpan-py

A Python object model for the [suanPan](https://github.com/TLCFEM/suanPan)
finite element program: every parsable command of the C++ application is
represented by a pydantic model class, objects export valid suanPan input
files, and a runner utility invokes the executable for analyses under
customisable folders.

The C++ source is the only source of truth: keywords, signatures, defaults
and quirks (eof-guarded optionals, clamped values, `is_true` boolean
spellings, DOF token expansions, ...) are mirrored from the C++ parsers,
and inconsistencies found on the way were fixed rather than papered over.

## Installation

```bash
pip install -e .          # from this folder
```

Requires Python >= 3.10 and pydantic >= 2.6.

## Layout

The package is structured like the original C++ application:

| Python package        | C++ counterpart                        |
|-----------------------|----------------------------------------|
| `suanpan.domain`      | `Domain/` (node, group, DOF, orientation, ...) |
| `suanpan.material`    | `Material/MaterialParser.cpp`          |
| `suanpan.element`     | `Element/ElementParser.cpp`            |
| `suanpan.section`     | `Section/SectionParser.cpp`            |
| `suanpan.constraint`  | `Constraint/ConstraintParser.cpp`      |
| `suanpan.load`        | `Load/` + amplitudes                   |
| `suanpan.converger`   | `Converger/ConvergerParser.cpp`        |
| `suanpan.recorder`    | `Recorder/`                            |
| `suanpan.solver`      | `Solver/` (integrators + solvers)      |
| `suanpan.step`        | `Step/StepParser.cpp`                  |
| `suanpan.model`       | the whole domain + step composition    |
| `suanpan.runner`      | `Toolbox/argument.cpp` command line    |

## Quick start

```python
from suanpan.domain import Node
from suanpan.material import Bilinear1D
from suanpan.element import T2D2
from suanpan.constraint import Fix
from suanpan.load import Cload
from suanpan.solver import Newton
from suanpan.converger import RelIncreDisp
from suanpan.recorder import NodeRecorder
from suanpan.step import StaticStep
from suanpan.model import Model

model = Model(title="A TEST MODEL FOR BILINEAR1D MATERIAL")
model.add(Node(tag=1, coordinate=[0, 0]))
model.add(Node(tag=2, coordinate=[4, 0]))
model.add(Node(tag=3, coordinate=[0, -3]))
model.add(Bilinear1D(tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2))
model.add(T2D2(tag=1, node_tags=[1, 2], material_tag=1, area=10))
model.add(T2D2(tag=2, node_tags=[3, 2], material_tag=1, area=10))
model.add(Fix(tag=1, dof="E", node_tags=[1, 3]))  # E expands to U1..UR3

step = StaticStep(tag=1, symm_mat=True)
step.solver = Newton(tag=1)
step.convergers = [
    RelIncreDisp(tag=1, tolerance=1e-4, max_iteration=10, print_flag=True)
]
model.add(step)

model.add(Cload(tag=1, amplitude_tag=0, magnitude=100, dof="2", object_tags=[2]))
model.add(NodeRecorder(tag=1, variable="U", object_tags=[2]))

print(model.export_text())
model.save("bilinear1d.supan")
```

This reproduces `Example/Material/Bilinear1D.supan` of the C++ repository.

## Export conventions

* Tokens are **positional** exactly as the C++ parsers read them. Optional
  values that are eof-guarded in C++ (`get_optional_input`) are omitted
  when they still carry their default, and once a later value is set all
  earlier positional tokens are kept.
* `is_true` accepts `true/1/on/yes/y/t`, `is_equal` is case-insensitive --
  exports use the canonical C++ dispatch spelling (`B21`, `Disp`,
  `modifiedNewton`, ...).
* Validation mirrors the C++ semantics: fixed node counts (`CSMQ5` needs
  five nodes), fixed `dim` vector lengths (I sections need six), DOF token
  expansion (`E`, `P`, `X`, `Y`, `Z`, `FU1`, ...), clamped values (wall
  restitution to `[0, 1]`, spectral radii to `[0, 1]`), and cross
  references (a section referencing a missing material is rejected).

## Running analyses

```python
from suanpan.model import Model
from suanpan.runner import ExecutionOptions, Runner
from suanpan.step import StaticStep

model = Model()
model.add(StaticStep(tag=1))

runner = Runner(work_root="output/suanpan-runs")  # customisable folder
result = runner.run(model, "case_1", ExecutionOptions(no_print=True))
print(result.ok, result.returncode, result.stdout)
```

* The executable resolves to an explicit path, `$SUANPAN_EXE`, then
  `suanPan` on `PATH`.
* Every analysis gets its own working directory (created under
  `work_root` for relative names), so HDF5 recorders and output files of
  batch runs never collide.
* `run_many([...])` executes a batch of `(model, folder)` jobs in a
  thread pool.
* Command line switches mirror `Toolbox/argument.cpp`:
  `-f` input file, `-o` output file, `-np` no print, `-nc` no color,
  `-nu` no update check, `-vb` verbose.

## Classes

* `suanpan.base.SuanpanObject` is the pydantic base of every command
  object; `to_commands()` returns the command lines, `str(obj)` the
  single line. Every concrete class registers itself in a keyword
  registry: `suanpan.base.find_class(keyword, command)` locates a class
  by its C++ keyword, `iter_classes()` enumerates all of them.
* `suanpan.model.Model` composes the whole model with typed pools
  (`nodes`, `materials`, `sections`, `elements`, ..., `steps`), a
  builder `add()` that routes by type, duplicate-tag and cross-reference
  validation, and exports in the exact order the C++ parser consumes
  commands.
* `suanpan.step` steps compose their `integrator`, `solver`, `convergers`,
  `criteria`, `constraints`, `loads` and `recorders` into a complete
  step cell.

More examples live in [`examples/`](examples/).

## Regenerating the bulk families

The material, element and section families (270+ classes) are generated
from machine-readable specs in `specs/` (extracted from the C++ parsers)
by `tools/generate.py`:

```bash
pip install pyyaml        # only needed for regeneration
python tools/generate.py
```

This rewrites `src/suanpan/{material,element,section}/_generated.py`.
Hand-written specials (`Balloon`, `PatchQuad`, step/runner/model logic,
...) live beside them in `_special.py` / their own modules.

## Tests

```bash
pip install pytest
python -m pytest
```

The suite checks exports against ground truths extracted from the C++
parsers, including the example files `Example/Material/Bilinear1D.supan`
and `Example/Element/DCP4.supan`.

## License

GPL-3.0, following the suanPan project.
