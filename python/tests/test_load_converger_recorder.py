"""Tests of the load, amplitude, converger and recorder modules."""

from suanpan.base import find_class
from suanpan.converger import FixedNumber, RelIncreDisp
from suanpan.load import (
    Acceleration,
    BodyForce,
    Cload,
    Disp,
    GroupCload,
    Linear,
    Ramp,
    ReferenceLoad,
    Sine,
    Tabular,
)
from suanpan.recorder import (
    ElementRecorder,
    ModalForceRecorder,
    ModalRecorder,
    NodeRecorder,
    Recorder,
)


class TestLoads:
    def test_cload(self):
        # `cload 1 0 100 2 2` from the example file
        assert Cload(
            tag=1, amplitude_tag=0, magnitude=100, dof="2", object_tags=[2]
        ).to_commands() == ["load Cload 1 0 100 2 2"]

    def test_acceleration(self):
        assert Acceleration(
            tag=1, amplitude_tag=0, magnitude=9.8, dof="3", object_tags=[1, 2]
        ).to_commands() == ["load Acceleration 1 0 9.8 3 1 2"]

    def test_body_force(self):
        assert BodyForce(
            tag=1, amplitude_tag=0, magnitude=-1, dof="2", object_tags=[3]
        ).to_commands() == ["load BodyForce 1 0 -1 2 3"]

    def test_reference_load(self):
        assert ReferenceLoad(
            tag=1, amplitude_tag=0, magnitude=5, dof="1", object_tags=[1]
        ).to_commands() == ["load ReferenceLoad 1 0 5 1 1"]

    def test_group_cload(self):
        assert GroupCload(
            tag=1, amplitude_tag=0, magnitude=5, dof="2", object_tags=[1, 2]
        ).to_commands() == ["load GroupCload 1 0 5 2 1 2"]

    def test_displacement(self):
        # the C++ dispatch keyword is `Disp` (alias of the class name)
        assert Disp(
            tag=1, amplitude_tag=0, magnitude=0.5, dof="1", object_tags=[9]
        ).to_commands() == ["load Disp 1 0 0.5 1 9"]


class TestAmplitudes:
    def test_tag_only(self):
        # C++ Ramp/Constant are tag-only amplitudes
        assert Ramp(tag=1).to_commands() == ["amplitude Ramp 1"]

    def test_tabular(self):
        # the C++ Tabular amplitude references a tabulated file
        assert Tabular(tag=1, file_name="tabular.txt").to_commands() == [
            "amplitude Tabular 1 tabular.txt"
        ]

    def test_linear_and_sine_registered(self):
        assert find_class("Linear", "amplitude") is Linear
        assert find_class("Sine", "amplitude") is Sine


class TestConvergers:
    def test_rel_incre_disp(self):
        # `converger RelIncreDisp 1 1E-4 10 1` from the example file
        assert RelIncreDisp(
            tag=1, tolerance=1e-4, max_iteration=10, print_flag=True
        ).to_commands() == ["converger RelIncreDisp 1 0.0001 10 true"]

    def test_fixed_number(self):
        # max_iteration (10) and print_flag (false) defaults are trimmed
        assert FixedNumber(tag=1).to_commands() == ["converger FixedNumber 1"]
        assert FixedNumber(tag=1, max_iteration=5).to_commands() == [
            "converger FixedNumber 1 5"
        ]


class TestRecorders:
    def test_node_recorder(self):
        assert NodeRecorder(tag=1, variable="U", object_tags=[1, 2]).to_commands() == [
            "recorder 1 plain Node U 1 2"
        ]

    def test_hdf5_recorder(self):
        obj = NodeRecorder(tag=1, variable="U", object_tags=[1, 2], use_hdf5=True)
        assert obj.to_commands() == ["recorder 1 hdf5 Node U 1 2"]

    def test_element_recorder(self):
        obj = ElementRecorder(tag=2, variable="S", object_tags=[1])
        assert obj.to_commands() == ["recorder 2 plain Element S 1"]

    def test_modal_recorder(self):
        obj = ModalRecorder(tag=3, directions=["U1", "UR3"])
        assert obj.to_commands() == ["recorder 3 hdf5 Modal U1 UR3"]

    def test_modal_force_recorder(self):
        obj = ModalForceRecorder(tag=4)
        assert obj.to_commands() == ["recorder 4 hdf5 ModalForce"]

    def test_recorder_base_is_abstract(self):
        assert Recorder.sp_abstract is True
