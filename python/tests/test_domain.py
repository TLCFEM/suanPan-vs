"""Tests of the domain helper classes (nodes, groups, orientations,
modifiers, initial conditions, masses and expressions)."""

import pytest

from suanpan.domain import (
    B3DC,
    CustomNodeGroup,
    ElementGroup,
    GroupGroup,
    InitialCondition,
    InitialDisplacement,
    InitialVelocity,
    NodalMass,
    Node,
    NodeGroup,
    NodeGroupGenerate,
    Orientation,
)


class TestNode:
    def test_2d_node(self):
        assert Node(tag=1, coordinate=[0, 0]).to_commands() == ["node 1 0 0"]

    def test_3d_node(self):
        assert Node(tag=2, coordinate=[4, -3, 2]).to_commands() == ["node 2 4 -3 2"]

    def test_dimension(self):
        assert Node(tag=1, coordinate=[0, 0]).dimension == 2
        assert Node(tag=1, coordinate=[0, 0, 0]).dimension == 3

    def test_floats_formatted_compactly(self):
        assert Node(tag=1, coordinate=[175.0, 193.75]).to_commands() == [
            "node 1 175 193.75"
        ]


class TestGroup:
    def test_node_group(self):
        assert NodeGroup(tag=1, node_tags=[1, 2, 3]).to_commands() == [
            "nodegroup 1 1 2 3"
        ]

    def test_element_group(self):
        assert ElementGroup(tag=2, element_tags=[9]).to_commands() == [
            "elementgroup 2 9"
        ]

    def test_group_group(self):
        assert GroupGroup(tag=4, group_tags=[1, 2]).to_commands() == [
            "groupgroup 4 1 2"
        ]

    def test_custom_expression_group(self):
        assert CustomNodeGroup(tag=5, expression_tag=3).to_commands() == [
            "customnodegroup 5 3"
        ]

    def test_missing_tags_allowed(self):
        assert NodeGroup(tag=7).to_commands() == ["nodegroup 7"]


class TestGenerate:
    def test_generate_nodegroup(self):
        # C++ new_generate: `generate <type> <tag> <start> <interval> <end>`
        group = NodeGroupGenerate(tag=1, start=1, end=3)
        assert group.to_commands() == ["generate nodegroup 1 1 1 3"]


class TestOrientation:
    def test_abstract_raises(self):
        with pytest.raises(NotImplementedError):
            Orientation(tag=1, xyz=[0, 0, 1]).to_commands()

    def test_b3dc(self):
        assert B3DC(tag=1, xyz=[0, 0, 1]).to_commands() == ["orientation B3DC 1 0 0 1"]

    def test_three_components_required(self):
        with pytest.raises(Exception):
            B3DC(tag=1, xyz=[0, 1])


class TestInitial:
    def test_initial_export_omits_tag(self):
        obj = InitialDisplacement(tag=1, dof=2, magnitude=0.5, node_tags=[3])
        assert obj.to_commands() == ["initial disp 0.5 2 3"]

    def test_velocity_alias(self):
        obj = InitialVelocity(tag=1, dof=1, magnitude=2.0, node_tags=[1, 2])
        assert obj.to_commands() == ["initial vel 2 1 1 2"]

    def test_abstract_raises(self):
        with pytest.raises(NotImplementedError):
            InitialCondition(tag=9).to_commands()


class TestMass:
    def test_nodal_mass(self):
        assert NodalMass(tag=1, node_tag=2, magnitude=3.0, dof="1").to_commands() == [
            "mass 1 2 3 1"
        ]
