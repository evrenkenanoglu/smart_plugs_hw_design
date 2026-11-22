import math
from types import SimpleNamespace

import pytest

from emc_sim.spice_conducted import (
    SpiceModelError,
    attenuation_db,
    assumed_lisn_branch_impedance,
    assumed_lisn_branch_poles,
    candidate_netlist,
    load_conducted_config,
    ngspice_version,
    passive_circuit_analysis,
    parallel_rl_impedance,
    run_ngspice,
)


@pytest.mark.parametrize(("frequency", "expected"), [
    (150000, complex(25.60611593, 22.43189887)),
    (1000000, complex(48.83998921, 7.13299026)),
    (30000000, complex(49.99867723, 0.24403043)),
])
def test_assumed_lisn_branch_impedance(frequency, expected):
    assert assumed_lisn_branch_impedance(frequency) == pytest.approx(expected, rel=1e-8)


def test_assumed_lisn_poles_are_real_and_stable():
    poles = assumed_lisn_branch_poles()
    assert [pole.real for pole in poles] == pytest.approx(
        [-1019041.57598, -80958.42402, -0.0001212121212], rel=1e-7
    )
    assert all(pole.imag == 0 for pole in poles)


def test_independent_mna_poles_and_response_match_parallel_rlc():
    netlist = """Parallel RLC
R1 lmeas 0 100
C1 lmeas 0 1u
L1 lmeas 0 1m
R2 nmeas 0 50
I1 lmeas 0 DC 0 AC 1u
.control
quit
.endc
.end
"""
    frequency = 5000
    result = passive_circuit_analysis(netlist, [frequency])
    poles = result["poles"]
    assert len(poles) == 2
    assert sorted(pole["real_rad_s"] for pole in poles) == pytest.approx([-5000, -5000])
    expected_imag = math.sqrt(1 / (1e-3 * 1e-6) - 5000**2)
    assert sorted(pole["imag_rad_s"] for pole in poles) == pytest.approx([-expected_imag, expected_imag])
    admittance = 1 / 100 + 2j * math.pi * frequency * 1e-6 + 1 / (2j * math.pi * frequency * 1e-3)
    assert result["responses"][0][0] == pytest.approx(-1e-6 / admittance)
    assert result["responses"][0][1] == 0
    assert result["max_eigen_residual"] < 1e-8


def test_mna_rejects_nonpassive_mutual_inductance():
    netlist = candidate_netlist("dm", .99, 80, [150000, 30000000])
    with pytest.raises(SpiceModelError, match="mutual coupling"):
        passive_circuit_analysis(netlist.replace("Kchoke Lwl Lwn 0.99", "Kchoke Lwl Lwn 1.1"), [1e6])


def test_candidate_full_circuit_modes_survive_descriptor_rescaling():
    netlist = candidate_netlist("dm", .99, 80, [150000, 30000000])
    first = passive_circuit_analysis(netlist, [])
    second = passive_circuit_analysis(netlist, [], reference_ohm=100, reference_hz=100000)
    modes = [p for p in first["poles"] if p["imag_rad_s"] > 0]
    comparison = [p for p in second["poles"] if p["imag_rad_s"] > 0]
    assert [p["oscillation_hz"] for p in modes] == pytest.approx([47844.345, 227551.309], rel=1e-6)
    assert [p["imag_rad_s"] for p in modes] == pytest.approx([p["imag_rad_s"] for p in comparison], rel=1e-8)
    assert all(p["real_rad_s"] < 0 for p in modes)


def test_attenuation_uses_bypass_over_filtered_per_conductor():
    filtered = [[1000, 1, 0, 0, 2]]
    bypass = [[1000, 10, 0, 0, 1]]
    assert attenuation_db(filtered, bypass, 1) == pytest.approx([20])
    assert attenuation_db(filtered, bypass, 3) == pytest.approx([-6.020599913])


@pytest.mark.parametrize("bypass", [[], [[1001, 1, 0, 1, 0]], [[1000, 0, 0, 1, 0]]])
def test_attenuation_rejects_mismatched_or_undefined_reference(bypass):
    with pytest.raises(SpiceModelError):
        attenuation_db([[1000, 1, 0, 1, 0]], bypass, 1)


def test_candidate_model_source_and_choke_orientation():
    dm = candidate_netlist("dm", 0.99, 80, [150000, 30000000])
    cm = candidate_netlist("cm", 0.99, 80, [150000, 30000000])
    assert "Idm outl outn DC 0 AC 1u" in dm
    assert "Icm1 outl 0 DC 0 AC 1u" in cm and "Icm2 outn 0 DC 0 AC 1u" in cm
    assert "Lwl il outl 10m" in dm and "Lwn isn in 10m" in dm
    assert "Ccy secondary1 secondary2 2.2n" in dm
    assert "Ccy secondary1 0" not in dm


def test_candidate_bypass_removes_filter_but_keeps_source_and_reference_network():
    bypass = candidate_netlist("dm", 0.99, 80, [150000, 30000000], bypass=True)
    assert "Rthroughl ntc outl 1m" in bypass
    assert "Rthroughn isn outn 1m" in bypass
    assert "Kchoke" not in bypass and "\nC2 " not in bypass and "\nCrv " not in bypass
    assert "Idm outl outn DC 0 AC 1u" in bypass
    assert "Rlrecv lmeas 0 50" in bypass


@pytest.mark.parametrize("mode,coupling", [("unknown", .99), ("dm", 1), ("cm", 0)])
def test_candidate_model_rejects_invalid_inputs(mode, coupling):
    with pytest.raises(SpiceModelError):
        candidate_netlist(mode, coupling, 80, [150000, 30000000])


def test_parallel_rl_impedance_matches_analytic_admittance():
    frequency = 1e6
    inductance = 50e-6
    resistance = 50.0
    impedance = parallel_rl_impedance(frequency, inductance, resistance)
    expected = 1.0 / (1.0 / resistance + 1.0 / complex(0, 2 * math.pi * frequency * inductance))
    assert impedance == pytest.approx(expected)
    assert impedance.real > 0
    assert impedance.imag > 0


@pytest.mark.parametrize("values", [(0, 1e-6, 50), (1e6, 0, 50), (1e6, 1e-6, -1)])
def test_parallel_rl_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        parallel_rl_impedance(*values)


def test_parallel_rl_rejects_overflowing_intermediate_values():
    with pytest.raises(ValueError, match="reactance"):
        parallel_rl_impedance(1e308, 1e308, 50.0)


def test_config_fails_closed_on_missing_network_provenance(tmp_path):
    (tmp_path / "model.cir").write_text("* empty model\n", encoding="utf-8")
    (tmp_path / "model.yaml").write_text(
        "netlist: model.cir\n"
        "source:\n"
        "  provenance: assumed illustrative source\n"
        "measurement_network:\n"
        "  status: TODO_VERIFY_FROM_STAGE_0\n"
        "  provenance: null\n"
        "frequency_band_hz: [150000, 30000000]\n",
        encoding="utf-8",
    )
    with pytest.raises(SpiceModelError, match="provenance"):
        load_conducted_config(tmp_path / "model.yaml")


def test_ngspice_missing_binary_does_not_create_success_data(tmp_path):
    netlist = tmp_path / "model.cir"
    netlist.write_text("* test\n", encoding="utf-8")
    with pytest.raises(SpiceModelError, match="not found"):
        run_ngspice(netlist, tmp_path / "run", executable="missing-ngspice-test")
    assert not (tmp_path / "run").exists()


def test_ngspice_version_is_reported_without_shell(monkeypatch):
    monkeypatch.setattr(
        "emc_sim.spice_conducted.shutil.which", lambda _: "ngspice.exe"
    )
    command = []

    def fake_run(args, **kwargs):
        command.extend(args)
        return SimpleNamespace(returncode=0, stdout="ngspice-45\n", stderr="")

    monkeypatch.setattr(
        "emc_sim.spice_conducted.subprocess.run",
        fake_run,
    )

    assert ngspice_version() == "ngspice-45"
    assert command == ["ngspice.exe", "-v"]


def test_ngspice_version_selects_console_binary_and_banner(monkeypatch):
    monkeypatch.setattr("emc_sim.spice_conducted.shutil.which",
                        lambda _: r"C:\tools\ngspice.exe")
    monkeypatch.setattr("emc_sim.spice_conducted.Path.is_file", lambda _: True)
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="******\n** ngspice-47 : Circuit level simulation\n", stderr="")

    monkeypatch.setattr("emc_sim.spice_conducted.subprocess.run", fake_run)
    assert ngspice_version() == "ngspice-47 : Circuit level simulation"
    assert calls[0][0].lower().endswith("ngspice_con.exe")


def test_ngspice_version_fails_if_executable_is_missing(monkeypatch):
    monkeypatch.setattr("emc_sim.spice_conducted.shutil.which", lambda _: None)

    with pytest.raises(SpiceModelError, match="not found"):
        ngspice_version()
