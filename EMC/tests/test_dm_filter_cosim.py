from dataclasses import replace

import numpy as np
import pytest
import skrf

from emc_sim.dm_filter_cosim import DMFilterAssumptions, cosimulate_dm_filter
from emc_sim.network_checks import NetworkCheckError


F = np.array([150e3, 1e6, 30e6])
BAND = (F[0], F[-1])
METADATA = {
    "solver_end_criteria_reached": True,
    "solver_status": "end_criteria_reached",
    "mesh_convergence": {"passed": True},
    "time_convergence": {"passed": True},
    "boundary_convergence": {"passed": True},
    "passivity": {"passed": True},
}


def network(s, frequencies=F, z0=50):
    return skrf.Network(frequency=skrf.Frequency.from_f(frequencies, unit="hz"),
                        s=np.broadcast_to(s, (len(frequencies), 2, 2)).copy(),
                        z0=z0, s_def="power")


def run(bypass, **overrides):
    args = {
        "run_metadata": METADATA,
        "candidate_export": "MAIN_OMRON/MCP_CANDIDATE_20261121_1753",
        "frequency_band_hz": BAND,
        "pre_post_polarity_confirmed": True,
    }
    args.update(overrides)
    return cosimulate_dm_filter(bypass, **args)


def expected_transfer(z_bypass, a):
    omega = 2 * np.pi * F
    z_choke = 2 * a.winding_resistance_ohm + 1j * omega * (
        2 * a.winding_inductance_h * (1 - a.coupling)
    )
    z_series = z_choke if z_bypass is None else z_choke * z_bypass / (z_choke + z_bypass)
    branch = z_series + a.load_resistance_ohm
    return a.load_resistance_ohm / (
        branch * (1 + a.source_resistance_ohm * 1j * omega * a.c2_f)
        + a.source_resistance_ohm
    )


def test_open_bypass_matches_analytic_input_shunt_and_choke():
    a = DMFilterAssumptions(source_resistance_ohm=17, load_resistance_ohm=130)
    result = run(network(np.eye(2)), assumptions=a)
    np.testing.assert_allclose(result.voltage_transfer, expected_transfer(None, a), rtol=1e-11)
    omega = 2 * np.pi * F
    z = 2 * a.winding_resistance_ohm + 1j * omega * 2 * a.winding_inductance_h * (1 - a.coupling)
    y = 1j * omega * a.c2_f
    den = 2 + z / 50 + 50 * y + y * z
    np.testing.assert_allclose(result.s[:, 0, 0], (z / 50 - 50 * y - y * z) / den, atol=1e-12)
    np.testing.assert_allclose(result.s[:, 1, 1], (z / 50 - 50 * y + y * z) / den, atol=1e-12)
    np.testing.assert_allclose(result.s[:, 1, 0], 2 / den, atol=1e-12)
    np.testing.assert_allclose(result.s[:, 0, 1], 2 / den, atol=1e-12)


@pytest.mark.parametrize("coupling", [0.95, 0.99, 0.999])
def test_finite_bypass_in_parallel_and_polarity(coupling):
    z_bypass = 200
    denominator = 100 + z_bypass
    s = np.array([[z_bypass, 100], [100, z_bypass]]) / denominator
    bypass = network(s)
    before = bypass.s.copy()
    a = DMFilterAssumptions(coupling=coupling, source_resistance_ohm=30,
                            load_resistance_ohm=80)
    result = run(bypass, assumptions=a)
    np.testing.assert_allclose(result.voltage_transfer, expected_transfer(z_bypass, a), rtol=1e-11)
    np.testing.assert_array_equal(bypass.s, before)
    assert result.voltage_transfer[0].imag < 0


def test_through_bypass_shorts_choke_but_not_input_capacitor():
    through = network([[0, 1], [1, 0]])
    a = DMFilterAssumptions(source_resistance_ohm=20, load_resistance_ohm=75)
    result = run(through, assumptions=a)
    expected = a.load_resistance_ohm / (
        a.source_resistance_ohm + a.load_resistance_ohm
        + 1j * 2 * np.pi * F * a.c2_f * a.source_resistance_ohm * a.load_resistance_ohm
    )
    np.testing.assert_allclose(result.voltage_transfer, expected, rtol=1e-11)
    assert "CY1" in result.limitation and "secondary" in result.limitation
    assert "NOT COMPLIANCE OR SAFETY PROOF" in result.stamp


def test_frequency_dependent_capacitive_bypass():
    z = 1 / (1j * 2 * np.pi * F * 15e-12)
    reflection = z / (100 + z)
    transmission = 100 / (100 + z)
    s = np.stack((reflection, transmission, transmission, reflection), axis=-1).reshape(-1, 2, 2)
    a = DMFilterAssumptions(source_resistance_ohm=65, load_resistance_ohm=200)
    result = run(network(s), assumptions=a)
    np.testing.assert_allclose(result.voltage_transfer, expected_transfer(z, a), rtol=1e-10)


def test_c2_is_on_input_not_output():
    result = run(network(np.eye(2)))
    assert np.max(np.abs(result.s[:, 0, 0] - result.s[:, 1, 1])) > 0.1
    no_cap = run(network(np.eye(2)), assumptions=replace(DMFilterAssumptions(), c2_f=0))
    np.testing.assert_allclose(no_cap.s[:, 0, 0], no_cap.s[:, 1, 1], atol=1e-12)
    assert result.s[0, 0, 0].imag < no_cap.s[0, 0, 0].imag


def test_matched_voltage_transfer_is_half_s21():
    result = run(network([[0.2, 0.6j], [0.6j, 0.2]]))
    np.testing.assert_allclose(result.voltage_transfer, result.s[:, 1, 0] / 2)


@pytest.mark.parametrize("gate", ["solver_end_criteria_reached", "mesh_convergence",
                                  "time_convergence", "boundary_convergence", "passivity"])
def test_rejects_missing_or_failed_evidence(gate):
    metadata = dict(METADATA)
    metadata.pop(gate)
    with pytest.raises(NetworkCheckError):
        run(network(np.eye(2)), run_metadata=metadata)


@pytest.mark.parametrize("bad_s, message", [
    ([[1.01, 0], [0, 1]], "passive"),
    ([[0, 0.2], [0.3, 0]], "reciprocal"),
    ([[np.nan, 0], [0, 0]], "non-finite"),
])
def test_rejects_invalid_bypass_network(bad_s, message):
    with pytest.raises(NetworkCheckError, match=message):
        run(network(bad_s))


def test_rejects_wrong_reference_frequencies_and_port_count():
    with pytest.raises(NetworkCheckError, match="50-ohm"):
        run(network(np.eye(2), z0=[50, 75]))
    with pytest.raises(NetworkCheckError, match="frequencies"):
        run(network(np.eye(2), frequencies=[150e3, 1e6, 2e6]))
    one_port = skrf.Network(frequency=skrf.Frequency.from_f(F, unit="hz"),
                            s=np.zeros((len(F), 1, 1)), z0=50)
    with pytest.raises(NetworkCheckError, match="two-port"):
        run(one_port)


@pytest.mark.parametrize("kwargs", [
    {"pre_post_polarity_confirmed": False},
    {"candidate_export": ""},
    {"frequency_band_hz": (0, 1e6)},
    {"assumptions": replace(DMFilterAssumptions(), coupling=1)},
    {"assumptions": replace(DMFilterAssumptions(), winding_resistance_ohm=-1)},
    {"assumptions": replace(DMFilterAssumptions(), source_resistance_ohm=0)},
    {"assumptions": replace(DMFilterAssumptions(), c2_f=float("nan"))},
])
def test_rejects_unjustified_inputs(kwargs):
    with pytest.raises(ValueError):
        run(network(np.eye(2)), **kwargs)
