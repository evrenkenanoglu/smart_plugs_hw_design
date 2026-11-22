"""Diagnose the historical L1 coupon against a closed-form microstrip estimate.

This script does not rerun or alter the archived openEMS pilot. A comparison
outside the configured tolerance blocks any claim that it is a validated
benchmark.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

EMC_ROOT = Path(__file__).resolve().parents[2]
if str(EMC_ROOT) not in sys.path:
    sys.path.insert(0, str(EMC_ROOT))

from emc_sim.analytical import (
    microstrip_characteristic_impedance,
    microstrip_effective_permittivity,
)
from emc_sim.reporting import create_run_directory, write_report, write_run_metadata


GENERIC_LENGTH_MM = 15.4598
GENERIC_WIDTH_MM = 1.0
GENERIC_SUBSTRATE_HEIGHT_MM = 1.6
GENERIC_EPSILON_R = 4.2
GENERIC_MAX_TIMESTEPS = 250_000
GENERIC_END_CRITERION = 1e-4
ANALYTICAL_TOLERANCE = 0.10
REFINEMENT_TOLERANCE = 0.05
BOUNDARY_INDEPENDENCE_TOLERANCE = REFINEMENT_TOLERANCE
POWER_BALANCE_EXCESS_TOLERANCE = 0.01
FREQUENCIES_HZ = (100e6, 2e9, 97)
PORT_EXTENSION_MM = 30.0
PORT_FEED_SHIFT_MM = 2.0
PORT_MEASUREMENT_SHIFT_MM = 15.0
PML_CELLS = 8
MESH_LEVELS = (
    {"name": "mesh_coarse", "dx_mm": 1.5, "dy_center_mm": 0.25, "z_substrate_cells": 4},
    {
        "name": "mesh_medium",
        "dx_mm": 1.25,
        "dy_center_mm": 1 / 6,
        "z_substrate_cells": 6,
    },
    {"name": "mesh_fine", "dx_mm": 1.0, "dy_center_mm": 0.125, "z_substrate_cells": 8},
)
COUPON_CASES = (
    {"name": "canonical_45mm", "length_mm": 45.0},
    {"name": "original_15p4598mm", "length_mm": GENERIC_LENGTH_MM},
)
BOUNDARY_CASES = (
    {
        "name": "reference",
        "x_padding_mm": 16.0,
        "y_half_extent_mm": 15.0,
        "z_max_mm": 20.0,
    },
    {
        "name": "expanded_x",
        "x_padding_mm": 32.0,
        "y_half_extent_mm": 15.0,
        "z_max_mm": 20.0,
    },
    {
        "name": "expanded_y",
        "x_padding_mm": 16.0,
        "y_half_extent_mm": 30.0,
        "z_max_mm": 20.0,
    },
    {
        "name": "expanded_z",
        "x_padding_mm": 16.0,
        "y_half_extent_mm": 15.0,
        "z_max_mm": 40.0,
    },
)

DEFAULT_HISTORY = (
    EMC_ROOT
    / "openems"
    / "experiments"
    / "runs"
    / "l1_route_20261117_180814"
)


def _append_log(path: Path, message: str) -> None:
    with path.open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def _mesh_axis(segments: list[tuple[float, float, float]],
               exact_lines: tuple[float, ...] = ()):
    import numpy as np

    lines = []
    for start, stop, maximum_spacing in segments:
        count = max(1, math.ceil((stop - start) / maximum_spacing))
        lines.extend(np.linspace(start, stop, count + 1).tolist())
    lines.extend(exact_lines)
    return np.unique(np.asarray(lines, dtype=float))


def _graded_mesh_segment(
    start: float,
    stop: float,
    initial_spacing: float,
    maximum_spacing: float,
    growth_ratio: float = 1.4,
) -> list[float]:
    if (
        not all(math.isfinite(value) for value in (start, stop, initial_spacing, maximum_spacing, growth_ratio))
        or stop <= start
        or initial_spacing <= 0.0
        or maximum_spacing <= 0.0
        or growth_ratio <= 1.0
    ):
        raise ValueError("Graded mesh segment parameters must be finite and positive")

    lines = [start]
    position = start
    spacing = min(initial_spacing, maximum_spacing)
    while position < stop:
        position = min(position + spacing, stop)
        lines.append(position)
        spacing = min(spacing * growth_ratio, maximum_spacing)
    return lines


def _voltage_wave_power_fractions(s11, s21, z_ref_input, z_ref_output):
    """Return reflected, transmitted, and total power fractions for voltage waves."""
    import numpy as np

    arrays = tuple(
        np.asarray(values, dtype=complex)
        for values in (s11, s21, z_ref_input, z_ref_output)
    )
    if any(array.ndim != 1 or array.shape != arrays[0].shape for array in arrays):
        raise ValueError("S-parameter and port-impedance arrays must have matching shapes")
    if not arrays[0].size or any(not np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("S-parameter and port-impedance arrays must be non-empty and finite")

    input_admittance = np.real(1.0 / arrays[2])
    output_admittance = np.real(1.0 / arrays[3])
    if (
        not np.all(np.isfinite(input_admittance))
        or not np.all(np.isfinite(output_admittance))
        or np.any(input_admittance <= 0.0)
        or np.any(output_admittance <= 0.0)
    ):
        raise ValueError("Port reference impedances must have positive real admittance")
    reflected = np.abs(arrays[0]) ** 2
    transmitted = np.abs(arrays[1]) ** 2 * output_admittance / input_admittance
    total = reflected + transmitted
    if not np.all(np.isfinite(total)):
        raise ValueError("Computed power fractions are not finite")
    return reflected, transmitted, total


def _relative_mesh_change(first, second):
    """Return per-frequency relative complex change between two port values."""
    import numpy as np

    first_values = np.asarray(first, dtype=complex)
    second_values = np.asarray(second, dtype=complex)
    if (
        first_values.ndim != 1
        or first_values.shape != second_values.shape
        or not first_values.size
        or not np.all(np.isfinite(first_values))
        or not np.all(np.isfinite(second_values))
    ):
        raise ValueError("Mesh values must be matching, non-empty finite vectors")
    return np.abs(second_values - first_values) / np.maximum(
        np.abs(second_values), 1e-15
    )


def _parse_solver_stats(run_path: Path) -> dict:
    summary_path = run_path / "openEMS_stats.txt"
    if not summary_path.is_file():
        raise FileNotFoundError("openEMS_stats.txt was not produced")

    values = {}
    with summary_path.open(encoding="utf-8") as summary:
        for line in summary:
            if "%" not in line:
                continue
            number, label = line.split("%", 1)
            label = label.strip().lower()
            try:
                value = float(number.strip())
            except ValueError:
                continue
            if "number of cells" in label:
                values["cell_count"] = int(value)
            elif "timestep (s)" in label:
                values["actual_timestep_s"] = value
            elif "number of iterations" in label:
                values["timestep_count"] = int(value)
            elif "simulation time" in label:
                values["solver_wall_time_s"] = value
            elif "total numerical time" in label:
                values["numerical_duration_s"] = value

    run_stats_path = run_path / "openEMS_run_stats.txt"
    if run_stats_path.is_file():
        samples = []
        with run_stats_path.open(encoding="utf-8") as run_stats:
            for line in run_stats:
                columns = line.split()
                if len(columns) != 4:
                    continue
                try:
                    samples.append(tuple(float(column) for column in columns))
                except ValueError:
                    continue
        if samples:
            energies = [sample[3] for sample in samples]
            peak = max(energies)
            values["sampled_final_energy_to_peak_ratio"] = (
                energies[-1] / peak if peak > 0 else None
            )
            values["energy_sample_count"] = len(samples)
    return values


def _run_mesh_level(
    run_directory: Path,
    mesh_spec: dict,
    frequencies_hz,
    analytical_z0_ohm: float,
    *,
    coupon_spec: dict,
    boundary_spec: dict,
) -> dict:
    import numpy as np

    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    level_name = mesh_spec["name"]
    level_path = run_directory / level_name
    level_path.mkdir(exist_ok=False)
    solver_log = level_path / "solver.log"
    result = {
        "mesh_level": level_name,
        "run_directory": level_name,
        "coupon_case": coupon_spec["name"],
        "boundary_case": boundary_spec["name"],
        "configured_max_timesteps": GENERIC_MAX_TIMESTEPS,
        "end_criterion": GENERIC_END_CRITERION,
        "solver_status": "not_started",
        "solver_energy_stop_passed": False,
        "postprocessing_success": False,
        "analytical_agreement_passed": False,
        "analytical_max_complex_relative_error": None,
    }

    try:
        length = float(coupon_spec["length_mm"])
        width = GENERIC_WIDTH_MM
        height = GENERIC_SUBSTRATE_HEIGHT_MM
        x_port_start = -PORT_EXTENSION_MM
        x_port_stop = length + PORT_EXTENSION_MM
        x_min = x_port_start - float(boundary_spec["x_padding_mm"])
        x_max = x_port_stop + float(boundary_spec["x_padding_mm"])
        y_min = -float(boundary_spec["y_half_extent_mm"])
        y_max = float(boundary_spec["y_half_extent_mm"])
        z_min = -height
        z_max = float(boundary_spec["z_max_mm"])

        x_lines = _mesh_axis(
            [
                (x_min, x_port_start, 1.5),
                (x_port_start, x_port_stop, mesh_spec["dx_mm"]),
                (x_port_stop, x_max, 1.5),
            ],
            exact_lines=(
                0.0,
                length,
                x_port_start + PORT_FEED_SHIFT_MM,
                x_port_start + PORT_MEASUREMENT_SHIFT_MM,
                x_port_stop - PORT_FEED_SHIFT_MM,
                x_port_stop - PORT_MEASUREMENT_SHIFT_MM,
                length + PORT_EXTENSION_MM - 0.5,
            ),
        )
        center_y_lines = _mesh_axis(
            [
                (-3.0, 3.0, mesh_spec["dy_center_mm"]),
            ],
            exact_lines=(-width / 2, width / 2),
        )
        positive_y_lines = _graded_mesh_segment(
            3.0,
            y_max,
            mesh_spec["dy_center_mm"],
            1.0,
        )
        negative_y_lines = [-value for value in reversed(positive_y_lines)]
        y_lines = np.unique(
            np.asarray([*negative_y_lines, *center_y_lines, *positive_y_lines])
        )
        substrate_z_step = height / mesh_spec["z_substrate_cells"]
        substrate_z_lines = _mesh_axis([(-height, 0.0, substrate_z_step)])
        air_z_lines = _graded_mesh_segment(
            0.0,
            z_max,
            substrate_z_step,
            3.0,
        )
        z_lines = np.unique(
            np.asarray([*substrate_z_lines, *air_z_lines])
        )

        fdtd = openEMS(
            NrTS=GENERIC_MAX_TIMESTEPS,
            EndCriteria=GENERIC_END_CRITERION,
        )
        fdtd.SetGaussExcite(1.05e9, 1.9e9)
        fdtd.SetBoundaryCond(["PML_8", "PML_8", "MUR", "MUR", "PEC", "MUR"])
        csx = ContinuousStructure()
        fdtd.SetCSX(csx)
        mesh = csx.GetGrid()
        mesh.SetDeltaUnit(1e-3)
        for axis, lines in (("x", x_lines), ("y", y_lines), ("z", z_lines)):
            mesh.AddLine(axis, lines)

        substrate = csx.AddMaterial(
            "Lossless_assumed_FR4_eps4p2",
            epsilon=[GENERIC_EPSILON_R] * 3,
            kappa=[0.0] * 3,
        )
        substrate.AddBox(
            start=[x_min, y_min, -height],
            stop=[x_max, y_max, 0.0],
            priority=0,
        )
        trace = csx.AddMetal("PEC_microstrip_trace")
        trace.AddBox(
            start=[x_min, -width / 2, 0.0],
            stop=[x_port_start, width / 2, 0.0],
            priority=10,
        )
        trace.AddBox(
            start=[0.0, -width / 2, 0.0],
            stop=[length, width / 2, 0.0],
            priority=10,
        )
        trace.AddBox(
            start=[x_port_stop, -width / 2, 0.0],
            stop=[x_max, width / 2, 0.0],
            priority=10,
        )
        fdtd.AddEdges2Grid(
            dirs="xy",
            properties=[trace],
            metal_edge_res=mesh_spec["dy_center_mm"],
        )
        input_port = fdtd.AddMSLPort(
            1,
            trace,
            start=[x_port_start, -width / 2, 0.0],
            stop=[0.0, width / 2, -height],
            prop_dir="x",
            exc_dir="z",
            excite=1.0,
            FeedShift=PORT_FEED_SHIFT_MM,
            MeasPlaneShift=PORT_MEASUREMENT_SHIFT_MM,
            priority=10,
        )
        output_port = fdtd.AddMSLPort(
            2,
            trace,
            start=[x_port_stop, -width / 2, 0.0],
            stop=[length, width / 2, -height],
            prop_dir="x",
            exc_dir="z",
            excite=0.0,
            FeedShift=PORT_FEED_SHIFT_MM,
            MeasPlaneShift=PORT_MEASUREMENT_SHIFT_MM,
            priority=10,
        )

        mesh.SmoothMeshLines("all", 3.0, 1.4)
        axis_lines = {
            axis: np.asarray(mesh.GetLines(axis), dtype=float)
            for axis in ("x", "y", "z")
        }
        delta_unit_m = float(mesh.GetDeltaUnit())
        min_spacing_mm = {
            axis: float(np.min(np.diff(lines))) for axis, lines in axis_lines.items()
        }
        z_zero_index = int(
            np.flatnonzero(np.isclose(axis_lines["z"], 0.0, rtol=0, atol=1e-9))[0]
        )
        z_air_spacing_mm = np.diff(axis_lines["z"][z_zero_index:])
        z_air_growth_ratios = (
            z_air_spacing_mm[1:] / z_air_spacing_mm[:-1]
            if len(z_air_spacing_mm) > 1
            else np.asarray([], dtype=float)
        )
        if np.any(z_air_growth_ratios > 1.4 + 1e-6):
            raise ValueError("Vertical air mesh grows faster than the configured 1.4 ratio")
        estimated_cell_count = math.prod(len(lines) - 1 for lines in axis_lines.values())
        for axis, required_lines in {
            "x": (
                x_port_start + PORT_FEED_SHIFT_MM,
                x_port_start + PORT_MEASUREMENT_SHIFT_MM,
                x_port_stop - PORT_FEED_SHIFT_MM,
                x_port_stop - PORT_MEASUREMENT_SHIFT_MM,
            ),
            "y": (-width / 2, width / 2),
            "z": (-height, 0.0),
        }.items():
            if any(
                not np.any(np.isclose(axis_lines[axis], coordinate, rtol=0, atol=1e-9))
                for coordinate in required_lines
            ):
                raise ValueError(f"Required port or conductor boundary is off the {axis}-mesh")

        edge_cell_widths = {}
        for edge in (-width / 2, width / 2):
            edge_indices = np.flatnonzero(
                np.isclose(axis_lines["y"], edge, rtol=0, atol=1e-9)
            )
            if len(edge_indices) != 1:
                raise ValueError(f"Trace edge {edge} mm is not uniquely meshed")
            edge_index = int(edge_indices[0])
            toward_center_mm = (
                axis_lines["y"][edge_index + 1] - edge
                if edge < 0
                else edge - axis_lines["y"][edge_index - 1]
            )
            away_from_center_mm = (
                edge - axis_lines["y"][edge_index - 1]
                if edge < 0
                else axis_lines["y"][edge_index + 1] - edge
            )
            ratios = sorted(
                (toward_center_mm / mesh_spec["dy_center_mm"],
                 away_from_center_mm / mesh_spec["dy_center_mm"])
            )
            if not np.allclose(ratios, (1 / 3, 2 / 3), rtol=0.01, atol=1e-9):
                raise ValueError(
                    f"Trace-edge mesh grading at y={edge} mm is {ratios}, "
                    "not the configured 1/3 and 2/3 spacing"
                )
            edge_cell_widths[f"{edge:g}"] = {
                "toward_center_mm": float(toward_center_mm),
                "away_from_center_mm": float(away_from_center_mm),
                "ratios_to_nominal_dy": [float(value) for value in ratios],
            }

        substrate_cell_count = int(
            np.count_nonzero(
                (axis_lines["z"] >= -height - 1e-9)
                & (axis_lines["z"] <= 1e-9)
            )
            - 1
        )
        if substrate_cell_count != mesh_spec["z_substrate_cells"]:
            raise ValueError(
                "Substrate mesh cell count does not match the requested resolution"
            )
        pml_interfaces = {
            "x": [
                float(axis_lines["x"][PML_CELLS]),
                float(axis_lines["x"][-PML_CELLS - 1]),
            ]
        }
        pml_clearances = {
            "input_port_start_to_x_pml_mm": float(
                x_port_start - pml_interfaces["x"][0]
            ),
            "output_port_start_to_x_pml_mm": float(
                pml_interfaces["x"][1] - x_port_stop
            ),
        }
        air_clearances = {
            "trace_edge_to_y_mur_mm": [
                float(-width / 2 - y_min),
                float(y_max - width / 2),
            ],
            "trace_to_z_plus_mur_mm": float(z_max),
            "substrate_to_z_plus_mur_mm": float(z_max),
        }
        for axis, coordinate in (
            ("x", x_port_start + PORT_FEED_SHIFT_MM),
            ("x", x_port_start + PORT_MEASUREMENT_SHIFT_MM),
            ("x", x_port_stop - PORT_FEED_SHIFT_MM),
            ("x", x_port_stop - PORT_MEASUREMENT_SHIFT_MM),
        ):
            if not pml_interfaces[axis][0] < coordinate < pml_interfaces[axis][1]:
                raise ValueError(
                    f"Port feed/measurement plane at x={coordinate} mm intersects PML"
                )
        csx_path = level_path / "generic_msl_coupon.xml"
        csx.Write2XML(str(csx_path))
        result.update(
            {
                "mesh_settings": {
                    "nominal_dx_mm_in_coupon_and_ports": mesh_spec["dx_mm"],
                    "nominal_dy_mm_across_trace_region": mesh_spec["dy_center_mm"],
                    "substrate_cells_through_thickness": mesh_spec["z_substrate_cells"],
                    "substrate_cells_verified": substrate_cell_count,
                    "first_air_cell_above_trace_mm": float(z_air_spacing_mm[0]),
                    "maximum_air_cell_spacing_growth_ratio": (
                        float(np.max(z_air_growth_ratios))
                        if z_air_growth_ratios.size
                        else 1.0
                    ),
                    "metal_edge_resolution_mm": mesh_spec["dy_center_mm"],
                    "trace_edge_mesh_lines_mm": [-width / 2, width / 2],
                    "trace_width_cells_after_edge_grading": int(
                        np.count_nonzero(
                            (axis_lines["y"] >= -width / 2 - 1e-9)
                            & (axis_lines["y"] <= width / 2 + 1e-9)
                        )
                        - 1
                    ),
                    "trace_edge_cell_widths_mm": edge_cell_widths,
                    "port_positions_mm": {
                        "input_feed_x": float(
                            x_port_start + PORT_FEED_SHIFT_MM
                        ),
                        "input_measurement_plane_x": float(
                            input_port.measplane_pos
                        ),
                        "output_feed_x": float(
                            x_port_stop - PORT_FEED_SHIFT_MM
                        ),
                        "output_measurement_plane_x": float(
                            output_port.measplane_pos
                        ),
                        "feed_to_measurement_distance_mm": float(
                            PORT_MEASUREMENT_SHIFT_MM - PORT_FEED_SHIFT_MM
                        ),
                        "measurement_plane_to_coupon_end_mm": float(
                            PORT_EXTENSION_MM - PORT_MEASUREMENT_SHIFT_MM
                        ),
                    },
                    "domain_bounds_mm": {
                        "x": [float(x_min), float(x_max)],
                        "y": [float(y_min), float(y_max)],
                        "z": [float(z_min), float(z_max)],
                    },
                    "x_pml_interface_positions_mm": pml_interfaces["x"],
                    "x_pml_clearances_mm": pml_clearances,
                    "air_clearances_to_mur_mm": air_clearances,
                    "ground_reference": (
                        "PEC boundary at z_min=-substrate height; infinite ideal "
                        "reference plane, no finite floating ground sheet"
                    ),
                    "max_smoothing_spacing_mm": 3.0,
                    "smoothing_ratio": 1.4,
                    "axis_line_counts": {
                        axis: int(len(lines)) for axis, lines in axis_lines.items()
                    },
                    "estimated_cartesian_cell_count": int(estimated_cell_count),
                    "minimum_cell_spacing_mm": min_spacing_mm,
                },
                "geometry_file": csx_path.name,
                "geometry_sha256": hashlib.sha256(csx_path.read_bytes()).hexdigest(),
            }
        )

        original_directory = Path.cwd()
        stdout_fd = os.dup(1)
        stderr_fd = os.dup(2)
        run_return_code = None
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            with solver_log.open("w", encoding="utf-8", buffering=1) as log:
                os.dup2(log.fileno(), 1)
                os.dup2(log.fileno(), 2)
                try:
                    _append_log(
                        run_directory / "benchmark.log",
                        f"Starting {level_name}; fixed NrTS={GENERIC_MAX_TIMESTEPS}, "
                        f"EndCriteria={GENERIC_END_CRITERION}",
                    )
                    run_return_code = fdtd.Run(
                        str(level_path),
                        cleanup=False,
                        verbose=1,
                        numThreads=4,
                        dump_statistics=True,
                        disable_dumps=True,
                    )
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()
        finally:
            os.dup2(stdout_fd, 1)
            os.dup2(stderr_fd, 2)
            os.close(stdout_fd)
            os.close(stderr_fd)
            os.chdir(original_directory)

        result["solver_return_code"] = (
            int(run_return_code) if isinstance(run_return_code, int) else None
        )
        stats = _parse_solver_stats(level_path)
        result["solver_statistics"] = stats
        iterations = stats.get("timestep_count")
        setup_ok = run_return_code in (None, 0) and iterations is not None
        energy_ratio = stats.get("sampled_final_energy_to_peak_ratio")
        energy_stop_marker = (
            f"end-criteria of "
            f"{10 * math.log10(GENERIC_END_CRITERION):.2f}db reached"
        )
        solver_log_text = solver_log.read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        energy_stop_confirmed = energy_stop_marker in solver_log_text
        energy_stop_reached = bool(
            setup_ok
            and iterations < GENERIC_MAX_TIMESTEPS
            and energy_stop_confirmed
            and energy_ratio is not None
            and math.isfinite(energy_ratio)
            and energy_ratio <= GENERIC_END_CRITERION
        )
        result["solver_energy_stop_passed"] = energy_stop_reached
        result["solver_energy_stop_log_confirmed"] = energy_stop_confirmed
        result["solver_status"] = (
            "energy_stop_before_timestep_cap"
            if energy_stop_reached
            else (
                "maximum_timesteps_reached"
                if iterations == GENERIC_MAX_TIMESTEPS
                else (
                    "stopped_before_cap_without_energy_confirmation"
                    if setup_ok
                    else "solver_or_setup_failed"
                )
            )
        )

        if not setup_ok:
            raise RuntimeError(
                f"openEMS did not produce completed solver statistics; return code "
                f"{run_return_code!r}, iterations {iterations!r}"
            )
        if not energy_stop_reached:
            raise RuntimeError(
                "openEMS did not satisfy the fixed energy-stop gate; require "
                f"fewer than {GENERIC_MAX_TIMESTEPS} timesteps, the explicit "
                "end-criteria log marker, and sampled energy/peak <= "
                f"{GENERIC_END_CRITERION:g} (steps={iterations!r}, "
                f"log_confirmed={energy_stop_confirmed}, "
                f"observed_energy_ratio={energy_ratio!r})"
            )

        input_port.CalcPort(str(level_path), frequencies_hz)
        output_port.CalcPort(str(level_path), frequencies_hz)
        z_ref_input = np.asarray(input_port.Z_ref, dtype=complex)
        z_ref_output = np.asarray(output_port.Z_ref, dtype=complex)
        expected_shape = np.asarray(frequencies_hz).shape
        if z_ref_input.shape != expected_shape or z_ref_output.shape != expected_shape:
            raise ValueError(
                "Expected one MSLPort.Z_ref value per frequency; "
                f"got input {z_ref_input.shape}, output {z_ref_output.shape}, "
                f"frequency {expected_shape}"
            )

        finite = bool(
            np.all(np.isfinite(z_ref_input)) and np.all(np.isfinite(z_ref_output))
        )
        analytic_error_input = np.abs(z_ref_input - analytical_z0_ohm) / analytical_z0_ohm
        analytic_error_output = (
            np.abs(z_ref_output - analytical_z0_ohm) / analytical_z0_ohm
        )
        maximum_analytic_error = (
            float(max(np.max(analytic_error_input), np.max(analytic_error_output)))
            if finite
            else None
        )
        result["analytical_max_complex_relative_error"] = maximum_analytic_error
        result["analytical_agreement_passed"] = bool(
            finite
            and maximum_analytic_error is not None
            and maximum_analytic_error <= ANALYTICAL_TOLERANCE
        )
        result["port_z_ref"] = {
            "frequency_dependent": True,
            "quantity_name": "openEMS MSLPort.Z_ref modal reference impedance; not measured impedance",
            "input_real_range_ohm": [
                float(np.min(z_ref_input.real)),
                float(np.max(z_ref_input.real)),
            ]
            if finite
            else None,
            "input_imag_range_ohm": [
                float(np.min(z_ref_input.imag)),
                float(np.max(z_ref_input.imag)),
            ]
            if finite
            else None,
            "output_real_range_ohm": [
                float(np.min(z_ref_output.real)),
                float(np.max(z_ref_output.real)),
            ]
            if finite
            else None,
            "output_imag_range_ohm": [
                float(np.min(z_ref_output.imag)),
                float(np.max(z_ref_output.imag)),
            ]
            if finite
            else None,
        }

        s11 = input_port.uf_ref / input_port.uf_inc
        s21 = output_port.uf_ref / input_port.uf_inc
        reflected_power_fraction, transmitted_power_fraction, total_power_fraction = (
            _voltage_wave_power_fractions(
                s11,
                s21,
                z_ref_input,
                z_ref_output,
            )
        )
        max_power_fraction = float(np.max(total_power_fraction))
        energy_balance_passed = (
            max_power_fraction <= 1.0 + POWER_BALANCE_EXCESS_TOLERANCE
        )
        result["energy_balance"] = {
            "normalization": (
                "Voltage-wave amplitudes normalized by each port's real "
                "characteristic admittance Re(1/Z_ref)"
            ),
            "summed_reflected_and_transmitted_power_fraction_range": [
                float(np.min(total_power_fraction)),
                max_power_fraction,
            ],
            "unaccounted_power_fraction_range": [
                float(np.min(1.0 - total_power_fraction)),
                float(np.max(1.0 - total_power_fraction)),
            ],
            "maximum_power_excess_fraction": max(
                0.0, max_power_fraction - 1.0
            ),
            "excess_tolerance_fraction": POWER_BALANCE_EXCESS_TOLERANCE,
            "passed": energy_balance_passed,
            "interpretation": (
                "A deficit may include dielectric absorption, power reaching "
                "the PML, radiation, and numerical error; this check does not "
                "separate those mechanisms."
            ),
        }
        with (level_path / "port_z_ref.csv").open(
            "w", newline="", encoding="utf-8"
        ) as result_file:
            writer = csv.writer(result_file)
            writer.writerow(
                [
                    "frequency_hz",
                    "analytical_hj_z0_ohm",
                    "openems_input_mslport_z_ref_real_ohm",
                    "openems_input_mslport_z_ref_imag_ohm",
                    "input_complex_relative_difference_from_hj",
                    "openems_output_mslport_z_ref_real_ohm",
                    "openems_output_mslport_z_ref_imag_ohm",
                    "output_complex_relative_difference_from_hj",
                    "s11_real",
                    "s11_imag",
                    "s21_voltage_wave_real",
                    "s21_voltage_wave_imag",
                    "s11_db",
                    "s21_db",
                    "reflected_power_fraction",
                    "transmitted_power_fraction",
                    "summed_power_fraction",
                    "unaccounted_power_fraction",
                ]
            )
            for index, frequency in enumerate(frequencies_hz):
                writer.writerow(
                    [
                        float(frequency),
                        analytical_z0_ohm,
                        float(z_ref_input[index].real),
                        float(z_ref_input[index].imag),
                        float(analytic_error_input[index]),
                        float(z_ref_output[index].real),
                        float(z_ref_output[index].imag),
                        float(analytic_error_output[index]),
                        float(s11[index].real),
                        float(s11[index].imag),
                        float(s21[index].real),
                        float(s21[index].imag),
                        float(20 * np.log10(max(abs(s11[index]), 1e-15))),
                        float(20 * np.log10(max(abs(s21[index]), 1e-15))),
                        float(reflected_power_fraction[index]),
                        float(transmitted_power_fraction[index]),
                        float(total_power_fraction[index]),
                        float(1.0 - total_power_fraction[index]),
                    ]
                )
        result["result_file"] = "port_z_ref.csv"
        result["postprocessing_success"] = finite
        result["mesh_status"] = (
            "blocked_power_balance"
            if not energy_balance_passed
            else (
                "passed_analytical_gate"
                if result["analytical_agreement_passed"]
                else "blocked_analytical_discrepancy"
            )
        )
        if not finite:
            raise ValueError("MSLPort.Z_ref contains non-finite values")

        _append_log(
            run_directory / "benchmark.log",
            f"Completed {level_name}: solver={result['solver_status']}, "
            f"cells={stats.get('cell_count')}, timesteps={iterations}, "
            f"max analytical complex relative error={maximum_analytic_error:.6g}",
        )
    except KeyboardInterrupt:
        result["solver_status"] = "interrupted_before_energy_stop"
        result["solver_energy_stop_passed"] = False
        result["interrupted"] = True
        result["mesh_status"] = "blocked_interrupted"
        result["error"] = "KeyboardInterrupt during solver execution"
        try:
            with solver_log.open("a", encoding="utf-8") as log:
                log.write("\nBenchmark interrupted before an energy-stop result.\n")
        except OSError:
            pass
        _append_log(
            run_directory / "benchmark.log",
            f"{level_name} interrupted before a confirmed energy stop",
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["mesh_status"] = "blocked_solver_or_postprocessing_failure"
        try:
            with solver_log.open("a", encoding="utf-8") as log:
                log.write("\nBenchmark wrapper exception:\n")
                log.write(traceback.format_exc())
        except OSError:
            pass
        _append_log(
            run_directory / "benchmark.log",
            f"{level_name} blocked: {result['error']}",
        )
    return result


def _write_generic_comparison(
    run_directory: Path,
    frequencies_hz,
    mesh_results: list[dict],
    analytical_z0_ohm: float,
) -> dict:
    import itertools

    import numpy as np

    comparison = {
        "refinement_stability_passed": False,
        "maximum_complex_relative_refinement_change": None,
        "refinement_tolerance": REFINEMENT_TOLERANCE,
        "pairwise_max_relative_changes": {},
    }
    valid_meshes = [
        item
        for item in mesh_results
        if item.get("postprocessing_success")
        and (run_directory / item["mesh_level"] / "port_z_ref.csv").is_file()
    ]
    mesh_data = {
        item["mesh_level"]: np.genfromtxt(
            run_directory / item["mesh_level"] / "port_z_ref.csv",
            delimiter=",",
            names=True,
            dtype=None,
            encoding="utf-8",
        )
        for item in valid_meshes
    }
    mesh_values = {}
    for level, data in mesh_data.items():
        mesh_values[level] = {
            "input": (
                data["openems_input_mslport_z_ref_real_ohm"]
                + 1j * data["openems_input_mslport_z_ref_imag_ohm"]
            ),
            "output": (
                data["openems_output_mslport_z_ref_real_ohm"]
                + 1j * data["openems_output_mslport_z_ref_imag_ohm"]
            ),
        }

    pairs = list(itertools.combinations(valid_meshes, 2))
    changes_by_pair = {}
    maximum_change_by_frequency = np.zeros(len(frequencies_hz), dtype=float)
    if len(valid_meshes) == len(mesh_results) and len(valid_meshes) >= 2:
        for first, second in pairs:
            first_name = first["mesh_level"]
            second_name = second["mesh_level"]
            input_change = _relative_mesh_change(
                mesh_values[first_name]["input"],
                mesh_values[second_name]["input"],
            )
            output_change = _relative_mesh_change(
                mesh_values[first_name]["output"],
                mesh_values[second_name]["output"],
            )
            pair_change = np.maximum(input_change, output_change)
            pair_name = f"{first_name}_to_{second_name}"
            changes_by_pair[pair_name] = pair_change
            comparison["pairwise_max_relative_changes"][pair_name] = float(
                np.max(pair_change)
            )
            maximum_change_by_frequency = np.maximum(
                maximum_change_by_frequency, pair_change
            )

        maximum_change = float(np.max(maximum_change_by_frequency))
        comparison["maximum_complex_relative_refinement_change"] = maximum_change
        comparison["refinement_stability_passed"] = (
            maximum_change <= REFINEMENT_TOLERANCE
        )

    comparison_path = run_directory / "mesh_refinement_comparison.csv"
    header = ["frequency_hz", "analytical_hj_z0_ohm"]
    for item in valid_meshes:
        level = item["mesh_level"]
        for port in ("input", "output"):
            header.extend(
                [
                    f"{level}_{port}_mslport_z_ref_real_ohm",
                    f"{level}_{port}_mslport_z_ref_imag_ohm",
                ]
            )
    header.extend(f"{pair}_max_relative_change" for pair in changes_by_pair)
    header.append("maximum_all_pairwise_relative_change")

    with comparison_path.open("w", newline="", encoding="utf-8") as result_file:
        writer = csv.writer(result_file)
        writer.writerow(header)
        if len(valid_meshes) == len(mesh_results) and len(valid_meshes) >= 2:
            for index, frequency in enumerate(frequencies_hz):
                row = [float(frequency), analytical_z0_ohm]
                for item in valid_meshes:
                    values = mesh_values[item["mesh_level"]]
                    for port in ("input", "output"):
                        value = values[port][index]
                        row.extend([float(value.real), float(value.imag)])
                row.extend(
                    float(change[index]) for change in changes_by_pair.values()
                )
                row.append(float(maximum_change_by_frequency[index]))
                writer.writerow(row)
    comparison["comparison_file"] = comparison_path.name

    if len(valid_meshes) == len(mesh_results) and len(valid_meshes) >= 2:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            frequencies_ghz = np.asarray(frequencies_hz) / 1e9
            figure, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)
            for item in valid_meshes:
                level = item["mesh_level"]
                data = mesh_data[level]
                values = mesh_values[level]
                label = level.removeprefix("mesh_")
                axes[0].plot(
                    frequencies_ghz,
                    data["openems_input_mslport_z_ref_real_ohm"],
                    label=f"{label} Re(Z_ref)",
                )
                axes[0].plot(
                    frequencies_ghz,
                    data["openems_input_mslport_z_ref_imag_ohm"],
                    "--",
                    label=f"{label} Im(Z_ref)",
                )
                axes[1].plot(
                    frequencies_ghz,
                    100
                    * np.abs(values["input"] - analytical_z0_ohm)
                    / analytical_z0_ohm,
                    label=f"{label} input deviation",
                )
                axes[2].plot(
                    frequencies_ghz,
                    data["summed_power_fraction"],
                    label=f"{label} power sum",
                )
            axes[0].axhline(
                analytical_z0_ohm,
                color="black",
                linestyle=":",
                label="Hammerstad-Jensen estimate",
            )
            axes[0].set_ylabel("openEMS MSLPort.Z_ref (ohm)")
            axes[0].grid(True)
            axes[0].legend(fontsize="small", ncol=2)
            axes[1].axhline(
                100 * ANALYTICAL_TOLERANCE,
                color="red",
                linestyle=":",
                label="analytical tolerance",
            )
            axes[1].set_ylabel("Complex relative difference (%)")
            axes[1].grid(True)
            axes[1].legend(fontsize="small")
            axes[2].axhline(1.0, color="black", linestyle=":")
            axes[2].set(
                xlabel="Frequency (GHz)",
                ylabel="Reflected + transmitted power",
            )
            axes[2].grid(True)
            axes[2].legend(fontsize="small")
            figure.tight_layout()
            figure.savefig(run_directory / "zref_comparison.png", dpi=160)
            plt.close(figure)
            comparison["plot_file"] = "zref_comparison.png"
        except Exception as error:
            comparison["plot_error"] = f"{type(error).__name__}: {error}"
    return comparison


def _read_port_impedances(csv_path: Path):
    import numpy as np

    data = np.genfromtxt(
        csv_path,
        delimiter=",",
        names=True,
        dtype=None,
        encoding="utf-8",
    )
    if data.shape == ():
        data = np.asarray([data], dtype=data.dtype)
    if data.ndim != 1 or not data.size or "frequency_hz" not in data.dtype.names:
        raise ValueError(f"Invalid port impedance table: {csv_path}")
    frequencies = np.asarray(data["frequency_hz"], dtype=float)
    impedances = {
        port: (
            np.asarray(data[f"openems_{port}_mslport_z_ref_real_ohm"], dtype=float)
            + 1j
            * np.asarray(
                data[f"openems_{port}_mslport_z_ref_imag_ohm"], dtype=float
            )
        )
        for port in ("input", "output")
    }
    if (
        not np.all(np.isfinite(frequencies))
        or any(not np.all(np.isfinite(values)) for values in impedances.values())
    ):
        raise ValueError(f"Non-finite port impedance values in {csv_path}")
    return frequencies, impedances


def _write_boundary_sensitivity(
    run_directory: Path,
    reference_directory: Path,
    variant_directories: dict[str, Path],
    frequencies_hz,
) -> dict:
    import numpy as np

    baseline_path = reference_directory / "mesh_medium" / "port_z_ref.csv"
    comparison = {
        "passed": False,
        "relative_tolerance": BOUNDARY_INDEPENDENCE_TOLERANCE,
        "maximum_relative_change": None,
        "case_max_relative_changes": {},
        "errors": [],
        "comparison_file": "boundary_sensitivity.csv",
    }
    columns = {}
    if not baseline_path.is_file():
        comparison["errors"].append(f"Missing reference impedance table: {baseline_path}")
        baseline_frequencies = np.asarray(frequencies_hz, dtype=float)
        baseline = None
    else:
        baseline_frequencies, baseline = _read_port_impedances(baseline_path)
        for port in ("input", "output"):
            columns[f"reference_{port}_real_ohm"] = baseline[port].real
            columns[f"reference_{port}_imag_ohm"] = baseline[port].imag

    case_maxima = []
    for case_name, case_directory in variant_directories.items():
        variant_path = case_directory / "mesh_medium" / "port_z_ref.csv"
        if not variant_path.is_file() or baseline is None:
            comparison["errors"].append(
                f"Missing impedance table required for {case_name}: {variant_path}"
            )
            continue
        variant_frequencies, variant = _read_port_impedances(variant_path)
        if (
            variant_frequencies.shape != baseline_frequencies.shape
            or not np.allclose(
                variant_frequencies, baseline_frequencies, rtol=0.0, atol=1e-6
            )
        ):
            comparison["errors"].append(
                f"Frequency samples differ for boundary case {case_name}"
            )
            continue

        per_port_changes = {}
        for port in ("input", "output"):
            change = _relative_mesh_change(baseline[port], variant[port])
            per_port_changes[port] = change
            columns[f"{case_name}_{port}_relative_change"] = change
        maximum_change = float(
            max(np.max(values) for values in per_port_changes.values())
        )
        comparison["case_max_relative_changes"][case_name] = maximum_change
        case_maxima.append(maximum_change)

    if case_maxima and not comparison["errors"]:
        maximum_change = max(case_maxima)
        comparison["maximum_relative_change"] = maximum_change
        comparison["passed"] = (
            maximum_change <= BOUNDARY_INDEPENDENCE_TOLERANCE
        )
    elif not variant_directories:
        comparison["errors"].append("No expanded-boundary cases were provided")

    header = ["frequency_hz"]
    header.extend(columns)
    with (run_directory / comparison["comparison_file"]).open(
        "w", newline="", encoding="utf-8"
    ) as result_file:
        writer = csv.writer(result_file)
        writer.writerow(header)
        for index, frequency in enumerate(baseline_frequencies):
            writer.writerow(
                [float(frequency)]
                + [float(values[index]) for values in columns.values()]
            )
    return comparison


def _write_length_diagnostic(
    run_directory: Path,
    canonical_directory: Path,
    original_directory: Path,
    mesh_specs: tuple[dict, ...],
    frequencies_hz,
) -> dict:
    import numpy as np

    diagnostic = {
        "purpose": (
            "Diagnostic only: compare port-field-derived Z_ref for the original "
            "short coupon against the 45 mm coupon at identical mesh levels."
        ),
        "relative_tolerance_for_interpretation": REFINEMENT_TOLERANCE,
        "passed": False,
        "maximum_relative_change": None,
        "mesh_level_max_relative_changes": {},
        "errors": [],
        "comparison_file": "coupon_length_diagnostic.csv",
    }
    columns = {}
    max_changes = []
    sample_frequencies = np.asarray(frequencies_hz, dtype=float)
    for mesh_spec in mesh_specs:
        level_name = mesh_spec["name"]
        canonical_path = canonical_directory / level_name / "port_z_ref.csv"
        original_path = original_directory / level_name / "port_z_ref.csv"
        if not canonical_path.is_file() or not original_path.is_file():
            diagnostic["errors"].append(
                f"Missing {level_name} impedance table for coupon-length comparison"
            )
            continue
        canonical_frequencies, canonical = _read_port_impedances(canonical_path)
        original_frequencies, original = _read_port_impedances(original_path)
        if (
            canonical_frequencies.shape != original_frequencies.shape
            or not np.allclose(
                canonical_frequencies, original_frequencies, rtol=0.0, atol=1e-6
            )
        ):
            diagnostic["errors"].append(
                f"Frequency samples differ at mesh level {level_name}"
            )
            continue
        sample_frequencies = canonical_frequencies
        for port in ("input", "output"):
            columns[f"{level_name}_canonical_{port}_real_ohm"] = canonical[
                port
            ].real
            columns[f"{level_name}_canonical_{port}_imag_ohm"] = canonical[
                port
            ].imag
            columns[f"{level_name}_original_{port}_real_ohm"] = original[
                port
            ].real
            columns[f"{level_name}_original_{port}_imag_ohm"] = original[
                port
            ].imag
            change = _relative_mesh_change(original[port], canonical[port])
            columns[f"{level_name}_{port}_relative_change"] = change
            max_changes.append(float(np.max(change)))
        level_maximum = max(
            float(np.max(columns[f"{level_name}_{port}_relative_change"]))
            for port in ("input", "output")
        )
        diagnostic["mesh_level_max_relative_changes"][level_name] = level_maximum

    if max_changes and not diagnostic["errors"]:
        maximum_change = max(max_changes)
        diagnostic["maximum_relative_change"] = maximum_change
        diagnostic["passed"] = maximum_change <= REFINEMENT_TOLERANCE

    with (run_directory / diagnostic["comparison_file"]).open(
        "w", newline="", encoding="utf-8"
    ) as result_file:
        writer = csv.writer(result_file)
        writer.writerow(["frequency_hz", *columns])
        for index, frequency in enumerate(sample_frequencies):
            writer.writerow(
                [float(frequency)]
                + [float(values[index]) for values in columns.values()]
            )
    return diagnostic


def run_generic_coupon() -> int:
    import numpy as np
    import CSXCAD as csxcad_package
    import openEMS as openems_package

    run_root = EMC_ROOT / "smart_power_strip" / "runs" / "benchmark"
    run_id = (
        "generic_msl_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        + "_"
        + uuid4().hex[:8]
    )
    run_directory = create_run_directory(run_root, run_id)
    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    shutil.copy2(source_path, run_directory / "benchmark_driver.py")
    benchmark_log = run_directory / "benchmark.log"
    _append_log(benchmark_log, "Created unique generic MSL benchmark run directory")

    analytical_z0 = microstrip_characteristic_impedance(
        GENERIC_WIDTH_MM * 1e-3,
        GENERIC_SUBSTRATE_HEIGHT_MM * 1e-3,
        GENERIC_EPSILON_R,
    )
    effective_epsilon = microstrip_effective_permittivity(
        GENERIC_WIDTH_MM * 1e-3,
        GENERIC_SUBSTRATE_HEIGHT_MM * 1e-3,
        GENERIC_EPSILON_R,
    )
    frequencies_hz = np.linspace(*FREQUENCIES_HZ)
    mesh_specs = tuple(dict(spec) for spec in MESH_LEVELS)
    reference_boundary = BOUNDARY_CASES[0]
    coupon_directories = {
        spec["name"]: run_directory / spec["name"] / reference_boundary["name"]
        for spec in COUPON_CASES
    }
    coupon_results = {}
    all_solver_runs = []

    for coupon_spec in COUPON_CASES:
        coupon_directory = coupon_directories[coupon_spec["name"]]
        coupon_directory.mkdir(parents=True, exist_ok=True)
        mesh_results = []
        for mesh_spec in mesh_specs:
            mesh_result = _run_mesh_level(
                coupon_directory,
                mesh_spec,
                frequencies_hz,
                analytical_z0,
                coupon_spec=coupon_spec,
                boundary_spec=reference_boundary,
            )
            mesh_result["artifact_path"] = str(
                (coupon_directory / mesh_spec["name"]).relative_to(run_directory)
            )
            mesh_results.append(mesh_result)
            all_solver_runs.append(mesh_result)
            if mesh_result.get("interrupted"):
                break

        comparison = _write_generic_comparison(
            coupon_directory, frequencies_hz, mesh_results, analytical_z0
        )
        coupon_results[coupon_spec["name"]] = {
            "trace_length_mm": coupon_spec["length_mm"],
            "mesh_levels": mesh_results,
            "refinement_comparison": comparison,
        }
        if any(item.get("interrupted") for item in mesh_results):
            break

    canonical_name = COUPON_CASES[0]["name"]
    original_name = COUPON_CASES[1]["name"]
    canonical_directory = coupon_directories[canonical_name]
    original_directory = coupon_directories[original_name]
    canonical_results = coupon_results.get(canonical_name, {}).get("mesh_levels", [])
    original_results = coupon_results.get(original_name, {}).get("mesh_levels", [])
    canonical_comparison = coupon_results.get(canonical_name, {}).get(
        "refinement_comparison", {}
    )

    boundary_directories = {
        spec["name"]: run_directory / canonical_name / spec["name"]
        for spec in BOUNDARY_CASES[1:]
    }
    for boundary_spec in BOUNDARY_CASES[1:]:
        boundary_directory = boundary_directories[boundary_spec["name"]]
        boundary_directory.mkdir(parents=True, exist_ok=True)
        if (
            len(canonical_results) != len(mesh_specs)
            or any(item.get("interrupted") for item in all_solver_runs)
        ):
            continue
        mesh_result = _run_mesh_level(
            boundary_directory,
            mesh_specs[1],
            frequencies_hz,
            analytical_z0,
            coupon_spec=COUPON_CASES[0],
            boundary_spec=boundary_spec,
        )
        mesh_result["artifact_path"] = str(
            (boundary_directory / mesh_specs[1]["name"]).relative_to(run_directory)
        )
        all_solver_runs.append(mesh_result)
        if mesh_result.get("interrupted"):
            break

    boundary_comparison = _write_boundary_sensitivity(
        run_directory,
        canonical_directory,
        boundary_directories,
        frequencies_hz,
    )
    length_diagnostic = _write_length_diagnostic(
        run_directory,
        canonical_directory,
        original_directory,
        mesh_specs,
        frequencies_hz,
    )

    expected_run_count = len(COUPON_CASES) * len(mesh_specs) + len(BOUNDARY_CASES) - 1
    energy_stop_passed = (
        len(all_solver_runs) == expected_run_count
        and all(item.get("solver_energy_stop_passed", False) for item in all_solver_runs)
    )
    power_balance_passed = (
        len(all_solver_runs) == expected_run_count
        and all(
            item.get("energy_balance", {}).get("passed", False)
            for item in all_solver_runs
        )
    )
    analytical_passed = (
        len(canonical_results) == len(mesh_specs)
        and all(
            item.get("analytical_agreement_passed", False)
            for item in canonical_results
        )
    )
    refinement_passed = canonical_comparison.get(
        "refinement_stability_passed", False
    )
    all_gates_passed = bool(
        energy_stop_passed
        and power_balance_passed
        and analytical_passed
        and refinement_passed
        and boundary_comparison["passed"]
    )
    status = "passed" if all_gates_passed else "blocked"

    run_metadata = {
        "scope": (
            "generic, non-product MSL coupon benchmark only; not a PCB, smart-plug, "
            "product, emissions, safety, compliance, or certification result"
        ),
        "benchmark_status": status,
        "benchmark_gate_passed": all_gates_passed,
        "provenance": {
            "parameter_source": (
                "User-specified generic coupon dimensions and assumed material values; "
                "no native CAD, PCB, Gerber, BOM, or historical pilot geometry imported."
            ),
            "source_script": str(source_path),
            "source_script_sha256": source_sha256,
            "saved_driver": "benchmark_driver.py",
            "historical_experiment_inputs_used": False,
        },
        "tool_versions": {
            "openems": getattr(openems_package, "__version__", "unknown"),
            "csxcad": getattr(csxcad_package, "__version__", "unknown"),
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "csxcad_install_path": os.environ.get("CSXCAD_INSTALL_PATH"),
            "openems_executable": shutil.which("openEMS"),
        },
        "geometry": {
            "units": "mm",
            "trace_width_mm": GENERIC_WIDTH_MM,
            "substrate_height_mm": GENERIC_SUBSTRATE_HEIGHT_MM,
            "port_extension_mm_each_end": PORT_EXTENSION_MM,
            "coupons": {
                spec["name"]: {
                    "trace_length_mm": spec["length_mm"],
                    "trace_shape": (
                        "Straight, uniform, zero-thickness PEC strip; no bends or vias."
                    ),
                }
                for spec in COUPON_CASES
            },
            "cross_section": (
                "Homogeneous dielectric from z=-1.6 mm to 0; strip at z=0; "
                "z_min is a PEC boundary used as the infinite ideal ground reference."
            ),
            "ground_reference": (
                "openEMS PEC boundary at z_min=-substrate height. No finite-width "
                "ground sheet is present, so the ground reference is not a floating island."
            ),
            "reference_domain_bounds_mm": (
                canonical_results[1].get("mesh_settings", {}).get(
                    "domain_bounds_mm"
                )
                if len(canonical_results) > 1
                else None
            ),
            "boundary_cases": {
                spec["name"]: {
                    "x_domain_padding_from_port_start_mm": spec["x_padding_mm"],
                    "y_half_extent_mm": spec["y_half_extent_mm"],
                    "z_max_mm": spec["z_max_mm"],
                }
                for spec in BOUNDARY_CASES
            },
        },
        "material_assumptions": {
            "substrate": "Idealized homogeneous, isotropic FR-4 surrogate",
            "relative_permittivity": GENERIC_EPSILON_R,
            "relative_permeability": 1.0,
            "loss_tangent": 0.0,
            "dielectric_loss": (
                "Disabled (kappa=0) for direct comparison to the lossless "
                "quasi-static Hammerstad-Jensen reference; not a product laminate model."
            ),
            "copper": "PEC, zero thickness; finite conductivity, plating and roughness omitted.",
            "solder_mask": "Omitted.",
            "surrounding_medium": "Free space/air, relative permittivity 1.",
        },
        "excitation": {
            "type": "Gaussian pulse at input openEMS MSLPort",
            "center_frequency_hz": 1.05e9,
            "bandwidth_hz": 1.9e9,
            "sweep_hz": [
                float(frequencies_hz[0]),
                float(frequencies_hz[-1]),
            ],
            "frequency_sample_count": int(len(frequencies_hz)),
            "port_geometry": (
                "Both ports are openEMS MSLPorts, not LumpedPorts. They span the "
                "1.0 mm trace width and 1.6 mm substrate height. With a 30 mm "
                "extension, FeedShift=2 mm and MeasPlaneShift=15 mm; the "
                "measurement plane is centered in the port extension, 13 mm "
                "from the feed and 15 mm outside the coupon end. Both are snapped "
                "to x-grid lines. The output port "
                "direction is -x, so its transmitted wave is the port's reflected "
                "wave. The trace and dielectric continue to the x-directed PML."
            ),
            "source_impedance_assumption": (
                "MSLPort Feed_R left at its default infinity (ideal port source); "
                "no resistor is used as a termination. The line continues into "
                "PML_8 at both x boundaries. The output MSLPort is an unexcited "
                "field monitor. No product source or load impedance is modeled."
            ),
            "reported_impedance": (
                "Frequency-dependent openEMS MSLPort.Z_ref modal reference impedance "
                "extracted by the solver from port fields; it is not measured impedance."
            ),
        },
        "boundary_conditions": {
            "faces": {
                "x_min": "PML_8",
                "x_max": "PML_8",
                "y_min": "MUR",
                "y_max": "MUR",
                "z_min": "PEC (infinite ideal ground reference)",
                "z_max": "MUR",
            },
            "x_pml_cells": PML_CELLS,
            "padding": (
                "Actual x-directed PML interfaces and all six domain bounds are "
                "recorded per run. Separate x, y, and z extent cases compare "
                "MSLPort.Z_ref against the reference domain."
            ),
        },
        "analytical_reference": {
            "method": "zero-thickness quasi-static Hammerstad-Jensen microstrip equations",
            "estimated_z0_ohm": analytical_z0,
            "estimated_effective_relative_permittivity": effective_epsilon,
            "assumptions": (
                "Zero-thickness strip, effectively infinite ground plane, homogeneous "
                "isotropic nondispersive dielectric, lossless quasi-static mode."
            ),
        },
        "acceptance_criteria": {
            "analytical_agreement": (
                "For both input and output openEMS MSLPort.Z_ref values at every "
                "frequency from 100 MHz through 2 GHz, max(|Z_ref - Z_HJ| / "
                "Z_HJ) <= tolerance; the comparison is complex-valued and uses "
                "the lossless HJ reference."
            ),
            "analytical_tolerance_fraction": ANALYTICAL_TOLERANCE,
            "mesh_refinement_stability": (
                "Across both ports, every frequency, and every pair of coarse, "
                "medium, and fine meshes, max(|Z_second - Z_first| / "
                "|Z_second|) <= tolerance."
            ),
            "refinement_tolerance_fraction": REFINEMENT_TOLERANCE,
            "boundary_independence": (
                "At the medium mesh, compare both ports and every frequency for "
                "independent x-PML, y-MUR, and z+-MUR extent increases; require "
                "maximum complex relative Z_ref change <= 5%."
            ),
            "boundary_independence_tolerance_fraction": (
                BOUNDARY_INDEPENDENCE_TOLERANCE
            ),
            "power_balance": (
                "For each mesh and frequency, sum reflected input power and "
                "transmitted output power after normalizing voltage waves by "
                "Re(1/Z_ref); allow at most the configured numerical excess."
            ),
            "power_balance_excess_tolerance_fraction": (
                POWER_BALANCE_EXCESS_TOLERANCE
            ),
            "power_balance_tolerance_basis": (
                "A numerical screening allowance only; it is not a product "
                "standard or certification criterion."
            ),
            "solver_energy_stop": (
                "Each run must stop before the fixed NrTS cap of 250000, include "
                "openEMS's explicit -40.00 dB end-criteria log marker, and have a "
                "sampled final-energy/peak ratio <= 1e-4. Reaching the cap or "
                "stopping without all three pieces of evidence is blocked."
            ),
            "tolerance_basis": (
                "Predeclared engineering screening tolerances for a generic "
                "quasi-static benchmark, not a product standard or certification limit."
            ),
        },
        "mesh_levels": canonical_results,
        "refinement_comparison": canonical_comparison,
        "coupon_results": coupon_results,
        "boundary_convergence": boundary_comparison,
        "coupon_length_diagnostic": length_diagnostic,
        "gates": {
            "solver_energy_stop_passed": energy_stop_passed,
            "power_balance_passed": power_balance_passed,
            "analytical_agreement_passed": analytical_passed,
            "mesh_refinement_stability_passed": refinement_passed,
            "boundary_independence_passed": boundary_comparison["passed"],
            "short_coupon_length_diagnostic_passed": length_diagnostic["passed"],
            "all_gates_passed": all_gates_passed,
        },
        "uncertainties_and_omissions": [
            "FR-4 epsilon_r=4.2 is an assumed constant, not frequency-dependent laminate data.",
            "The benchmark uses a lossless dielectric to match the analytical reference; actual laminate loss and dispersion are omitted.",
            "The z_min PEC boundary is an ideal infinite ground plane; finite copper thickness, conductivity, plating, and roughness are omitted.",
            "Zero-thickness PEC conductors omit copper thickness, conductivity, plating, roughness and edge-current effects.",
            "Solder mask, vias, bends, components, enclosure, cables, and real source/load impedances are omitted.",
            "MUR/PML boundary truncation, mesh discretization and port placement can affect the extracted modal impedance; boundary sensitivity is explicitly checked but does not validate all boundary configurations.",
            "No physical measurement has been made.",
        ],
        "measurements": [],
        "result_files": sorted(
            str(path.relative_to(run_directory))
            for path in run_directory.rglob("*")
            if path.is_file() and path.name != "run_metadata.json"
        ),
    }
    write_run_metadata(run_directory, run_metadata)

    energy_summary = ", ".join(
        f"{item['coupon_case']}/{item['boundary_case']}/{item['mesh_level']}: "
        f"{item['solver_status']} "
        f"({item.get('solver_statistics', {}).get('timestep_count', 'n/a')} steps)"
        for item in all_solver_runs
    )
    canonical_errors = ", ".join(
        f"{item['mesh_level']}={item.get('analytical_max_complex_relative_error', float('nan')):.2%}"
        for item in canonical_results
        if item.get("analytical_max_complex_relative_error") is not None
    ) or "unavailable"
    boundary_change = boundary_comparison.get("maximum_relative_change")
    boundary_change_text = (
        f"{boundary_change:.2%}" if boundary_change is not None else "unavailable"
    )
    length_change = length_diagnostic.get("maximum_relative_change")
    length_change_text = (
        f"{length_change:.2%}" if length_change is not None else "unavailable"
    )
    result_text = (
        f"Generic coupon benchmark {status.upper()}. Hammerstad-Jensen estimate: "
        f"{analytical_z0:.3f} ohm. Canonical 45 mm analytical max errors "
        f"(coarse/medium/fine): {canonical_errors}. Solver energy-stop gate: "
        f"{'PASS' if energy_stop_passed else 'BLOCKED'}; power-balance gate: "
        f"{'PASS' if power_balance_passed else 'BLOCKED'}; analytical gate: "
        f"{'PASS' if analytical_passed else 'BLOCKED'}; 5% mesh gate: "
        f"{'PASS' if refinement_passed else 'BLOCKED'}; 5% boundary-independence "
        f"gate: {'PASS' if boundary_comparison['passed'] else 'BLOCKED'} "
        f"(max change {boundary_change_text}). Original-length diagnostic max "
        f"change versus 45 mm: {length_change_text}. Runs: {energy_summary}. "
        "The compared values are frequency-dependent openEMS MSLPort.Z_ref modal "
        "reference impedances, not measured impedances. This generic coupon is "
        "not the user's PCB or product."
    )
    evidence = {
        "assumptions": [
            "Generic 45 mm and original 15.4598 mm x 1.0 mm straight coupons; assumed h=1.6 mm and FR-4 surrogate epsilon_r=4.2.",
            "Lossless dielectric, zero-thickness PEC strip, and an infinite ideal ground reference implemented by PEC at z_min.",
            (
                "AddMSLPort at both ends; 30 mm port extensions, FeedShift=2 mm, "
                "MeasPlaneShift=15 mm, 13 mm between feed and measurement planes, "
                "and 15 mm from measurement plane to coupon end. Feed_R remains at "
                "default infinity; the trace continues through x-directed PML_8."
            ),
            "Separate x-PML, y-MUR, and z+-MUR extent cases compare medium-mesh Z_ref; all domains are written from the actual mesh bounds.",
            "No PCB, Gerbers, native CAD, components, enclosure, cables or product operating case used.",
            f"openEMS {run_metadata['tool_versions']['openems']}; CSXCAD {run_metadata['tool_versions']['csxcad']}; Python {platform.python_version()}.",
        ],
        "calculations": [
            f"Hammerstad-Jensen estimate: {analytical_z0:.3f} ohm.",
            f"Hammerstad-Jensen effective relative permittivity estimate: {effective_epsilon:.5f}.",
            f"Analytical tolerance: {ANALYTICAL_TOLERANCE:.1%}; mesh and boundary tolerances: {REFINEMENT_TOLERANCE:.1%}.",
            f"Boundary-independence max relative change: {boundary_change_text}; diagnostic coupon-length max relative change: {length_change_text}.",
        ],
        "simulations": [
            f"{item['coupon_case']}/{item['boundary_case']}/{item['mesh_level']}: status {item['solver_status']}; solver statistics {item.get('solver_statistics', {})}; "
            f"max complex analytical relative difference {item.get('analytical_max_complex_relative_error')}; "
            f"power-balance summary {item.get('energy_balance', {})}."
            for item in all_solver_runs
        ],
        "measurements": [],
    }
    limitations = [
        "Model quantity is the openEMS MSLPort.Z_ref modal reference impedance; it is not a measured impedance.",
        "A benchmark pass does not validate a product PCB, predict emissions, or establish safety, compliance, certification, or margin.",
        "The selected tolerances are engineering screening criteria, not requirements from a product standard.",
        "The ideal MSLPort source and unexcited output monitor do not represent product source/load impedances; boundary termination and port placement may affect standing waves.",
        "Analytical Hammerstad-Jensen equations omit finite-frequency dispersion, dielectric loss, and conductor thickness; the model uses a lossless surrogate for a like-for-like benchmark.",
        "Any real product assessment requires revision-matched design evidence, validated operating cases, and review by qualified engineers.",
        "Product EMC, safety and certification testing must be performed by a properly equipped, qualified laboratory; this model is not a substitute and provides no energized-test instructions.",
    ]
    write_report(
        run_directory,
        question=(
            "For a generic non-product 45 mm x 1.0 mm microstrip coupon, do "
            "frequency-dependent openEMS MSLPort.Z_ref values agree with the "
            "Hammerstad-Jensen estimate and remain stable across mesh and "
            "independent boundary extents, while the original 15.4598 mm length "
            "is checked for port-coupling sensitivity?"
        ),
        evidence=evidence,
        result=result_text,
        limitations=limitations,
    )
    _append_log(benchmark_log, result_text)
    print(result_text)
    print(f"Generic benchmark artifacts: {run_directory}")
    return 0 if all_gates_passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-generic-coupon",
        action="store_true",
        help=(
            "explicitly run a new generic, non-product openEMS MSL coupon "
            "with coarse, medium, and fine mesh levels; the historical "
            "diagnostic remains the default"
        ),
    )
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--relative-tolerance", type=float, default=0.05)
    args = parser.parse_args()

    if args.run_generic_coupon:
        return run_generic_coupon()

    metadata = json.loads(
        (args.history / "run_metadata.json").read_text(encoding="utf-8")
    )
    assumptions = metadata["assumptions"]
    width_m = float(metadata["route_width_mm"]) * 1e-3
    height_m = float(assumptions["board_thickness_mm"]) * 1e-3
    eps_r = float(assumptions["relative_permittivity"])
    calculated_z0 = microstrip_characteristic_impedance(width_m, height_m, eps_r)
    port_range = metadata["excitation"]["port_reference_impedance"]["real_range_ohm"]
    port_reference_midpoint = sum(port_range) / 2.0
    relative_difference = abs(port_reference_midpoint - calculated_z0) / calculated_z0
    benchmark_gate = relative_difference <= args.relative_tolerance

    with (args.history / "s_parameters.csv").open(
        newline="", encoding="utf-8"
    ) as source:
        rows = list(csv.DictReader(source))
    run_directory = create_run_directory(EMC_ROOT / "smart_power_strip" / "runs" / "benchmark")
    run_metadata = {
        "scope": "historical coupon diagnostic only; not a new FDTD simulation",
        "historical_run": str(args.history),
        "historical_solver": metadata.get("solver"),
        "historical_solver_status": metadata.get("solver_status"),
        "benchmark_gate": "consistent_with_estimate" if benchmark_gate else "blocked_discrepancy",
        "benchmark_gate_passed": benchmark_gate,
        "relative_tolerance": args.relative_tolerance,
        "calculation": {
            "method": "zero-thickness quasi-static Hammerstad-Jensen microstrip estimate",
            "trace_width_m": width_m,
            "substrate_height_m": height_m,
            "relative_permittivity": eps_r,
            "estimated_z0_ohm": calculated_z0,
        },
        "historical_simulation": {
            "port_reference_impedance_real_range_ohm": port_range,
            "msl_port_z_ref_real_midpoint_ohm": port_reference_midpoint,
            "relative_difference_from_estimate": relative_difference,
            "s_parameter_row_count": len(rows),
            "s_parameters_are_interpreted_as_product_results": False,
        },
        "assumptions": [
            "Historical coupon dimensions and assumed material values are used as supplied.",
            "The historical coupon assumes a continuous return plane not imported from the PCB.",
        ],
        "measurements": [],
    }
    write_run_metadata(run_directory, run_metadata)
    result = (
        f"Analytical Z0 estimate: {calculated_z0:.3f} ohm. "
        f"Historical MSL port-reference real-part midpoint: "
        f"{port_reference_midpoint:.3f} ohm. "
        f"Relative difference: {relative_difference:.1%}. "
        + (
            "The configured diagnostic tolerance is met; this alone does not establish "
            "mesh convergence or validate the historical model."
            if benchmark_gate
            else "The benchmark gate is BLOCKED. Do not interpret the historical "
            "S-parameters or use them to change the PCB."
        )
    )
    write_report(
        run_directory,
        question="Does the historical coupon's extracted port impedance agree with a simple analytical microstrip estimate?",
        evidence={
            "assumptions": run_metadata["assumptions"],
            "calculations": [
                f"Hammerstad-Jensen estimate: {calculated_z0:.3f} ohm",
                f"Relative difference: {relative_difference:.1%}",
            ],
            "simulations": [
                f"Historical openEMS run status: {metadata.get('solver_status')}",
                "Historical S-parameters are retained as simulation outputs but not treated as product performance.",
            ],
            "measurements": [],
        },
        result=result,
        limitations=[
            "This is a post-hoc diagnostic; no openEMS model was rerun.",
            "The simplified analytical formula omits copper thickness, roughness, finite plane dimensions, and dispersion.",
            "The coupon is not the full PCB or actual filter; no mesh convergence study is available.",
        ],
    )
    print(result)
    print(f"Diagnostic artifacts: {run_directory}")
    return 0 if benchmark_gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
