from types import SimpleNamespace

import pytest

from emc_sim import network_checks
from emc_sim.network_checks import (
    NetworkCheckError,
    check_passivity,
    check_reciprocity,
    load_touchstone,
    maximum_singular_values,
    require_converged_run,
    validate_finite_values,
)


@pytest.fixture
def converged_metadata():
    return {
        "solver_end_criteria_reached": True,
        "mesh_convergence": {"passed": True},
    }


def make_network(s):
    numpy = pytest.importorskip("numpy")
    return SimpleNamespace(s=numpy.asarray(s), s_def="power")


def test_load_touchstone_uses_scikit_rf_network(monkeypatch):
    expected_network = object()
    calls = []

    def fake_import(module_name):
        assert module_name == "skrf"
        return SimpleNamespace(
            Network=lambda path: calls.append(path) or expected_network
        )

    monkeypatch.setattr(network_checks, "import_module", fake_import)

    assert load_touchstone("model.s2p") is expected_network
    assert calls == ["model.s2p"]


def test_load_touchstone_reads_a_real_power_wave_network(
    tmp_path, converged_metadata
):
    pytest.importorskip("skrf")
    touchstone = tmp_path / "lossless_through.s2p"
    touchstone.write_text(
        "# GHz S RI R 50\n"
        "0.1 0 0 1 0 1 0 0 0\n"
        "0.2 0 0 1 0 1 0 0 0\n",
        encoding="ascii",
    )

    network = load_touchstone(touchstone)

    assert network.s_def == "power"
    assert check_passivity(network, run_metadata=converged_metadata)
    assert check_reciprocity(network, run_metadata=converged_metadata)


def test_passivity_uses_maximum_singular_value(converged_metadata):
    # A lossless through has two unit-magnitude terms, but each singular value
    # is one; summing |Sij|^2 would incorrectly classify it as active.
    through = make_network([[[0.0, 1.0], [1.0, 0.0]]])

    assert maximum_singular_values(through, run_metadata=converged_metadata) == pytest.approx(
        (1.0,)
    )
    assert check_passivity(through, run_metadata=converged_metadata)


def test_active_network_fails_passivity_check(converged_metadata):
    active = make_network([[[1.01 + 0j]]])

    assert not check_passivity(active, run_metadata=converged_metadata)
    assert check_passivity(
        active, run_metadata=converged_metadata, tolerance=0.02
    )


def test_reciprocal_and_nonreciprocal_networks(converged_metadata):
    reciprocal = make_network([[[0.1, 0.4j], [0.4j, 0.2]]])
    nonreciprocal = make_network([[[0.0, 0.0, 1.0],
                                   [1.0, 0.0, 0.0],
                                   [0.0, 1.0, 0.0]]])

    assert check_reciprocity(reciprocal, run_metadata=converged_metadata)
    assert not check_reciprocity(nonreciprocal, run_metadata=converged_metadata)


def test_reciprocity_tolerance_is_absolute(converged_metadata):
    slightly_asymmetric = make_network([[[0.0, 0.0005], [0.0, 0.0]]])

    assert check_reciprocity(
        slightly_asymmetric, run_metadata=converged_metadata, tolerance=0.001
    )
    assert not check_reciprocity(
        slightly_asymmetric, run_metadata=converged_metadata, tolerance=0.0001
    )


def test_nonfinite_s_parameters_are_rejected(converged_metadata):
    nonfinite = make_network([[[complex(float("nan"), 0.0)]]])

    with pytest.raises(NetworkCheckError, match="non-finite"):
        validate_finite_values(nonfinite, run_metadata=converged_metadata)


@pytest.mark.parametrize(
    "metadata",
    [
        {"solver_end_criteria_reached": False, "mesh_convergence": {"passed": True}},
        {"solver_end_criteria_reached": True, "mesh_convergence": {"passed": False}},
        {"solver_end_criteria_reached": True},
    ],
)
def test_unconverged_run_is_rejected(metadata):
    with pytest.raises(NetworkCheckError):
        require_converged_run(metadata)


def test_network_processing_requires_converged_run():
    network = make_network([[[0.0]]])

    with pytest.raises(NetworkCheckError, match="solver_end_criteria_reached"):
        check_passivity(
            network,
            run_metadata={
                "solver_end_criteria_reached": False,
                "mesh_convergence": {"passed": True},
            },
        )


@pytest.mark.parametrize("tolerance", [-1.0, float("nan"), float("inf"), True])
def test_tolerance_must_be_finite_nonnegative_and_not_boolean(
    converged_metadata, tolerance
):
    network = make_network([[[0.0]]])

    with pytest.raises(ValueError, match="tolerance"):
        check_passivity(
            network, run_metadata=converged_metadata, tolerance=tolerance
        )


def test_missing_scikit_rf_has_clear_error(monkeypatch):
    def fail_import(module_name):
        if module_name == "skrf":
            raise ModuleNotFoundError("skrf")
        raise AssertionError(f"Unexpected optional import: {module_name}")

    monkeypatch.setattr(network_checks, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="scikit-rf"):
        load_touchstone("model.s2p")


def test_missing_numpy_has_clear_error(monkeypatch, converged_metadata):
    def fail_import(module_name):
        if module_name == "numpy":
            raise ModuleNotFoundError("numpy")
        raise AssertionError(f"Unexpected optional import: {module_name}")

    monkeypatch.setattr(network_checks, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="NumPy"):
        validate_finite_values(
            SimpleNamespace(s=[[[0.0]]], s_def="power"),
            run_metadata=converged_metadata,
        )
