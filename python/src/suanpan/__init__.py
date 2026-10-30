"""suanpan-py: a Python representation of suanPan models.

The package mirrors the layout of the C++ application: classes are
grouped by the directory that owns their parser (material, element,
section, constraint, load, step, solver, converger, recorder, domain).
Every concrete class derives from :class:`suanpan.base.SuanpanObject`
and can export the suanPan input file command lines it depends on;
:class:`suanpan.model.Model` composes them into a complete model and
:class:`suanpan.runner.Runner` executes analyses via the official
executable.
"""

from suanpan.base import SuanpanObject, find_class, iter_classes
from suanpan.model import Model
from suanpan.runner import ExecutionOptions, Runner, RunResult
from suanpan.step import Step

__version__ = "1.0.0"

__all__ = [
    "ExecutionOptions",
    "Model",
    "RunResult",
    "Runner",
    "Step",
    "SuanpanObject",
    "__version__",
    "find_class",
    "iter_classes",
]
