import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from emc_sim.gerber_import import BoardGeometry, LayerGeometry


path = Path(__file__).resolve().parents[1] / "smart_power_strip" / "workflows" / "03_local_pcb_em_extract.py"
spec = importlib.util.spec_from_file_location("local_pcb_em_extract", path)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


def test_mesh_grading_rejects_abrupt_or_invalid_transitions():
    workflow._check_mesh_grading([0, 1, 2.4, 3.8])
    with pytest.raises(RuntimeError, match="grading"):
        workflow._check_mesh_grading([0, 1, 3])
    with pytest.raises(RuntimeError, match="strictly increasing"):
        workflow._check_mesh_grading([0, 1, 1])


def test_graded_axis_preserves_close_anchors_and_limits_growth():
    anchors = [0, .001, .001002, .003, .005]
    lines = workflow._graded_axis(anchors, .001)
    workflow._check_mesh_grading(lines)
    assert all(any(abs(line - anchor) < 1e-12 for line in lines) for anchor in anchors)
    assert max(b - a for a, b in zip(lines, lines[1:])) <= .001


def test_shared_center_lines_require_all_barrel_sides_sampled():
    centers = workflow._cluster_hole_centers([0, 13e-6, .001])
    assert centers == [6.5e-6, .001]
    holes = [(0., 0., .001)]
    lines = [-.0010125, 0., .0010125]
    workflow._validate_barrel_mesh(holes, lines, lines)
    with pytest.raises(RuntimeError, match="unsampled cardinal"):
        workflow._validate_barrel_mesh(holes, [-.0010125, 0., .0011], lines)


def test_candidate_sweep_covers_requested_band():
    frequencies = workflow._candidate_frequencies()
    assert len(frequencies) == 81
    assert frequencies[0] == 30e6
    assert frequencies[-1] == 1e9
    assert np.all(np.diff(frequencies) > 0)
    assert np.allclose(frequencies[1:] / frequencies[:-1],
                       frequencies[1] / frequencies[0])


def test_network_release_requires_independent_boundary_gate():
    metadata = {
        "solver_end_criteria_reached": True,
        "solver_status": "end_criteria_reached",
        "mesh_convergence": {"passed": True},
        "time_convergence": {"passed": True},
        "passivity": {"passed": True},
        "reciprocity": {"passed": True},
        "boundary_convergence": {"passed": False},
    }
    with pytest.raises(RuntimeError, match="boundary_convergence"):
        workflow._require_release_gates(metadata)
    metadata["boundary_convergence"]["passed"] = True
    workflow._require_release_gates(metadata)
    metadata["time_convergence"]["passed"] = False
    with pytest.raises(RuntimeError, match="time_convergence"):
        workflow._require_release_gates(metadata)
    metadata["time_convergence"]["passed"] = True
    metadata["reciprocity"]["passed"] = False
    with pytest.raises(RuntimeError, match="reciprocity"):
        workflow._require_release_gates(metadata)


def test_boundary_convergence_requires_each_independent_axis():
    reference = np.ones((3, 2, 2), dtype=complex)
    expanded = {name: reference.copy() for name in ("expanded_x", "expanded_y", "expanded_z")}
    assert workflow._boundary_convergence(reference, expanded)["passed"]
    expanded["expanded_y"][0, 0, 1] = 1.1
    result = workflow._boundary_convergence(reference, expanded)
    assert not result["passed"]
    assert result["maximum_relative_changes"]["expanded_y"] > .05
    del expanded["expanded_z"]
    with pytest.raises(ValueError, match="boundary sensitivity"):
        workflow._boundary_convergence(reference, expanded)


def test_pec_edge_audit_detects_missing_copper_edge(monkeypatch):
    class Grid:
        def find(self, name):
            return SimpleNamespace(text="0,1,2")

    monkeypatch.setattr(workflow.ET, "parse", lambda path: SimpleNamespace(find=lambda name: Grid()))
    points = np.array([[0, 1, 0], [1, 1, 0], [1, 0, 0], [1, 2, 0]], dtype=float)
    lines = np.array([[0, 1], [2, 1], [1, 3]])
    monkeypatch.setattr(workflow, "_read_pec_dump", lambda path: (points, lines))
    layer = LayerGeometry("Top", 0, 1e-6, box(.1, .1, 1.9, 1.9), None, 1e-6)
    result = workflow._audit_pec_edges(BoardGeometry((layer,), None, 1e-6),
                                       Path("unused-geometry"), Path("unused-pec"))
    assert result["layers"]["Top"]["x"]["missing_expected_midpoints"] == 1
    assert result["layers"]["Top"]["y"]["missing_expected_midpoints"] == 0


def test_barrel_audit_detects_missing_pec_segment(monkeypatch):
    class Grid:
        def find(self, name):
            return SimpleNamespace(text="0,0.0016" if name == "ZLines"
                                   else "-0.0010125,0,0.0010125")

    monkeypatch.setattr(workflow.ET, "parse", lambda path: SimpleNamespace(find=lambda name: Grid()))
    cardinal = [(-.0010125, 0), (.0010125, 0), (0, -.0010125), (0, .0010125)]
    points = np.array([[x, y, z] for x, y in cardinal for z in (0, .0016)])
    lines = np.array([[0, 1], [2, 3], [4, 5]])
    monkeypatch.setattr(workflow, "_read_pec_dump", lambda path: (points, lines))
    result = workflow._audit_barrel_edges([(0, 0, .001)], Path("unused-geometry"), Path("unused-pec"))
    assert result["expected_segments"] == 4
    assert result["missing_segments"] == 1


def test_pec_fidelity_gate_rejects_missing_or_unexpected_edges():
    def layer():
        return {axis: {"expected_copper_midpoints": 1, "missing_expected_midpoints": 0,
                       "extra_outside_port_boxes": 0} for axis in ("x", "y")}

    diagnostic = {
        "pec_edge_audit": {"layers": {"Top": layer(), "Bottom": layer()}},
        "barrel_edge_audit": {"expected_segments": 4, "missing_segments": 0},
    }
    workflow._require_pec_fidelity(diagnostic)
    diagnostic["pec_edge_audit"]["layers"]["Top"]["x"]["missing_expected_midpoints"] = 1
    with pytest.raises(RuntimeError, match="Top/x"):
        workflow._require_pec_fidelity(diagnostic)
    diagnostic["pec_edge_audit"]["layers"]["Top"]["x"]["missing_expected_midpoints"] = 0
    diagnostic["barrel_edge_audit"]["missing_segments"] = 1
    with pytest.raises(RuntimeError, match="barrel"):
        workflow._require_pec_fidelity(diagnostic)


def test_candidate_cli_verifies_manifest_and_attempts_full_solve(monkeypatch):
    observed = {}
    monkeypatch.setattr(sys, "argv", ["03_local_pcb_em_extract.py", "--allow-candidate"])

    def verify(path, **kwargs):
        observed["verify"] = path, kwargs
        return {"locked": False}

    def run(args, app_root, input_root):
        observed["run"] = args, app_root, input_root
        return 1

    monkeypatch.setattr(workflow, "verify_manifest", verify)
    monkeypatch.setattr(workflow, "run_candidate", run)
    assert workflow.main() == 1
    args, root, input_root = observed["run"]
    assert observed["verify"] == (root / "configs" / "revision_manifest.json",
                                  {"allow_candidate": True, "input_root": root})
    assert input_root == root / "inputs" / "locked_rev"
    assert args.layer_map == root / "configs" / "layer_map.json"
    assert args.stackup == root / "configs" / "stackup.json"
    assert args.diagnostic_steps is None


@pytest.mark.parametrize("arguments", [[], ["--allow-candidate"]])
def test_manifest_failure_blocks_both_modes(monkeypatch, arguments):
    observed = {}
    monkeypatch.setattr(sys, "argv", ["03_local_pcb_em_extract.py", *arguments])

    def reject(path, **kwargs):
        observed.update(kwargs)
        raise ValueError("manifest hash mismatch or unlocked")

    monkeypatch.setattr(workflow, "verify_manifest", reject)
    monkeypatch.setattr(workflow, "run_candidate",
                        lambda *args: pytest.fail("unverified candidate was run"))
    with pytest.raises(SystemExit) as exc:
        workflow.main()
    assert exc.value.code == 2
    assert observed.get("allow_candidate", False) is bool(arguments)


def test_candidate_does_not_swallow_programmer_error(monkeypatch):
    import matplotlib.pyplot as plt

    root = Path(__file__).resolve().parents[1] / "smart_power_strip"
    args = SimpleNamespace(layer_map=root / "configs" / "layer_map.json",
                           stackup=root / "configs" / "stackup.json",
                           manifest=root / "configs" / "revision_manifest.json",
                           diagnostic_steps=1000)
    configuration = SimpleNamespace(gerber_sources={}, drill_sources=())
    board = SimpleNamespace(crop_bbox_m=(0, 0, 1, 1))
    monkeypatch.setattr(workflow, "validate_layer_configuration", lambda *a, **k: configuration)
    monkeypatch.setattr(workflow, "_validate_candidate_configuration", lambda *a: None)
    monkeypatch.setattr(workflow, "_healed_candidate_board",
                        lambda *a: (board, board, (), (), {}))
    monkeypatch.setattr(workflow, "_with_port_fixtures", lambda b: b)
    monkeypatch.setattr(workflow, "create_run_directory", lambda *a: root / "unused-test-run")
    monkeypatch.setattr(workflow.shutil, "copy2", lambda *a: None)
    monkeypatch.setattr(workflow, "sha256_file", lambda *a: "0" * 64)
    monkeypatch.setattr(workflow, "write_run_metadata", lambda *a, **k: None)
    monkeypatch.setattr(workflow, "write_report", lambda *a, **k: None)
    monkeypatch.setattr(plt, "subplots", lambda *a, **k: (_ for _ in ()).throw(KeyError("bug")))
    with pytest.raises(KeyError, match="bug"):
        workflow.run_candidate(args, root, root / "inputs" / "locked_rev")


def test_constrained_copper_conversion_preserves_cutout():
    class Metal:
        def __init__(self):
            self.polygons = []

        def AddPolygon(self, coordinates, **kwargs):
            self.polygons.append(Polygon(zip(*coordinates)))

    class CSX:
        def __init__(self):
            self.metal = Metal()

        def AddMetal(self, name):
            return self.metal

    copper = box(0, 0, 4, 4).difference(box(1, 1, 3, 3))
    layer = LayerGeometry("Top", 0, 1e-6, copper, None, 1e-6)
    board = BoardGeometry((layer,), None, 1e-6)
    csx = CSX()
    workflow._add_candidate_copper(csx, board)
    assert unary_union(csx.metal.polygons).symmetric_difference(copper).area < 1e-12


def test_copper_partition_preserves_multiple_cutouts():
    class Metal:
        def __init__(self):
            self.polygons = []

        def AddPolygon(self, coordinates, **kwargs):
            self.polygons.append(Polygon(zip(*coordinates)))

    class CSX:
        def __init__(self):
            self.metal = Metal()

        def AddMetal(self, name):
            return self.metal

    copper = box(0, 0, 10, 5).difference(
        unary_union([box(1, 1, 2, 2), box(4, 1, 5, 2), box(7, 3, 8, 4)])
    )
    board = BoardGeometry((LayerGeometry("Top", 0, 1e-6, copper, None, 1e-6),), None, 1e-6)
    csx = CSX()
    workflow._add_candidate_copper(csx, board)
    assert all(not part.interiors for part in csx.metal.polygons)
    assert unary_union(csx.metal.polygons).symmetric_difference(copper).area < 1e-12


def test_candidate_port_mapping_rejects_unrelated_crossing():
    root = Path(__file__).resolve().parents[1] / "smart_power_strip"
    configs = root / "configs"
    input_root = root / "inputs" / "locked_rev"
    configuration = workflow.validate_layer_configuration(
        json.loads((configs / "layer_map.json").read_text()),
        json.loads((configs / "stackup.json").read_text()),
        base_directory=input_root, allow_candidate=True,
    )
    board = workflow._candidate_board(configuration)
    probe = input_root / "MAIN_OMRON" / "MCP_CANDIDATE_20261121_1753" / "gerbers" / "FlyingProbeTesting.json"
    holes = workflow._round_plated_holes(board)
    board = workflow._with_port_fixtures(board)
    workflow._validate_port_geometry(board, probe, holes)
    with pytest.raises(workflow.GerberImportError, match="not connected"):
        workflow._validate_port_geometry(board, probe, ())
    top = board.layer("Top")
    obstruction = box(.025, -.0925, .0251, -.0923)
    modified = replace(top, geometry=top.geometry.union(obstruction))
    changed = replace(board, layers=tuple(modified if layer.name == "Top" else layer for layer in board.layers))
    with pytest.raises(workflow.GerberImportError, match="crosses an unrelated"):
        workflow._validate_port_geometry(changed, probe, holes)


def test_healed_crop_preserves_candidate_port_connectivity():
    root = Path(__file__).resolve().parents[1] / "smart_power_strip"
    configs = root / "configs"
    input_root = root / "inputs" / "locked_rev"
    configuration = workflow.validate_layer_configuration(
        json.loads((configs / "layer_map.json").read_text()),
        json.loads((configs / "stackup.json").read_text()),
        base_directory=input_root, allow_candidate=True,
    )
    original, healed, holes, squares, metrics = workflow._healed_candidate_board(configuration)
    probe = input_root / "MAIN_OMRON" / "MCP_CANDIDATE_20261121_1753" / "gerbers" / "FlyingProbeTesting.json"
    for board in (original, healed):
        workflow._validate_port_geometry(workflow._with_port_fixtures(board), probe, holes)
    assert len(squares) == len(holes) == 6
    assert all(value["islands_before"] == value["islands_after"] for value in metrics.values())


def test_healed_mesh_has_graded_air_and_minimum_xy_cell():
    for spacing in (.0004, .0002):
        lines = workflow._healed_axis(.016, .042, spacing, .0152)
        workflow._check_mesh_grading(lines)
        assert np.min(np.diff(lines)) >= spacing - 1e-12
        assert lines[8] <= .016 - .003
        assert lines[-9] >= .042 + .003


def test_energy_bound_accounts_for_initial_peak_missing_from_wall_clock_samples(tmp_path):
    samples = tmp_path / "openEMS_run_stats.txt"
    samples.write_text("% time timestep speed energy\n4 1485 1 3.03e-16\n52 20240 1 8.93e-19\n")
    log = ("Timestep: 1485 || Energy: ~3.03e-16 (-15.22dB)\n"
           "Timestep: 20240 || Energy: ~8.93e-19 (-40.52dB)\n"
           "end-criteria of -40.00dB reached after 20240 timesteps (-40.52dB)\n")
    upper = workflow._energy_upper_bound(log, samples, 20240, 1e-4)
    assert 8.8e-5 < upper < 1e-4
    assert 8.93e-19 / 3.03e-16 > 1e-4
    with pytest.raises(RuntimeError, match="disagree"):
        workflow._energy_upper_bound(log.replace("1485", "1486"), samples, 20240, 1e-4)
    with pytest.raises(RuntimeError, match="marker"):
        workflow._energy_upper_bound(log.replace("-40.52dB", "-39.52dB"), samples, 20240, 1e-4)
    with pytest.raises(RuntimeError, match="marker"):
        workflow._energy_upper_bound(log.split("end-criteria")[0], samples, 20240, 1e-4)
    with pytest.raises(RuntimeError, match="final sample"):
        workflow._energy_upper_bound(log, samples, 20241, 1e-4)
    samples.write_text("% time timestep speed energy\n4 1485 1 nan\n")
    with pytest.raises(RuntimeError, match="Invalid"):
        workflow._energy_upper_bound(log, samples, 20240, 1e-4)


def test_pulse_spectrum_validation_uses_source_scale_not_absolute_dft_units():
    incident = np.array([8e-13, 9e-13])
    voltage = 2 * incident
    current = np.zeros(2)
    source = np.full(2, 4e-8)
    length = .006
    result = workflow._validate_incident_spectrum(incident, voltage, current, source, length)
    assert result["minimum_relative_band_amplitude"] > .8
    assert result["minimum_incident_to_nominal_source_voltage_spectrum"] == pytest.approx(
        8e-13 / (4e-8 * length))
    with pytest.raises(RuntimeError, match="weak"):
        workflow._validate_incident_spectrum(incident * 1e-3, voltage, current, source, length)
    with pytest.raises(RuntimeError, match="weak"):
        workflow._validate_incident_spectrum(np.array([1e-15, 1e-12]), voltage, current, source, length)
    with pytest.raises(RuntimeError, match="ill-conditioned"):
        workflow._validate_incident_spectrum(incident, incident * 1e5, current, source, length)
    with pytest.raises(RuntimeError, match="invalid"):
        workflow._validate_incident_spectrum(incident * np.nan, voltage, current, source, length)
    with pytest.raises(ValueError, match="Source length"):
        workflow._validate_incident_spectrum(incident, voltage, current, source, 0)


def test_failed_mesh_comparison_saves_only_diagnostic_plot(tmp_path):
    matrices = [np.ones((2, 2, 2), dtype=complex) for _ in range(3)]
    matrices[1][:, 0, 1] = .8
    changes = workflow._mesh_convergence_diagnostic(
        np.array([30e6, 1e9]), matrices, tmp_path / "mesh.png")
    assert changes == pytest.approx([.2, .2, 0])
    assert (tmp_path / "mesh.png").is_file()
    assert not list(tmp_path.glob("*.s2p"))


def test_network_wave_assembly_accounts_for_unexcited_port_incident_waves():
    incident = np.array([[[1, .2], [.1, 1]], [[2, -.1j], [.3, 1]]], dtype=complex)
    expected = np.array([[[.1, .25j], [.25j, -.2]], [[.2, .4], [.4, .3]]])
    reflected = expected @ incident
    excitations = [np.stack((incident[:, :, i], reflected[:, :, i]), axis=1)
                   for i in range(2)]
    assert workflow._assemble_network_waves(excitations) == pytest.approx(expected)
    singular = [np.ones((2, 2, 2)), np.ones((2, 2, 2))]
    with pytest.raises(RuntimeError, match="singular or ill-conditioned"):
        workflow._assemble_network_waves(singular)
    ill_conditioned_incident = np.array([[[1, 1], [1, 1.0001]]], dtype=complex)
    ill_conditioned_waves = [
        np.stack((ill_conditioned_incident[:, :, i], ill_conditioned_incident[:, :, i]), axis=1)
        for i in range(2)
    ]
    with pytest.raises(RuntimeError, match="ill-conditioned"):
        workflow._assemble_network_waves(ill_conditioned_waves)
    with pytest.raises(ValueError, match="two port"):
        workflow._assemble_network_waves(excitations[:1])
