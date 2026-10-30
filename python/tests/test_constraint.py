"""Tests of the constraint module: boundary conditions, walls, criteria
and interactions."""

import pytest

from suanpan.constraint import (
    MPC,
    Embed3D,
    FiniteRigidWallPenalty,
    Fix,
    Fix2,
    FixedLength2D,
    FixedParticle,
    GroupPenaltyBC,
    Hertzian,
    LogicCriteriaAll,
    LogicCriteriaAny,
    MaxDisplacement,
    MaxHistory,
    MaximumForce3D,
    MinDisplacement,
    MinHistory,
    MPCNode,
    MultiplierBC,
    PenaltyBC,
    RestitutionWallPenalty,
    RigidWallPenalty,
    StrainEnergyEvolution,
)


class TestBC:
    def test_fix(self):
        assert Fix(tag=1, dof="U2", node_tags=[1, 2, 3]).to_commands() == [
            "constraint Fix 1 U2 1 2 3"
        ]

    def test_fix_encastre(self):
        # `fix 1 E 1 3` from the example file
        assert Fix(tag=1, dof="E", node_tags=[1, 3]).to_commands() == [
            "constraint Fix 1 E 1 3"
        ]

    def test_aliases(self):
        assert PenaltyBC is Fix and MultiplierBC is Fix2

    def test_fix2(self):
        assert Fix2(tag=2, dof="E", node_tags=[4]).to_commands() == [
            "constraint Fix2 2 E 4"
        ]

    def test_group_penalty(self):
        assert GroupPenaltyBC(tag=3, dof="2", node_tags=[7, 8]).to_commands() == [
            "constraint GroupPenaltyBC 3 2 7 8"
        ]

    def test_dof_validated(self):
        with pytest.raises(Exception):
            Fix(tag=1, dof="bogus", node_tags=[1])
        # 'P' (pinned) is a valid multi-dof token
        assert Fix(tag=1, dof="P", node_tags=[1]).to_commands() == [
            "constraint Fix 1 P 1"
        ]


class TestEmbedFixedLength:
    def test_embed3d(self):
        assert Embed3D(tag=1, element_tag=5, node_tag=9).to_commands() == [
            "constraint Embed3D 1 5 9"
        ]

    def test_fixed_length(self):
        assert FixedLength2D(tag=10, node_i=1, node_j=2).to_commands() == [
            "constraint FixedLength2D 10 1 2"
        ]


class TestTwoNode:
    def test_maximum_force(self):
        assert MaximumForce3D(tag=1, node_i=2, node_j=3, value=100).to_commands() == [
            "constraint MaximumForce3D 1 2 3 100"
        ]


class TestMPC:
    def test_mpc(self):
        obj = MPC(
            tag=1,
            amplitude=0,
            magnitude=1,
            nodes=[
                {"node": 1, "dof": "2", "weight": 0.5},
                {"node": 2, "dof": "3", "weight": -1},
            ],
        )
        assert obj.to_commands() == ["constraint MPC 1 0 1 1 2 0.5 2 3 -1"]

    def test_single_dof_triples(self):
        with pytest.raises(Exception):
            MPCNode(node=1, dof="E", weight=0.5)


class TestWalls:
    def test_parameter_counts(self):
        # rigid walls: raw counts 2/4/6/9 auto-append alpha=1E4
        assert RigidWallPenalty(tag=1, parameters=[0, 1]).to_commands() == [
            "constraint RigidWall 1 0 1"
        ]
        assert RigidWallPenalty(tag=1, parameters=[0, 1, 1e4]).to_commands() == [
            "constraint RigidWall 1 0 1 10000"
        ]

    def test_invalid_count_rejected(self):
        # 8 is neither a raw count (2/4/6/9) nor a final count (3/5/7/10)
        with pytest.raises(Exception):
            RigidWallPenalty(tag=1, parameters=[1.0] * 8)

    def test_finite_wall(self):
        assert FiniteRigidWallPenalty(tag=1, parameters=[0, 1, 0, 1]).to_commands() == [
            "constraint FiniteRigidWall 1 0 1 0 1"
        ]

    def test_restitution_clamped(self):
        # count 3 is a raw count: RC is the trailing value, clamped to [0, 1]
        obj = RestitutionWallPenalty(tag=1, parameters=[0, 1, 1.5])
        assert obj.to_commands() == ["constraint RestitutionWall 1 0 1 1"]


class TestCriteria:
    def test_logic_all(self):
        assert LogicCriteriaAll(tag=1, criterion_tags=[1, 2, 3]).to_commands() == [
            "criterion LogicAll 1 1 2 3"
        ]

    def test_logic_any_requires_tags(self):
        with pytest.raises(Exception):
            LogicCriteriaAny(tag=2, criterion_tags=[])

    def test_strain_energy_evolution(self):
        assert StrainEnergyEvolution(
            tag=1, incre_level=2, final_level=70
        ).to_commands() == ["criterion StrainEnergyEvolution 1 2 70"]

    def test_history_criteria(self):
        assert MaxHistory(tag=1, variable="S", limit=300).to_commands() == [
            "criterion MaxHistory 1 S 300"
        ]
        assert MinHistory(
            tag=1, variable="S", limit=300, element_tags=[1, 2]
        ).to_commands() == ["criterion MinHistory 1 S 300 1 2"]

    def test_displacement_criteria(self):
        assert MaxDisplacement(tag=1, node=2, dof="2", limit=0.1).to_commands() == [
            "criterion MaxDisplacement 1 2 2 0.1"
        ]
        assert MinDisplacement(tag=1, node=11, dof="2", limit=-5.5).to_commands() == [
            "criterion MinDisplacement 1 11 2 -5.5"
        ]

    def test_single_dof_required(self):
        with pytest.raises(Exception):
            MaxDisplacement(tag=1, node=2, dof="E", limit=0.1)


class TestInteractions:
    def test_hertzian(self):
        assert Hertzian(tag=1).to_commands() == ["interaction Hertzian 1"]

    def test_fixed_particle(self):
        assert FixedParticle(tag=2, multiplier=1e4, node_tags=[3]).to_commands() == [
            "interaction FixedParticle 2 10000 3"
        ]
