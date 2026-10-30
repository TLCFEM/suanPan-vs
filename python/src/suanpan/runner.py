"""Utilities to call the suanPan executable for analyses.

The runners write an input file into a dedicated per-analysis folder
(the "analysis folder") and invoke the executable with its command line
interface:

    suanPan [-v] [-np] [-nc] [-nu] [-f INPUT_FILE] [-o OUTPUT_FILE]

which mirrors ``Toolbox/argument.cpp``.  Customisable folders make batch
and parallel runs straightforward: every analysis gets its own working
directory, so HDF5 recorders and output files never collide.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from suanpan.model import Model

__all__ = ["ExecutionOptions", "RunResult", "Runner"]

#: default executable name, as built by the CMake project
DEFAULT_EXECUTABLE = "suanPan"


@dataclass
class ExecutionOptions:
    """Options mirroring the ``suanPan`` command line switches."""

    #: path of the input file, relative to the run folder if not absolute
    input_file: str = "model.supan"
    #: redirect terminal output to a file inside the run folder
    output_file: str | None = None
    #: -np, suppress (most) terminal output
    no_print: bool = False
    #: -nc, suppress colored output
    no_color: bool = False
    #: -nu, skip the new version check
    no_update: bool = True
    #: -vb, very verbose output
    verbose: bool = False
    #: optional extra arguments appended verbatim
    extra_args: list[str] = field(default_factory=list)

    def to_args(self, folder: Path) -> list[str]:
        path = Path(self.input_file)
        if not path.is_absolute():
            path = folder / path
        args = ["-f", str(path)]
        if self.output_file:
            out = Path(self.output_file)
            if not out.is_absolute():
                out = folder / out
            args += ["-o", str(out)]
        if self.no_print:
            args.append("-np")
        if self.no_color:
            args.append("-nc")
        if self.no_update:
            args.append("-nu")
        if self.verbose:
            args.append("-vb")
        args += list(self.extra_args)
        return args


@dataclass
class RunResult:
    """Outcome of one analysis run."""

    folder: Path
    input_file: Path
    returncode: int
    stdout: str
    stderr: str
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Runner:
    """Build analysis folders, write input files and run the executable.

    ``executable`` resolves in order to: an explicit path, ``SUANPAN_EXE``
    in the environment or the ``suanPan`` binary found on ``PATH``.
    """

    def __init__(
        self,
        executable: str | os.PathLike | None = None,
        work_root: str | os.PathLike = "suanpan-runs",
        timeout: float | None = None,
    ) -> None:
        self.executable = self._resolve_executable(executable)
        self.work_root = Path(work_root)
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_executable(executable: str | os.PathLike | None) -> str:
        if executable is not None:
            return os.fspath(executable)
        env = os.environ.get("SUANPAN_EXE")
        if env:
            return env
        found = shutil.which(DEFAULT_EXECUTABLE)
        if found:
            return found
        # fall back to the bare name -- subprocess will surface the error
        return DEFAULT_EXECUTABLE

    def _prepare_folder(self, folder: Path) -> Path:
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError(f"analysis folder already exists: {folder}")
        folder.mkdir(parents=True)
        # ensure the folder is usable regardless of a restrictive umask
        os.chmod(
            folder,
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
        )
        return folder

    def _resolve_folder(self, folder: str | os.PathLike) -> Path:
        """Resolve an analysis folder; relative paths are taken under
        ``work_root``."""
        folder = Path(folder)
        if not folder.is_absolute():
            folder = self.work_root / folder
        return folder

    def prepare(
        self,
        model: Model | str,
        folder: str | os.PathLike,
        options: ExecutionOptions | None = None,
    ) -> Path:
        """Create the analysis folder and write the input file.

        ``model`` accepts a :class:`Model` or raw input file text.
        """
        folder = self._prepare_folder(self._resolve_folder(folder))
        input_path = Path(
            options.input_file if options else ExecutionOptions().input_file
        )
        if not input_path.is_absolute():
            input_path = folder / input_path
        text = model.export_text() if isinstance(model, Model) else str(model)
        input_path.write_text(text)
        # keep the input readable for other users (custom folders may be
        # shared by batch runs with different umasks)
        os.chmod(input_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        return input_path

    def command_line(self, input_path: Path, options: ExecutionOptions) -> list[str]:
        return [self.executable, *options.to_args(input_path.parent)]

    def run(
        self,
        model: Model | str,
        folder: str | os.PathLike,
        options: ExecutionOptions | None = None,
        cleanup: bool = False,
    ) -> RunResult:
        """Run one analysis in ``folder``.

        ``cleanup=True`` removes the folder entirely afterwards; use
        with care when recorders write results into it.
        """
        options = options or ExecutionOptions()
        input_path = self.prepare(model, folder, options)
        argv = self.command_line(input_path, options)
        completed = subprocess.run(
            argv,
            cwd=input_path.parent,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        result = RunResult(
            folder=input_path.parent,
            input_file=input_path,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            command=argv,
        )
        if cleanup:
            shutil.rmtree(result.folder, ignore_errors=True)
        return result

    def run_many(
        self,
        jobs: list[tuple[Model | str, str | os.PathLike]],
        options: ExecutionOptions | None = None,
        parallel: int | None = None,
        cleanup: bool = False,
    ) -> list[RunResult]:
        """Run a batch of ``(model, folder)`` jobs, optionally in parallel.

        Returns results in the order of ``jobs``.
        """
        workers = parallel if parallel else min(len(jobs), os.cpu_count() or 1)
        results: list[RunResult | None] = [None] * len(jobs)
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(self.run, model, folder, options, cleanup): index
                for index, (model, folder) in enumerate(jobs)
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        return [result for result in results if result is not None]
