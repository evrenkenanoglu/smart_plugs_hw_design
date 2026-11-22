import csv
import importlib.util
from pathlib import Path

import numpy as np
import pytest


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "smart_power_strip"
    / "workflows"
    / "01_verify_benchmark.py"
)
SPEC = importlib.util.spec_from_file_location("benchmark_workflow", WORKFLOW_PATH)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_voltage_wave_power_balance_normalizes_by_complex_port_admittance():
    reflected, transmitted, total = benchmark._voltage_wave_power_fractions(
        np.array([0.2 + 0j]),
        np.array([0.6 + 0j]),
        np.array([100.0 + 0j]),
        np.array([50.0 + 0j]),
    )

    assert reflected[0] == pytest.approx(0.04)
    assert transmitted[0] == pytest.approx(0.72)
    assert total[0] == pytest.approx(0.76)


def test_voltage_wave_power_balance_rejects_non_passive_reference_impedance():
    with pytest.raises(ValueError, match="positive real admittance"):
        benchmark._voltage_wave_power_fractions(
            np.array([0.0 + 0j]),
            np.array([0.5 + 0j]),
            np.array([50.0 + 0j]),
            np.array([-50.0 + 0j]),
        )


def test_graded_mesh_segment_resolves_near_field_and_limits_growth():
    lines = np.asarray(
        benchmark._graded_mesh_segment(
            0.0,
            20.0,
            initial_spacing=0.2,
            maximum_spacing=3.0,
            growth_ratio=1.4,
        )
    )
    spacings = np.diff(lines)
    increasing_ratios = spacings[1:][spacings[1:] >= spacings[:-1]] / spacings[:-1][
        spacings[1:] >= spacings[:-1]
    ]

    assert lines[0] == pytest.approx(0.0)
    assert lines[-1] == pytest.approx(20.0)
    assert spacings[0] == pytest.approx(0.2)
    assert np.max(spacings) <= 3.0
    assert np.all(increasing_ratios <= 1.4 + 1e-9)


def test_refinement_gate_checks_all_mesh_pairs_without_loosening_five_percent(
    tmp_path,
):
    frequencies = np.array([1e9, 2e9])
    levels = (
        ("mesh_coarse", 100.0),
        ("mesh_medium", 104.0),
        ("mesh_fine", 108.0),
    )
    mesh_results = []
    for level, impedance in levels:
        level_path = tmp_path / level
        level_path.mkdir()
        with (level_path / "port_z_ref.csv").open(
            "w", newline="", encoding="utf-8"
        ) as result_file:
            writer = csv.writer(result_file)
            writer.writerow(
                [
                    "frequency_hz",
                    "openems_input_mslport_z_ref_real_ohm",
                    "openems_input_mslport_z_ref_imag_ohm",
                    "openems_output_mslport_z_ref_real_ohm",
                    "openems_output_mslport_z_ref_imag_ohm",
                    "summed_power_fraction",
                ]
            )
            for frequency in frequencies:
                writer.writerow([frequency, impedance, 0.0, impedance, 0.0, 0.99])
        mesh_results.append(
            {"mesh_level": level, "postprocessing_success": True}
        )

    comparison = benchmark._write_generic_comparison(
        tmp_path, frequencies, mesh_results, analytical_z0_ohm=89.0
    )

    assert comparison["refinement_tolerance"] == 0.05
    assert comparison["pairwise_max_relative_changes"][
        "mesh_coarse_to_mesh_medium"
    ] == pytest.approx(4 / 104)
    assert comparison["pairwise_max_relative_changes"][
        "mesh_medium_to_mesh_fine"
    ] == pytest.approx(4 / 108)
    assert comparison["pairwise_max_relative_changes"][
        "mesh_coarse_to_mesh_fine"
    ] == pytest.approx(8 / 108)
    assert not comparison["refinement_stability_passed"]
    assert (tmp_path / "mesh_refinement_comparison.csv").is_file()
    assert (tmp_path / "zref_comparison.png").is_file()


def _write_boundary_zref(path, frequencies, input_values, output_values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as result_file:
        writer = csv.writer(result_file)
        writer.writerow(
            [
                "frequency_hz",
                "openems_input_mslport_z_ref_real_ohm",
                "openems_input_mslport_z_ref_imag_ohm",
                "openems_output_mslport_z_ref_real_ohm",
                "openems_output_mslport_z_ref_imag_ohm",
            ]
        )
        for frequency, input_value, output_value in zip(
            frequencies, input_values, output_values, strict=True
        ):
            writer.writerow(
                [
                    frequency,
                    input_value.real,
                    input_value.imag,
                    output_value.real,
                    output_value.imag,
                ]
            )


def test_boundary_independence_gate_checks_each_axis_and_both_ports(tmp_path):
    frequencies = np.array([1e9, 2e9])
    reference = tmp_path / "canonical_45mm" / "reference"
    variants = {
        name: tmp_path / "canonical_45mm" / name
        for name in ("expanded_x", "expanded_y", "expanded_z")
    }
    _write_boundary_zref(
        reference / "mesh_medium" / "port_z_ref.csv",
        frequencies,
        np.array([100 + 0j, 100 + 0j]),
        np.array([90 + 0j, 90 + 0j]),
    )
    _write_boundary_zref(
        variants["expanded_x"] / "mesh_medium" / "port_z_ref.csv",
        frequencies,
        np.array([101 + 0j, 101 + 0j]),
        np.array([91 + 0j, 91 + 0j]),
    )
    _write_boundary_zref(
        variants["expanded_y"] / "mesh_medium" / "port_z_ref.csv",
        frequencies,
        np.array([104 + 0j, 104 + 0j]),
        np.array([94 + 0j, 94 + 0j]),
    )
    expanded_z_path = variants["expanded_z"] / "mesh_medium" / "port_z_ref.csv"
    _write_boundary_zref(
        expanded_z_path,
        frequencies,
        np.array([104 + 0j, 104 + 0j]),
        np.array([94 + 0j, 94 + 0j]),
    )

    passing = benchmark._write_boundary_sensitivity(
        tmp_path, reference, variants, frequencies
    )
    assert passing["passed"]
    assert passing["relative_tolerance"] == 0.05
    assert passing["maximum_relative_change"] == pytest.approx(4 / 94)

    _write_boundary_zref(
        expanded_z_path,
        frequencies,
        np.array([106 + 0j, 106 + 0j]),
        np.array([96 + 0j, 96 + 0j]),
    )
    failing = benchmark._write_boundary_sensitivity(
        tmp_path, reference, variants, frequencies
    )
    assert not failing["passed"]
    assert failing["maximum_relative_change"] == pytest.approx(6 / 96)
    assert (tmp_path / "boundary_sensitivity.csv").is_file()
