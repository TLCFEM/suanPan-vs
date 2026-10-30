"""Tests of the generated + hand written material classes."""

import pytest

from suanpan.material import (
    CDPM2,
    OS146,
    Balloon,
    Balloon1D,
    Bilinear1D,
    BilinearHoffman,
    BilinearTsaiWu,
    ConcreteK4,
    CustomElastic1D,
    Elastic1D,
    Elastic3D,
    Laminated,
    MultilinearElastic1D,
    MultiSubloading1D,
    Parallel,
    PlaneStrain,
    Uniaxial,
)


class TestElastic:
    def test_elastic1d(self):
        # C++: tag, elastic_modulus, density(0)
        assert Elastic1D(tag=1, elastic_modulus=2e5).to_commands() == [
            "Elastic1D 1 200000"
        ]
        assert Elastic1D(tag=1, elastic_modulus=2e5, density=7850).to_commands() == [
            "Elastic1D 1 200000 7850"
        ]

    def test_elastic3d_alias(self):
        # Elastic3D == IsotropicElastic3D in the dispatch table
        assert Elastic3D(
            tag=2, elastic_modulus=1e4, poissons_ratio=0.3
        ).to_commands() == ["Elastic3D 2 10000 0.3"]

    def test_custom_elastic1d(self):
        # C++: tag, expression_tag, density(0)
        assert CustomElastic1D(tag=1, expression_tag=2).to_commands() == [
            "CustomElastic1D 1 2"
        ]


class TestBilinear:
    def test_bilinear1d_full(self):
        # example file: `material Bilinear1D 1 100 5 .2`
        assert Bilinear1D(
            tag=1, elastic_modulus=100, yield_stress=5, hardening_ratio=0.2
        ).to_commands() == ["Bilinear1D 1 100 5 0.2"]

    def test_bilinear1d_beta_and_density(self):
        obj = Bilinear1D(
            tag=1,
            elastic_modulus=100,
            yield_stress=5,
            hardening_ratio=0.2,
            beta=0.8,
            density=1.5,
        )
        assert obj.to_commands() == ["Bilinear1D 1 100 5 0.2 0.8 1.5"]

    def test_orthotropic_flavours(self):
        # the C++ dispatcher has no `BilinearOrthotropic` keyword: the
        # orthotropic handler is reached via the Hoffman / TsaiWu spellings
        assert BilinearHoffman.keyword == "BilinearHoffman"
        assert BilinearTsaiWu.keyword == "BilinearTsaiWu"
        assert BilinearHoffman.model_fields.keys() == BilinearTsaiWu.model_fields.keys()


class TestWrappers:
    def test_uniaxial(self):
        assert Uniaxial(tag=3, full_tag=1, max_iteration=5).to_commands() == [
            "Uniaxial 3 1 5"
        ]

    def test_os146(self):
        # max_iteration is optional (default one) and trailing -> trimmed
        assert OS146(tag=4, full_tag=2).to_commands() == ["OS146 4 2"]
        assert OS146(tag=4, full_tag=2, max_iteration=5).to_commands() == [
            "OS146 4 2 5"
        ]

    def test_parallel(self):
        assert Parallel(tag=1, object_tags=[1, 2, 3]).to_commands() == [
            "Parallel 1 1 2 3"
        ]

    def test_laminated(self):
        assert Laminated(tag=1, object_tags=[4, 5]).to_commands() == ["Laminated 1 4 5"]

    def test_plane_strain(self):
        assert PlaneStrain(tag=1, full_tag=7).to_commands() == ["PlaneStrain 1 7"]


class TestMultilinear:
    def test_strain_stress_pairs(self):
        obj = MultilinearElastic1D(tag=1, rest_values=[0, 0, 0.002, 400])
        assert obj.to_commands() == ["MultilinearElastic1D 1 0 0 0.002 400"]


class TestSpecials:
    def test_balloon(self):
        obj = Balloon(
            tag=1, p=[1.0] * 24, density=1.0, bfc=[{"a": 1, "b": 2}], memory="maximum"
        )
        tokens = obj.to_commands()[0].split()
        assert tokens[0] == "material" and tokens[1] == "Balloon"
        assert tokens[-5:] == ["-fc", "1", "2", "-memory", "maximum"]
        assert len(tokens) == 2 + 1 + 24 + 1 + 5

    def test_balloon1d_23_values(self):
        with pytest.raises(Exception):
            Balloon1D(tag=1, p=[1.0] * 24, density=1.0)
        obj = Balloon1D(tag=1, p=[2.0] * 23, density=7.85)
        assert obj.to_commands() == [
            " ".join(["material", "Balloon1D", "1", *("2" for _ in range(23)), "7.85"])
        ]

    def test_concrete_k4(self):
        # trailing boolean trio exported as one group
        obj = ConcreteK4(tag=1, elastic_modulus=2e4, hardening=0.1, pool=[1.0] * 8)
        assert obj.to_commands() == [
            "material ConcreteK4 1 20000 0.1 " + " ".join("1" for _ in range(8))
        ]
        obj = ConcreteK4(
            tag=1,
            elastic_modulus=2e4,
            hardening=0.1,
            pool=[1.0] * 8,
            objective_damage=True,
        )
        assert obj.to_commands()[-1].endswith("true true true")

    def test_multisubloading1d(self):
        obj = MultiSubloading1D(
            tag=1,
            parameters=[1.0] * 11,
            back=[{"a": 1, "b": 2}],
            core=[{"a": 3, "b": 4}],
        )
        assert obj.to_commands() == [
            "material MultiSubloading1D 1 "
            + " ".join("1" for _ in range(11))
            + " -back 1 2 -core 3 4"
        ]

    def test_multisubloading_requires_11(self):
        with pytest.raises(Exception):
            MultiSubloading1D(tag=1, parameters=[1.0] * 10)


class TestCDPM2:
    def test_default_pool_omitted(self):
        # the optional 15 value pool re-parses to the C++ default when omitted
        assert CDPM2(tag=1).to_commands() == ["CDPM2 1"]

    def test_pool_exported_when_given(self):
        pool = [
            3e4,
            0.3,
            3.0,
            30.0,
            0.3,
            0.01,
            0.85,
            0.08,
            0.003,
            2.0,
            1e-6,
            5.0,
            5e-4,
            5e-4,
            0.5,
        ]
        obj = CDPM2(tag=1, para_pool=pool)
        tokens = obj.to_commands()[0].split()
        assert tokens[0] == "CDPM2" and tokens[1] == "1" and len(tokens) == 2 + 15

    def test_aniso_spelling(self):
        from suanpan.material import CDPM2ANISO, CDPM2NO

        assert CDPM2ANISO.keyword == "CDPM2ANISO"
        assert CDPM2NO.keyword == "CDPM2NO"
