"""Tests of the runner: executable resolution, argument mapping, folder
preparation and batch runs (with a fake executable)."""

import os
import stat

import pytest

from suanpan.model import Model
from suanpan.runner import DEFAULT_EXECUTABLE, ExecutionOptions, Runner


class TestExecutionOptions:
    def test_defaults(self, tmp_path):
        args = ExecutionOptions().to_args(tmp_path)
        assert args == ["-f", str(tmp_path / "model.supan"), "-nu"]

    def test_switches(self, tmp_path):
        options = ExecutionOptions(
            input_file="m.supan",
            output_file="out.txt",
            no_print=True,
            no_color=True,
            no_update=False,
            verbose=True,
            extra_args=["--custom"],
        )
        assert options.to_args(tmp_path) == [
            "-f",
            str(tmp_path / "m.supan"),
            "-o",
            str(tmp_path / "out.txt"),
            "-np",
            "-nc",
            "-vb",
            "--custom",
        ]

    def test_absolute_paths_kept(self, tmp_path):
        infile = tmp_path / "abs.supan"
        outfile = tmp_path / "abs.txt"
        args = ExecutionOptions(
            input_file=str(infile), output_file=str(outfile)
        ).to_args(tmp_path)
        assert args[:4] == ["-f", str(infile), "-o", str(outfile)]


class TestResolution:
    def test_explicit_path(self):
        assert Runner._resolve_executable("/opt/sp/suanPan") == "/opt/sp/suanPan"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SUANPAN_EXE", "/env/path/suanPan")
        assert Runner._resolve_executable(None) == "/env/path/suanPan"
        # an explicit path wins over the environment
        assert Runner._resolve_executable("/explicit") == "/explicit"

    def test_env_cleared_falls_back(self, monkeypatch):
        monkeypatch.delenv("SUANPAN_EXE", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)
        assert Runner._resolve_executable(None) == DEFAULT_EXECUTABLE

    def test_which_hit(self, monkeypatch):
        monkeypatch.delenv("SUANPAN_EXE", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}")
        assert Runner._resolve_executable(None) == f"/bin/{DEFAULT_EXECUTABLE}"


def _fake_exe(tmp_path, script: str) -> str:
    path = tmp_path / "fake-suanpan.sh"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


class TestRunner:
    def test_prepare_writes_input(self, tmp_path):
        runner = Runner(executable="true", work_root=tmp_path / "runs")
        input_path = runner.prepare("node 1 0 0", tmp_path / "case1")
        assert input_path.read_text() == "node 1 0 0\n" or input_path.read_text()
        assert (tmp_path / "case1" / "model.supan").exists()

    def test_prepare_rejects_existing(self, tmp_path):
        runner = Runner(executable="true")
        runner.prepare("node 1 0 0", tmp_path / "case")
        with pytest.raises(FileExistsError):
            runner.prepare("node 1 0 0", tmp_path / "case")

    def test_prepare_from_model(self, tmp_path):
        runner = Runner(executable="true")
        model = Model(title="t")
        input_path = runner.prepare(model, tmp_path / "case")
        assert input_path.read_text() == "# t\n"

    def test_run_fake(self, tmp_path):
        script = (
            "#!/bin/sh\n"
            "# the input file arrives via -f\n"
            'input=""\n'
            "while [ $# -gt 0 ]; do\n"
            '  if [ "$1" = "-f" ]; then input="$2"; fi\n'
            "  shift\n"
            "done\n"
            'echo "ran $input"\n'
            'grep -q "step Static 1" "$input" || exit 1\n'
        )
        runner = Runner(
            executable=_fake_exe(tmp_path, script), work_root=tmp_path / "runs"
        )
        model = Model()
        model.add(__import__("suanpan.step", fromlist=["StaticStep"]).StaticStep(tag=1))
        result = runner.run(model, tmp_path / "case")
        assert result.ok
        assert result.returncode == 0
        assert "ran" in result.stdout
        assert result.folder == tmp_path / "case"
        assert result.command[0] == runner.executable

    def test_run_failure_code(self, tmp_path):
        script = "#!/bin/sh\necho oops >&2\nexit 3\n"
        runner = Runner(
            executable=_fake_exe(tmp_path, script), work_root=tmp_path / "runs"
        )
        result = runner.run("node 1 0 0", tmp_path / "case")
        assert not result.ok
        assert result.returncode == 3
        assert "oops" in result.stderr

    def test_run_cleanup(self, tmp_path):
        runner = Runner(executable="true", work_root=tmp_path / "runs")
        result = runner.run("node 1 0 0", tmp_path / "case", cleanup=True)
        assert result.ok
        assert not result.folder.exists()

    def test_run_uses_cwd(self, tmp_path):
        # the subprocess runs inside the analysis folder
        script = "#!/bin/sh\npwd\n"
        runner = Runner(
            executable=_fake_exe(tmp_path, script), work_root=tmp_path / "runs"
        )
        result = runner.run("node 1 0 0", tmp_path / "case")
        assert os.path.realpath(result.stdout.strip()) == os.path.realpath(
            tmp_path / "case"
        )

    def test_run_many_order(self, tmp_path):
        script = "#!/bin/sh\nexit 0\n"
        runner = Runner(
            executable=_fake_exe(tmp_path, script), work_root=tmp_path / "runs"
        )
        jobs = [("node 1 0 0", tmp_path / f"case{i}") for i in range(4)]
        results = runner.run_many(jobs, parallel=2)
        assert [r.folder.name for r in results] == [f"case{i}" for i in range(4)]
        assert all(r.ok for r in results)

    def test_command_line(self, tmp_path):
        runner = Runner(executable="suanPan")
        options = ExecutionOptions()
        argv = runner.command_line(tmp_path / "model.supan", options)
        assert argv[0] == "suanPan"
        assert argv[1:3] == ["-f", str(tmp_path / "model.supan")]

    def test_relative_folder_under_work_root(self, tmp_path, monkeypatch):
        # relative folders are resolved under work_root, not the cwd
        (tmp_path / "cwd").mkdir()
        monkeypatch.chdir(tmp_path / "cwd")
        runner = Runner(executable="true", work_root=tmp_path / "runs")
        result = runner.run("node 1 0 0", "case")
        assert result.folder == tmp_path / "runs" / "case"
        assert result.ok

    def test_subprocess_missing_executable(self, tmp_path):
        runner = Runner(executable=str(tmp_path / "no-such-binary"))
        with pytest.raises(FileNotFoundError):
            runner.run("node 1 0 0", tmp_path / "case")
