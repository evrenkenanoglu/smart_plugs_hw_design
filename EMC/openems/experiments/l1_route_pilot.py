from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import argparse
import zipfile
from datetime import datetime
from json import JSONDecoder
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import CSXCAD as csxcad_package
import openEMS as openems_package
from CSXCAD import ContinuousStructure
from openEMS import openEMS


ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    ROOT
    / "PCB_DESIGN"
    / "Smart_Plugs_EasyEDA"
    / "Smart_Plugs_backup"
    / "Smart_Plugs_2026-11-15-00-26.epro2"
)
PCB_UUID = "819591c4247e455ea945fac5ca6e11c8"
L1_COMPONENT_ID = "e1385"
ROUTE_IDS = ("e1163", "e1169", "e1171")
MIL_TO_MM = 0.0254


def read_native_pcb(path: Path) -> tuple[dict, list[dict]]:
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("Smart_Plugs.epru").decode("utf-8")

    decoder = JSONDecoder()
    objects = []
    offset = 0
    while offset < len(payload):
        while offset < len(payload) and (
            payload[offset].isspace() or payload[offset] == "|"
        ):
            offset += 1
        if offset == len(payload):
            break
        item, offset = decoder.raw_decode(payload, offset)
        objects.append(item)

    for index in range(0, len(objects) - 1, 2):
        header = objects[index]
        body = objects[index + 1]
        if (
            isinstance(header, dict)
            and header.get("type") == "DOCHEAD"
            and isinstance(body, dict)
            and body.get("docType") == "PCB"
            and body.get("uuid") == PCB_UUID
        ):
            records = []
            for record_index in range(index + 2, len(objects) - 1, 2):
                record_header = objects[record_index]
                record_body = objects[record_index + 1]
                if (
                    isinstance(record_header, dict)
                    and record_header.get("type") == "DOCHEAD"
                ):
                    break
                if isinstance(record_header, dict) and isinstance(record_body, dict):
                    records.append({"header": record_header, "body": record_body})
            return body, records

    raise ValueError(f"PCB document {PCB_UUID} not found in {path}")


def get_route(records: list[dict]) -> tuple[dict, list[dict]]:
    components = [
        record["body"]
        for record in records
        if record["header"].get("type") == "COMPONENT"
        and record["header"].get("id") == L1_COMPONENT_ID
    ]
    if len(components) != 1:
        raise ValueError(f"Expected one L1 component record, found {len(components)}")

    lines = {
        record["header"].get("id"): record["body"]
        for record in records
        if record["header"].get("type") == "LINE"
        and record["header"].get("id") in ROUTE_IDS
    }
    if set(lines) != set(ROUTE_IDS):
        raise ValueError(f"Could not find all selected route segments: {set(lines)}")
    if any(
        line.get("netName") != "$L1_3"
        or line.get("layerId") != 1
        or not math.isclose(line.get("width", 0) * MIL_TO_MM, 1.0, abs_tol=0.02)
        for line in lines.values()
    ):
        raise ValueError("Selected route is not the expected 1 mm top-layer L1_3 net")

    ordered = [lines[line_id] for line_id in ROUTE_IDS]
    for previous, following in zip(ordered, ordered[1:]):
        if not (
            math.isclose(previous["endX"], following["startX"], abs_tol=1e-4)
            and math.isclose(previous["endY"], following["startY"], abs_tol=1e-4)
        ):
            raise ValueError("Selected L1_3 route segments are not contiguous")
    return components[0], ordered


def main(setup_only: bool = False, max_timesteps: int = 250000) -> None:
    component, source_lines = get_route(read_native_pcb(SOURCE)[1])
    origin_x = source_lines[0]["startX"]
    origin_y = source_lines[0]["startY"]
    width_mm = source_lines[0]["width"] * MIL_TO_MM
    route_points = []
    for line in source_lines:
        start = (
            (line["startX"] - origin_x) * MIL_TO_MM,
            (line["startY"] - origin_y) * MIL_TO_MM,
        )
        stop = (
            (line["endX"] - origin_x) * MIL_TO_MM,
            (line["endY"] - origin_y) * MIL_TO_MM,
        )
        if not route_points:
            route_points.append(start)
        route_points.append(stop)

    route_length = sum(
        math.dist(start, stop) for start, stop in zip(route_points, route_points[1:])
    )
    substrate_thickness = 1.6
    dielectric_constant = 4.2
    loss_tangent = 0.02
    center_frequency = 1.05e9
    bandwidth = 1.9e9
    mesh_spacing_mm = 0.5
    substrate_width = 8.0
    port_extension = 6.0
    x_bounds = (-6.0, route_length + 6.0)
    y_bounds = (-10.0, 10.0)
    z_bounds = (-substrate_thickness, 8.0)

    run_root = Path(__file__).resolve().parent / "runs"
    run_path = run_root / datetime.now().strftime("l1_route_%Y%m%d_%H%M%S")
    run_path.mkdir(parents=True, exist_ok=False)

    fdtd = openEMS(NrTS=max_timesteps, EndCriteria=1e-4)
    fdtd.SetGaussExcite(center_frequency, bandwidth)
    fdtd.SetBoundaryCond(["PML_8", "PML_8", "PML_8", "PML_8", "PEC", "MUR"])

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)

    substrate = csx.AddMaterial(
        "Assumed_FR4",
        epsilon=dielectric_constant,
        kappa=(
            2
            * math.pi
            * center_frequency
            * 8.8541878128e-12
            * dielectric_constant
            * loss_tangent
        ),
    )
    substrate.AddBox(
        start=[-port_extension, -substrate_width / 2, -substrate_thickness],
        stop=[route_length + port_extension, substrate_width / 2, 0.0],
        priority=0,
    )

    ground = csx.AddMetal("Assumed_PEC_Return_Plane")
    ground.AddBox(
        start=[-port_extension, -substrate_width / 2, -substrate_thickness],
        stop=[route_length + port_extension, substrate_width / 2, -substrate_thickness],
        priority=10,
    )
    trace = csx.AddMetal("Native_Width_Straightened_Trace_Coupon")
    trace.AddBox(
        start=[0.0, -width_mm / 2, 0.0],
        stop=[route_length, width_mm / 2, 0.0],
        priority=10,
    )

    for axis, bounds in (("x", x_bounds), ("y", y_bounds)):
        mesh.AddLine(
            axis,
            np.arange(bounds[0], bounds[1] + mesh_spacing_mm / 2, mesh_spacing_mm),
        )
    mesh.AddLine(
        "z",
        np.arange(z_bounds[0], z_bounds[1] + mesh_spacing_mm / 2, mesh_spacing_mm),
    )
    mesh.AddLine("z", [0.0, -substrate_thickness])

    input_port = fdtd.AddMSLPort(
        1,
        trace,
        start=[-port_extension, -width_mm / 2, 0.0],
        stop=[0.0, width_mm / 2, -substrate_thickness],
        prop_dir="x",
        exc_dir="z",
        excite=1.0,
        FeedShift=5.0,
        MeasPlaneShift=port_extension - 0.5,
        priority=10,
    )
    output_port = fdtd.AddMSLPort(
        2,
        trace,
        start=[route_length + port_extension, -width_mm / 2, 0.0],
        stop=[route_length, width_mm / 2, -substrate_thickness],
        prop_dir="x",
        exc_dir="z",
        excite=0.0,
        MeasPlaneShift=port_extension - 0.5,
        priority=10,
    )

    fdtd.AddEdges2Grid(
        dirs="xy",
        properties=[trace, ground],
        metal_edge_res=mesh_spacing_mm / 2,
    )
    mesh.SmoothMeshLines("all", mesh_spacing_mm, 1.4)

    csx.Write2XML(str(run_path / "l1_route_pilot.xml"))
    fdtd.Run(
        str(run_path),
        cleanup=False,
        setup_only=setup_only,
        verbose=1,
        numThreads=4,
        dump_statistics=True,
    )
    if setup_only:
        print(f"Setup-only artifacts: {run_path}")
        return

    frequencies = np.linspace(100e6, 2e9, 381)
    input_port.CalcPort(str(run_path), frequencies)
    output_port.CalcPort(str(run_path), frequencies)
    port_reference_impedance = np.asarray(input_port.Z_ref)
    if port_reference_impedance.shape != frequencies.shape:
        raise ValueError(
            "Expected one extracted input-port reference impedance per "
            f"frequency, got shape {port_reference_impedance.shape}"
        )
    if not np.all(np.isfinite(port_reference_impedance)):
        raise ValueError("Input-port reference impedance contains non-finite values")
    s11 = input_port.uf_ref / input_port.uf_inc
    s21 = output_port.uf_ref / input_port.uf_inc
    stats = np.loadtxt(run_path / "openEMS_run_stats.txt", skiprows=1)
    if stats.ndim == 1:
        stats = stats.reshape(1, -1)
    summary_lines = (run_path / "openEMS_stats.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    iteration_summary = next(
        (line for line in summary_lines if "% number of iterations" in line), None
    )
    if iteration_summary is None:
        raise ValueError("Could not find the solver iteration count in openEMS_stats.txt")
    timestep_count = int(iteration_summary.split("%", 1)[0].strip())
    sampled_energy_ratio = float(stats[-1, 3] / np.max(stats[:, 3]))
    # A successful run ending below its cap indicates the solver energy criterion was met.
    end_criteria_reached = timestep_count < max_timesteps
    solver_status = (
        "end_criteria_reached"
        if end_criteria_reached
        else "unconverged_max_timesteps"
    )
    with (run_path / "s_parameters.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "frequency_hz",
                "port_z_ref_real_ohm",
                "port_z_ref_imag_ohm",
                "s11_db",
                "s21_db",
            ]
        )
        writer.writerows(
            zip(
                frequencies,
                port_reference_impedance.real,
                port_reference_impedance.imag,
                20 * np.log10(np.maximum(np.abs(s11), 1e-15)),
                20 * np.log10(np.maximum(np.abs(s21), 1e-15)),
            )
        )

    fig, axis = plt.subplots(figsize=(8, 4.5), tight_layout=True)
    axis.plot(frequencies / 1e9, 20 * np.log10(np.maximum(np.abs(s11), 1e-15)), label="S11")
    axis.plot(frequencies / 1e9, 20 * np.log10(np.maximum(np.abs(s21), 1e-15)), label="S21")
    axis.set(xlabel="Frequency (GHz)", ylabel="Magnitude (dB)", xlim=(0.1, 2.0))
    if not end_criteria_reached:
        axis.set_title("UNCONVERGED — exploratory coupon only")
    axis.grid(True)
    axis.legend()
    fig.savefig(run_path / "s_parameters.png", dpi=160)
    plt.close(fig)

    sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    metadata = {
        "scope": "exploratory transmission-line pilot; not a product EMC prediction",
        "native_project_archive": str(SOURCE),
        "native_project_sha256": sha256,
        "pcb_document_uuid": PCB_UUID,
        "l1_component_record_id": L1_COMPONENT_ID,
        "l1_component_native_position_mil": [
            component["x"],
            component["y"],
        ],
        "included_route_ids": list(ROUTE_IDS),
        "included_net": "$L1_3",
        "route_width_mm": width_mm,
        "native_route_points_local_mm": route_points,
        "straight_coupon_length_mm": route_length,
        "solver": "openEMS",
        "openems_version": getattr(openems_package, "__version__", "unknown"),
        "csxcad_version": getattr(csxcad_package, "__version__", "unknown"),
        "mesh_spacing_mm": mesh_spacing_mm,
        "mesh_spacing_is_converged": False,
        "solver_status": solver_status,
        "solver_end_criteria_reached": end_criteria_reached,
        "final_energy_to_sampled_peak_energy_ratio": sampled_energy_ratio,
        "timestep_count": timestep_count,
        "maximum_timestep_limit": max_timesteps,
        "excitation": {
            "type": "Gaussian microstrip-port excitation",
            "center_hz": center_frequency,
            "bandwidth_hz": bandwidth,
            "frequency_sweep_hz": [100e6, 2e9],
            "port_reference_impedance": {
                "frequency_dependent": True,
                "real_range_ohm": [
                    float(np.min(port_reference_impedance.real)),
                    float(np.max(port_reference_impedance.real)),
                ],
                "imaginary_range_ohm": [
                    float(np.min(port_reference_impedance.imag)),
                    float(np.max(port_reference_impedance.imag)),
                ],
                "per_frequency_values_csv": "s_parameters.csv",
            },
        },
        "assumptions": {
            "board_thickness_mm": substrate_thickness,
            "relative_permittivity": dielectric_constant,
            "loss_tangent": loss_tangent,
            "substrate_width_mm": substrate_width,
            "port_extension_mm": port_extension,
            "copper": "PEC; copper thickness and losses not represented",
            "return": "continuous bottom reference plane assumed; not imported from the PCB",
            "trace_geometry": (
                "straightened coupon preserving total native path length and width; "
                "native bends and surrounding layout omitted"
            ),
        },
        "omitted": [
            "L1 common-mode choke electrical/parasitic model",
            "C2 and all other components",
            "remaining PCB copper, pours, vias, enclosure, and cables",
            "validated switching-noise source and operating case",
        ],
        "result_files": [
            "l1_route_pilot.xml",
            "s_parameters.csv",
            "s_parameters.png",
        ],
    }
    (run_path / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Pilot artifacts: {run_path}")
    print(f"Source SHA-256: {sha256}")
    print(f"Maximum timestep limit: {max_timesteps}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="validate solver geometry and ports without time-stepping",
    )
    parser.add_argument(
        "--max-timesteps",
        type=int,
        default=250000,
        help="maximum FDTD steps before the solver stops (default: 250000)",
    )
    args = parser.parse_args()
    if args.max_timesteps <= 0:
        parser.error("--max-timesteps must be a positive integer")
    main(setup_only=args.setup_only, max_timesteps=args.max_timesteps)
