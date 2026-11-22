"""Validate Stage 0 inputs before a project-specific openEMS extraction."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from importlib.metadata import version
from pathlib import Path

EMC_ROOT = Path(__file__).resolve().parents[2]
if str(EMC_ROOT) not in sys.path:
    sys.path.insert(0, str(EMC_ROOT))

from emc_sim.gerber_import import (
    GerberImportError,
    import_gerbers,
    validate_layer_configuration,
    write_overlay_png,
)
from emc_sim.manifest import sha256_file, verify_manifest
from emc_sim.reporting import create_run_directory, write_report, write_run_metadata
from emc_sim.candidate_healing import heal_candidate_copper


CANDIDATE_STAMP = "CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF"
END_CRITERION = 1e-4
MAX_TIMESTEPS = 350_000
DEFAULT_DIAGNOSTIC_STEPS = 1000
FREQUENCY_BAND_HZ = (30e6, 1e9)
FREQUENCY_POINTS = 81
HEALED_CROP_M = (.016, -.104, .042, -.0888)
PORT_HALF_WIDTH_MM = .4
HEALED_PADDING_MM = (15.2, 15.2, 15.2)
PORTS = (
    # Both ports are line minus neutral, on opposite sides of unpopulated L1.
    ((27.2, -92.4, 1.2), (21.2, -92.4, 2.0)),  # L1.1 to L1.4
    ((36.8, -95.2, 1.2), (38.0, -95.2, 2.0)),  # U1.1 to U1.2
)
PORT_FIXTURES_MM = (
    (27.2, -92.8, 27.6, -92.0), (20.8, -92.8, 21.2, -92.0),
    (36.6, -95.6, 36.8, -94.8), (38.0, -95.6, 38.2, -94.8),
)


def _validate_candidate_configuration(configuration, stackup, candidate):
    if set(configuration.gerber_sources) != {"Top", "Bottom"}:
        raise GerberImportError("Candidate model requires exactly Top and Bottom copper")
    layers = {layer.name: layer for layer in configuration.copper_layers}
    for name, elevation in (("Top", .0016), ("Bottom", 0.0)):
        if not math.isclose(layers[name].z_m, elevation, abs_tol=1e-12):
            raise GerberImportError(f"Unexpected {name} elevation")
        if not math.isclose(layers[name].thickness_m, 35e-6, abs_tol=1e-12):
            raise GerberImportError(f"Unexpected {name} copper thickness")
    dielectric = stackup.get("dielectrics")
    if (stackup.get("board_thickness_mm") != 1.6 or not isinstance(dielectric, list)
        or len(dielectric) != 1 or dielectric[0].get("epsilon_r") != 4.2
        or dielectric[0].get("loss_tangent") != .02):
        raise GerberImportError("Candidate FR4 assumptions do not match model parameters")
    if configuration.crop_bbox_m is None or any(
        not math.isclose(a, b, abs_tol=1e-12) for a, b in
        zip(configuration.crop_bbox_m, (.016, -.106, .062, -.080))
    ):
        raise GerberImportError("Candidate crop must match the configured L1–U1 window")
    prefix = "MCP_CANDIDATE_20261121_1753_MAIN_OMRON_"
    evidence = json.loads((candidate / "candidate_evidence.json").read_text(encoding="utf-8"))
    expected = {entry["path"]: entry["sha256"] for entry in evidence["files"]}
    for suffix in ("Gerbers.zip", "Netlist.pads", "PnP.csv"):
        name = prefix + suffix
        if expected.get(name) != sha256_file(candidate / name):
            raise GerberImportError(f"Candidate source SHA-256 mismatch: {name}")
    expected_paths = {
        "Top": "Gerber_TopLayer.GTL", "Bottom": "Gerber_BottomLayer.GBL",
        "PTH": "Drill_PTH_Through.DRL", "PTH_vias": "Drill_PTH_Through_Via.DRL",
        "probe": "FlyingProbeTesting.json",
    }
    configured = {**configuration.gerber_sources,
                  **{drill.name: Path(drill.source) for drill in configuration.drill_sources},
                  "probe": candidate / "gerbers" / expected_paths["probe"]}
    if set(configured) != set(expected_paths):
        raise GerberImportError("Unexpected candidate Gerber/drill configuration")
    with zipfile.ZipFile(candidate / (prefix + "Gerbers.zip")) as archive:
        for name, path in configured.items():
            path = Path(path)
            if path.resolve() != (candidate / "gerbers" / expected_paths[name]).resolve():
                raise GerberImportError(f"Unexpected candidate source path for {name}")
            if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(
                    archive.read(expected_paths[name])).digest():
                raise GerberImportError(f"Extracted candidate file differs from ZIP: {name}")


def _candidate_board(configuration):
    return import_gerbers(
        configuration.gerber_sources, configuration.copper_layers,
        drill_sources=configuration.drill_sources, crop_bbox_m=configuration.crop_bbox_m,
    )


def _healed_candidate_board(configuration):
    kwargs = {"crop_bbox_m": HEALED_CROP_M}
    original = import_gerbers(
        configuration.gerber_sources, configuration.copper_layers,
        drill_sources=configuration.drill_sources, **kwargs,
    )
    uncut = import_gerbers(configuration.gerber_sources, configuration.copper_layers, **kwargs)
    holes = _round_plated_holes(original)
    healed, squares, metrics = heal_candidate_copper(original, uncut, holes, hole_grid_m=.0004)
    return original, healed, holes, squares, metrics


def _with_port_fixtures(board):
    from shapely.geometry import box

    top = board.layer("Top")
    geometry = top.geometry
    for coordinates in PORT_FIXTURES_MM:
        fixture = box(*(value / 1000 for value in coordinates)).buffer(1e-6, join_style="mitre")
        touching = [part for part in top.polygons if fixture.intersects(part)]
        if len(touching) != 1 or fixture.intersection(touching[0]).area <= 0:
            raise GerberImportError("Each port fixture must overlap exactly one copper island")
        geometry = geometry.union(fixture)
    if len(list(getattr(geometry, "geoms", (geometry,)))) != len(top.polygons):
        raise GerberImportError("Port fixtures merged copper islands")
    replacement = replace(top, geometry=geometry)
    return replace(board, layers=tuple(replacement if layer.name == "Top" else layer
                                       for layer in board.layers))


def _round_plated_holes(board):
    """Return local plated through holes; reject clipped or non-round holes."""
    holes = {}
    for drill in board.drill_files:
        if drill.plating_status != "plated" or set(drill.affected_layers) != {"Top", "Bottom"}:
            raise GerberImportError("Only explicitly plated Top-to-Bottom holes are supported")
        for polygon in getattr(drill.geometry, "geoms", (drill.geometry,)):
            if polygon.is_empty:
                continue
            if polygon.geom_type != "Polygon" or polygon.interiors:
                raise GerberImportError("Unsupported plated hole geometry")
            x0, y0, x1, y1 = polygon.bounds
            radius = (x1 - x0) / 2
            if radius <= 0 or abs((y1 - y0) - 2 * radius) > 2e-6:
                raise GerberImportError("Clipped or non-round plated hole")
            if abs(polygon.area / (math.pi * radius * radius) - 1) > .01:
                raise GerberImportError("Unsupported non-circular plated drill")
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            holes[(round(x, 9), round(y, 9), round(radius, 9))] = (x, y, radius)
    if not holes:
        raise GerberImportError("No plated through holes in model crop")
    return tuple(holes.values())


def _validate_port_geometry(board, probe_file, holes):
    import shapely
    from shapely.geometry import LineString, Point, box
    from shapely.ops import unary_union

    probe = json.loads(probe_file.read_text(encoding="utf-8"))
    if probe.get("lengthUnit") != "mil":
        raise GerberImportError("Candidate probe coordinates must be in mil")
    rows = [dict(zip(probe["pins"]["fields"], row)) for row in probe["pins"]["rows"]]
    pin_rows = {}
    for row in rows:
        name = row["PIN_NAME"]
        if name in pin_rows:
            if any(row[key] != pin_rows[name][key] for key in ("PIN_X", "PIN_Y", "NET_NAME")):
                raise GerberImportError(f"Conflicting duplicate probe data for {name}")
        else:
            pin_rows[name] = row
    top = board.layer("Top").geometry
    mapped = []
    port_pins = (
        (("L1_1", "$C2_1"), ("L1_4", "$C2_2")),
        (("U1_1", "$L1_2"), ("U1_2", "$L1_3")),
    )
    for (start, stop), pins in zip(PORTS, port_pins):
        a = Point(start[0] / 1000, start[1] / 1000)
        b = Point(stop[0] / 1000, stop[1] / 1000)
        islands_a = [p for p in board.layer("Top").polygons if p.covers(a)]
        islands_b = [p for p in board.layer("Top").polygons if p.covers(b)]
        if len(islands_a) != 1 or len(islands_b) != 1 or islands_a[0].equals(islands_b[0]):
            raise GerberImportError("Port endpoints must touch two distinct top copper islands")
        for island, (pin, expected_net) in zip((islands_a[0], islands_b[0]), pins):
            row = pin_rows[pin]
            location = Point(row["PIN_X"] * 0.0000254, row["PIN_Y"] * 0.0000254)
            radius = float(row["HOLE_SIZE"]) * 0.0000254 / 2
            if row["NET_NAME"] != expected_net or island.distance(location) > radius + 2e-6:
                raise GerberImportError(f"Port island does not match probe pin {pin}/{expected_net}")
        mapped.append((islands_a[0], islands_b[0]))
        crossing = shapely.set_precision(top, 0).intersection(LineString([a, b]))
        endpoints = [shapely.set_precision(island, 0).buffer(1e-10)
                     for island in (islands_a[0], islands_b[0])]
        if any(not any(island.covers(part) for island in endpoints)
               for part in getattr(crossing, "geoms", (crossing,))):
            raise GerberImportError("A port crosses an unrelated copper island")
        source_box = box(min(start[0], stop[0]) / 1000,
                         (start[1] - PORT_HALF_WIDTH_MM) / 1000,
                         max(start[0], stop[0]) / 1000,
                         (start[1] + PORT_HALF_WIDTH_MM) / 1000)
        fixtures = unary_union([box(*(v / 1000 for v in bounds)).buffer(1e-6, join_style="mitre")
                                for bounds in PORT_FIXTURES_MM])
        if shapely.set_precision(top, 0).intersection(source_box).difference(
                fixtures.buffer(1e-10)).area > 1e-18:
            raise GerberImportError("Port source volume overlaps copper beyond its fixtures")
    layers = [board.layer("Top"), board.layer("Bottom")]
    shapes = [(layer.name, polygon) for layer in layers for polygon in layer.polygons]
    parent = list(range(len(shapes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for x, y, radius in holes:
        ring = Point(x, y).buffer(radius + 25e-6)
        neighbors = [i for i, (_, polygon) in enumerate(shapes)
                     if polygon.distance(ring) < 1e-9]
        for neighbor in neighbors[1:]:
            parent[find(neighbor)] = find(neighbors[0])
    port_roots = [
        find(next(j for j, (name, polygon) in enumerate(shapes)
                  if name == "Top" and polygon.equals(island)))
        for pair in mapped for island in pair
    ]
    if len(set(port_roots)) != 4:
        raise GerberImportError("L1 input and output nets must remain isolated with the choke unpopulated")
    for index, pin in enumerate(("L1_2", "L1_3")):
        row = pin_rows[pin]
        location = Point(row["PIN_X"] * 0.0000254, row["PIN_Y"] * 0.0000254)
        radius = float(row["HOLE_SIZE"]) * 0.0000254 / 2
        matching = [find(j) for j, (name, polygon) in enumerate(shapes)
                    if name == "Top" and polygon.distance(location) <= radius + 2e-6]
        if row["NET_NAME"] != port_pins[1][index][1] or port_roots[2 + index] not in matching:
            raise GerberImportError(f"Port output copper is not connected to {pin}")


def _check_mesh_grading(lines, growth=1.4):
    import numpy as np

    intervals = np.diff(np.asarray(lines, dtype=float))
    if len(intervals) < 2 or not np.all(np.isfinite(intervals)) or np.any(intervals <= 0):
        raise RuntimeError("Mesh lines must be finite and strictly increasing")
    ratios = np.maximum(intervals[1:] / intervals[:-1], intervals[:-1] / intervals[1:])
    if float(np.max(ratios)) > growth + 1e-6:
        raise RuntimeError(f"Mesh grading exceeds {growth}: {float(np.max(ratios))}")


def _graded_axis(anchors, maximum_spacing):
    """Keep geometry anchors while grading both sides of each interval."""
    import numpy as np

    values = np.sort(np.asarray(anchors, dtype=float))
    if not np.all(np.isfinite(values)) or not math.isfinite(maximum_spacing) or maximum_spacing <= 0:
        raise ValueError("Invalid mesh anchors or maximum spacing")
    values = values[np.r_[True, np.diff(values) > 1e-10]]
    if len(values) < 2:
        raise ValueError("At least two distinct mesh anchors are required")
    gaps = np.diff(values)
    ends = np.minimum(np.r_[gaps[0], gaps], np.r_[gaps, gaps[-1]])
    ends = np.minimum(ends, maximum_spacing)
    left_caps, right_caps = ends[:-1].copy(), ends[1:].copy()
    for _ in range(200):
        pieces = []
        for i, length in enumerate(gaps):
            for count in range(1, 10001):
                index = np.arange(count)
                widths = np.minimum.reduce([
                    np.full(count, maximum_spacing),
                    left_caps[i] * np.power(1.3, index),
                    right_caps[i] * np.power(1.3, index[::-1]),
                ])
                total = float(np.sum(widths))
                if total >= length:
                    pieces.append(widths * (length / total))
                    break
            else:
                raise RuntimeError("Graded mesh exceeded 10,000 cells in one interval")
        changed = False
        for i in range(len(pieces) - 1):
            left, right = pieces[i][-1], pieces[i + 1][0]
            if left > 1.4 * right * (1 + 1e-8):
                right_caps[i] = min(right_caps[i], 1.39 * right)
                changed = True
            if right > 1.4 * left * (1 + 1e-8):
                left_caps[i + 1] = min(left_caps[i + 1], 1.39 * left)
                changed = True
        if not changed:
            break
    else:
        raise RuntimeError("Geometric mesh grading did not converge")
    lines = [values[0]]
    for i, widths in enumerate(pieces):
        lines.extend((values[i] + np.cumsum(widths)).tolist())
        lines[-1] = values[i + 1]
    _check_mesh_grading(lines)
    return lines


def _air_widths(padding, inner_step):
    import numpy as np

    if not math.isfinite(padding) or not math.isfinite(inner_step) or padding <= 0 or inner_step <= 0:
        raise ValueError("Air padding and inner step must be positive and finite")
    for count in range(1, 200):
        factors = np.power(1.3, np.arange(count))
        low, high = inner_step, inner_step * 1.4
        if np.minimum(low * factors, .0015).sum() > padding + 1e-12:
            continue
        if np.minimum(high * factors, .0015).sum() < padding - 1e-12:
            continue
        for _ in range(60):
            middle = (low + high) / 2
            if np.minimum(middle * factors, .0015).sum() < padding:
                low = middle
            else:
                high = middle
        widths = np.minimum((low + high) / 2 * factors, .0015)
        if math.isclose(float(widths.sum()), padding, abs_tol=1e-12):
            _check_mesh_grading(np.r_[0, np.cumsum(np.r_[inner_step, widths])])
            return widths
    raise RuntimeError("Cannot create graded air mesh within declared cell limits")


def _healed_axis(low, high, spacing, padding):
    import numpy as np

    cells = round((high - low) / spacing)
    if cells < 1 or not math.isclose(low + cells * spacing, high, abs_tol=1e-12):
        raise ValueError("Healed crop must be an integer number of mesh cells")
    core = np.linspace(low, high, cells + 1)
    widths = _air_widths(padding, spacing)
    lines = np.r_[low - np.cumsum(widths)[::-1], core, high + np.cumsum(widths)]
    _check_mesh_grading(lines)
    return lines


def _square_barrel_audit(squares, geometry_path, pec_path):
    holes = []
    for square in squares:
        xmin, ymin, xmax, ymax = square.bounds
        if not math.isclose(xmax - xmin, ymax - ymin, abs_tol=1e-12):
            raise RuntimeError("Simplified plated hole is not square")
        holes.append(((xmin + xmax) / 2, (ymin + ymax) / 2,
                      (xmax - xmin) / 2 - 12.5e-6))
    result = _audit_barrel_edges(holes, geometry_path, pec_path)
    result["method"] = "PEC z-edges at the four midpoints of each simplified square barrel"
    result["limitation"] = "Does not prove complete barrel or pad connectivity, or the real plating geometry."
    return result


def _cluster_hole_centers(values, maximum_displacement=8e-6):
    """Share a grid line between nearby hole centers without moving the holes."""
    ordered = sorted(float(value) for value in values)
    if not all(math.isfinite(value) for value in ordered):
        raise ValueError("Hole centers must be finite")
    groups = []
    for value in ordered:
        if groups and value - groups[-1][0] <= 2 * maximum_displacement:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [(group[0] + group[-1]) / 2 for group in groups]


def _validate_barrel_mesh(holes, x_lines, y_lines):
    """Require one z-directed mesh edge through each cardinal barrel side."""
    import numpy as np

    xs, ys = np.asarray(x_lines), np.asarray(y_lines)
    if (xs.ndim != 1 or ys.ndim != 1 or not np.all(np.isfinite(xs))
            or not np.all(np.isfinite(ys))):
        raise ValueError("Invalid barrel mesh lines")
    for x, y, radius in holes:
        center_x = xs[np.argmin(np.abs(xs - x))]
        center_y = ys[np.argmin(np.abs(ys - y))]
        candidates = [
            (xs[np.argmin(np.abs(xs - target))], center_y)
            for target in (x - radius - 12.5e-6, x + radius + 12.5e-6)
        ] + [
            (center_x, ys[np.argmin(np.abs(ys - target))])
            for target in (y - radius - 12.5e-6, y + radius + 12.5e-6)
        ]
        if any(not (radius < math.hypot(px - x, py - y) < radius + 25e-6)
               for px, py in candidates):
            raise RuntimeError(f"Barrel has an unsampled cardinal side at ({x}, {y}) m")


def _add_candidate_copper(csx, board):
    import shapely
    from shapely.geometry import LineString, Polygon
    from shapely.ops import split

    for layer in board.layers:
        metal = csx.AddMetal(layer.name)
        for original_polygon in layer.polygons:
            polygon = shapely.set_precision(original_polygon, 0)
            pending = [polygon]
            parts = []
            while pending:
                piece = pending.pop()
                if not piece.interiors:
                    parts.append(piece)
                    continue
                x = Polygon(piece.interiors[0]).representative_point().x
                xmin, ymin, xmax, ymax = piece.bounds
                margin = max(xmax - xmin, ymax - ymin, 1e-6)
                cut = LineString([(x, ymin - margin), (x, ymax + margin)])
                children = tuple(split(piece, cut).geoms)
                if (len(children) < 2 or any(child.geom_type != "Polygon" for child in children)
                    or max(len(child.interiors) for child in children) >= len(piece.interiors)):
                    raise GerberImportError("Copper cutout partition did not make progress")
                pending.extend(children)
            while True:
                merged_pair = False
                for i, first in enumerate(parts):
                    for j in range(i + 1, len(parts)):
                        if not first.intersects(parts[j]):
                            continue
                        merged = first.union(parts[j])
                        if merged.geom_type == "Polygon" and not merged.interiors and merged.is_valid:
                            parts[i] = merged
                            parts.pop(j)
                            merged_pair = True
                            break
                    if merged_pair:
                        break
                if not merged_pair:
                    break
            if not parts or any(part.geom_type != "Polygon" or part.interiors for part in parts):
                raise GerberImportError("Copper decomposition produced invalid polygons")
            reconstructed = shapely.union_all(parts)
            if reconstructed.symmetric_difference(polygon).area > max(polygon.area * 1e-10, 1e-30):
                raise GerberImportError("Copper partition changed geometry or hole area")
            for part in parts:
                coordinates = list(part.exterior.coords)[:-1]
                metal.AddPolygon([[p[0] for p in coordinates], [p[1] for p in coordinates]],
                                 norm_dir="z", elevation=layer.z_m, priority=10)


def _sample_yee_midpoints(board, geometry_path):
    import numpy as np
    import shapely

    mesh = ET.parse(geometry_path).find(".//RectilinearGrid")
    if mesh is None:
        raise RuntimeError("Serialized mesh is missing")
    x = np.fromstring(mesh.find("XLines").text, sep=",")
    y = np.fromstring(mesh.find("YLines").text, sep=",")
    _check_mesh_grading(x)
    _check_mesh_grading(y)
    xx, yy = np.meshgrid((x[:-1] + x[1:]) / 2, y)
    xxx, yyy = np.meshgrid(x, (y[:-1] + y[1:]) / 2)
    points = shapely.points(np.r_[xx.ravel(), xxx.ravel()],
                            np.r_[yy.ravel(), yyy.ravel()])
    result = {}
    for layer in board.layers:
        missing = [polygon for polygon in layer.polygons
                   if not np.any(shapely.intersects(polygon, points))]
        result[layer.name] = {
            "copper_island_count": len(layer.polygons),
            "islands_without_candidate_midpoint": len(missing),
            "area_without_candidate_midpoint_m2": sum(p.area for p in missing),
            "total_copper_area_m2": layer.geometry.area,
        }
    return {
        "method": "2D geometric screen of x/y Yee-edge midpoint candidates; not verified against openEMS internal rasterization",
        "limitation": "Does not verify island shape, connectivity, z-directed edges, PEC edge assignment, or unused triangle warnings.",
        "layers": result,
    }


def _read_pec_dump(path):
    """Read the compressed VTK PolyData edge dump produced by openEMS 0.37."""
    import numpy as np

    root = ET.parse(path).getroot()
    if (root.get("type") != "PolyData" or root.get("byte_order") != "LittleEndian"
        or root.get("header_type") != "UInt32"
        or root.get("compressor") != "vtkZLibDataCompressor"):
        raise RuntimeError("Unsupported PEC dump encoding")
    appended = root.find("AppendedData")
    if appended is None or appended.get("encoding") != "base64":
        raise RuntimeError("Missing encoded PEC dump data")
    encoded = "".join((appended.text or "").split()).removeprefix("_")
    piece = root.find(".//Piece")
    if piece is None:
        raise RuntimeError("PEC dump has no PolyData piece")

    def array(element, dtype):
        if element is None or element.get("format") != "appended":
            raise RuntimeError("Missing appended PEC dump array")
        offset = int(element.get("offset"))
        block_count = struct.unpack("<I", base64.b64decode(encoded[offset:offset + 8])[:4])[0]
        if block_count > 10000:
            raise RuntimeError("Excessive PEC dump block count")
        header_bytes = (3 + block_count) * 4
        header_chars = ((header_bytes + 2) // 3) * 4
        header = base64.b64decode(encoded[offset:offset + header_chars])
        values = struct.unpack("<" + "I" * (3 + block_count), header)
        sizes = values[3:]
        compressed_size = sum(sizes)
        payload = base64.b64decode(encoded[offset + header_chars:
                                           offset + header_chars + ((compressed_size + 2) // 3) * 4])
        blocks, position = [], 0
        for size in sizes:
            blocks.append(zlib.decompress(payload[position:position + size]))
            position += size
        raw = b"".join(blocks)
        expected = 0 if not block_count else (block_count - 1) * values[1] + values[2]
        if len(raw) != expected:
            raise RuntimeError("PEC dump decompressed length mismatch")
        return np.frombuffer(raw, dtype=dtype)

    points = array(piece.find("./Points/DataArray"), "<f4").astype(float).reshape(-1, 3)
    lines = array(piece.find('./Lines/DataArray[@Name="connectivity"]'), "<i8")
    offsets = array(piece.find('./Lines/DataArray[@Name="offsets"]'), "<i8")
    if (len(lines) != 2 * len(offsets) or not np.array_equal(offsets, np.arange(2, len(lines) + 1, 2))
        or np.any(lines < 0) or np.any(lines >= len(points)) or not np.all(np.isfinite(points))):
        raise RuntimeError("PEC dump contains invalid line connectivity")
    return points, lines.reshape(-1, 2)


def _audit_pec_edges(board, geometry_path, pec_path):
    """Compare planar copper midpoint samples to the actual dumped PEC edges."""
    import numpy as np
    import shapely
    from scipy.spatial import cKDTree

    mesh = ET.parse(geometry_path).find(".//RectilinearGrid")
    if mesh is None:
        raise RuntimeError("Serialized mesh is missing")
    x = np.fromstring(mesh.find("XLines").text, sep=",")
    y = np.fromstring(mesh.find("YLines").text, sep=",")
    points, lines = _read_pec_dump(pec_path)
    ends = points[lines]
    delta = ends[:, 1] - ends[:, 0]
    midpoint = (ends[:, 0] + ends[:, 1]) / 2
    result = {}
    for layer in board.layers:
        same_z = np.isclose(ends[:, 0, 2], layer.z_m, atol=1e-8, rtol=0) & np.isclose(
            ends[:, 1, 2], layer.z_m, atol=1e-8, rtol=0)
        orientations = (
            ("x", (x[:-1] + x[1:]) / 2, y,
             same_z & (np.abs(delta[:, 0]) > 1e-10) & (np.abs(delta[:, 1]) < 1e-10)),
            ("y", x, (y[:-1] + y[1:]) / 2,
             same_z & (np.abs(delta[:, 1]) > 1e-10) & (np.abs(delta[:, 0]) < 1e-10)),
        )
        result[layer.name] = {}
        for direction, grid_x, grid_y, selected in orientations:
            xx, yy = np.meshgrid(grid_x, grid_y)
            expected = shapely.intersects_xy(layer.geometry, xx, yy)
            targets = np.column_stack((xx[expected], yy[expected]))
            actual = midpoint[selected, :2]
            distance = (cKDTree(actual).query(targets)[0] if len(actual)
                        else np.full(len(targets), np.inf))
            missed = targets[distance > 1e-8]
            extra_mask = shapely.distance(layer.geometry, shapely.points(actual)) > 1e-8
            extra = actual[extra_mask]
            in_port = np.zeros(len(extra), dtype=bool)
            if layer.name == "Top":
                for start, stop in PORTS:
                    in_port |= (
                        (extra[:, 0] >= min(start[0], stop[0]) / 1000 - 1e-8)
                        & (extra[:, 0] <= max(start[0], stop[0]) / 1000 + 1e-8)
                        & (extra[:, 1] >= (start[1] - PORT_HALF_WIDTH_MM) / 1000 - 1e-8)
                        & (extra[:, 1] <= (start[1] + PORT_HALF_WIDTH_MM) / 1000 + 1e-8)
                    )
            result[layer.name][direction] = {
                "expected_copper_midpoints": len(targets),
                "actual_pec_edges_on_plane": len(actual),
                "missing_expected_midpoints": len(missed),
                "first_missing_coordinates_mm": (missed[:20] * 1000).tolist(),
                "extra_pec_midpoints_outside_copper": len(extra),
                "extra_within_idealized_port_boxes": int(np.count_nonzero(in_port)),
                "extra_outside_port_boxes": int(np.count_nonzero(~in_port)),
                "first_extra_coordinates_mm": (extra[:20] * 1000).tolist(),
            }
    return {
        "method": "Planar copper Yee-edge midpoint candidates compared with openEMS PEC_dump.vtp edge midpoints; 10 nm matching tolerance.",
        "limitation": "Does not verify sub-cell copper shape, barrel connectivity, port validity, mesh convergence, or explain unused primitive warnings; extra port-box edges are idealized fixture metal.",
        "layers": result,
    }


def _audit_barrel_edges(holes, geometry_path, pec_path):
    """Check dumped PEC z-edges at each barrel's four cardinal samples."""
    import numpy as np

    if not holes:
        raise RuntimeError("No modeled barrels to audit")
    mesh = ET.parse(geometry_path).find(".//RectilinearGrid")
    if mesh is None:
        raise RuntimeError("Serialized mesh is missing")
    x = np.fromstring(mesh.find("XLines").text, sep=",")
    y = np.fromstring(mesh.find("YLines").text, sep=",")
    z = np.fromstring(mesh.find("ZLines").text, sep=",")
    z = z[(z >= -1e-12) & (z <= .0016 + 1e-12)]
    if len(z) < 2 or not (math.isclose(z[0], 0, abs_tol=1e-12)
                          and math.isclose(z[-1], .0016, abs_tol=1e-12)):
        raise RuntimeError("Serialized mesh does not span the assumed substrate")
    points, lines = _read_pec_dump(pec_path)
    ends = points[lines]
    delta = ends[:, 1] - ends[:, 0]
    z_edges = ends[(np.abs(delta[:, 2]) > 1e-10)
                   & (np.abs(delta[:, 0]) < 1e-10)
                   & (np.abs(delta[:, 1]) < 1e-10)]
    missing = []
    for hole_index, (hole_x, hole_y, radius) in enumerate(holes):
        cx = x[np.argmin(np.abs(x - hole_x))]
        cy = y[np.argmin(np.abs(y - hole_y))]
        cardinal = [(x[np.argmin(np.abs(x - target))], cy)
                    for target in (hole_x - radius - 12.5e-6, hole_x + radius + 12.5e-6)]
        cardinal += [(cx, y[np.argmin(np.abs(y - target))])
                     for target in (hole_y - radius - 12.5e-6, hole_y + radius + 12.5e-6)]
        for side, (sample_x, sample_y) in enumerate(cardinal):
            candidates = z_edges[(np.abs(z_edges[:, 0, 0] - sample_x) < 1e-8)
                                 & (np.abs(z_edges[:, 0, 1] - sample_y) < 1e-8)]
            for lower, upper in zip(z[:-1], z[1:]):
                forward = (np.isclose(candidates[:, 0, 2], lower, atol=1e-8, rtol=0)
                           & np.isclose(candidates[:, 1, 2], upper, atol=1e-8, rtol=0))
                backward = (np.isclose(candidates[:, 1, 2], lower, atol=1e-8, rtol=0)
                            & np.isclose(candidates[:, 0, 2], upper, atol=1e-8, rtol=0))
                if not np.any(forward | backward):
                    missing.append({"hole": hole_index, "side": side,
                                    "z_bounds_m": [float(lower), float(upper)]})
    return {
        "method": "openEMS dumped z-directed PEC edges at four cardinal mesh samples per modeled barrel",
        "hole_count": len(holes),
        "expected_segments": len(holes) * 4 * (len(z) - 1),
        "missing_segments": len(missing),
        "first_missing": missing[:20],
        "limitation": "Does not prove complete curved barrel fidelity, plating parameters, or connection to copper sheets.",
    }


def _benchmark_module():
    path = Path(__file__).with_name("01_verify_benchmark.py")
    spec = importlib.util.spec_from_file_location("emc_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_frequencies():
    import numpy as np

    return np.geomspace(*FREQUENCY_BAND_HZ, FREQUENCY_POINTS)


def _require_release_gates(metadata):
    if (metadata.get("solver_end_criteria_reached") is not True
        or metadata.get("solver_status") != "end_criteria_reached"):
        raise RuntimeError("Energy convergence is required before network release")
    for gate in ("mesh_convergence", "time_convergence", "boundary_convergence",
                 "passivity", "reciprocity"):
        if not isinstance(metadata.get(gate), dict) or metadata[gate].get("passed") is not True:
            raise RuntimeError(f"{gate} must pass before network release")


def _require_pec_fidelity(diagnostics):
    audit = diagnostics.get("pec_edge_audit", {}).get("layers", {})
    if set(audit) != {"Top", "Bottom"}:
        raise RuntimeError("Both copper layers require PEC edge audits")
    for layer in ("Top", "Bottom"):
        for direction in ("x", "y"):
            result = audit[layer].get(direction, {})
            if (not result.get("expected_copper_midpoints")
                or result.get("missing_expected_midpoints") != 0
                or result.get("extra_outside_port_boxes") != 0):
                raise RuntimeError(f"PEC copper edge audit failed for {layer}/{direction}")
    barrels = diagnostics.get("barrel_edge_audit", {})
    if not barrels.get("expected_segments") or barrels.get("missing_segments") != 0:
        raise RuntimeError("PEC barrel edge audit failed")


def _boundary_convergence(reference, expanded, tolerance=.05, reference_padding=(10, 10, 10),
                          expanded_padding=None):
    """Compare each independently expanded boundary against the reference."""
    import numpy as np

    reference = np.asarray(reference, dtype=complex)
    if (reference.ndim != 3 or reference.shape[1:] != (2, 2)
        or not reference.shape[0] or not np.all(np.isfinite(reference))
        or set(expanded) != {"expanded_x", "expanded_y", "expanded_z"}
        or not math.isfinite(tolerance) or tolerance <= 0):
        raise ValueError("Invalid boundary sensitivity inputs")
    changes = {}
    if expanded_padding is None:
        expanded_padding = {"expanded_x": [20, 10, 10],
                            "expanded_y": [10, 20, 10],
                            "expanded_z": [10, 10, 20]}
    if set(expanded_padding) != set(expanded):
        raise ValueError("Invalid boundary padding cases")
    for name, value in expanded.items():
        value = np.asarray(value, dtype=complex)
        if value.shape != reference.shape or not np.all(np.isfinite(value)):
            raise ValueError(f"Invalid boundary sensitivity matrix: {name}")
        changes[name] = float(np.max(
            np.abs(value - reference) / np.maximum(np.maximum(np.abs(reference), np.abs(value)), 1e-12)))
    return {"passed": max(changes.values()) <= tolerance,
            "tolerance": tolerance, "maximum_relative_changes": changes,
            "reference_padding_mm": list(reference_padding),
            "expanded_padding_mm": expanded_padding}


def _energy_upper_bound(log_text, stats_path, expected_steps, criterion):
    """Bound final/peak energy using sampled energies and solver-reported dB.

    The wall-clock samples may miss the initial peak. Each reported dB value
    bounds the historical peak; use the least favourable two-decimal rounding
    and the matching energy sample rather than treating a sampled peak as the
    true peak.
    """
    samples = {}
    for line in stats_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("%"):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise RuntimeError("Malformed openEMS energy sample")
        step = int(fields[1])
        try:
            decimal_energy = Decimal(fields[3])
            energy = float(decimal_energy)
            if not decimal_energy.is_finite() or decimal_energy <= 0:
                raise ValueError("nonpositive or nonfinite energy")
            rounding = float(Decimal("0.5").scaleb(decimal_energy.as_tuple().exponent))
        except (InvalidOperation, ValueError, OverflowError) as exc:
            raise RuntimeError("Invalid openEMS energy value") from exc
        if step in samples or not math.isfinite(energy) or energy <= 0 or not math.isfinite(rounding):
            raise RuntimeError("Invalid openEMS energy sample")
        samples[step] = (max(0., energy - rounding), energy + rounding)
    if not samples:
        raise RuntimeError("No openEMS energy samples")
    marker = re.findall(
        r"end-criteria of\s+([+-]?\d+\.\d{2})db reached after\s+(\d+)"
        r"\s+timesteps\s+\(\s*([+-]?\d+\.\d{2})db\s*\)",
        log_text, re.IGNORECASE)
    if len(marker) != 1:
        raise RuntimeError("Missing or ambiguous solver energy-stop marker")
    threshold_db, marker_step, final_db = marker[0]
    if (threshold_db != f"{10 * math.log10(criterion):.2f}"
        or int(marker_step) != expected_steps or max(samples) != expected_steps
        or 10 ** ((float(final_db) + .005) / 10) > criterion):
        raise RuntimeError("Solver energy-stop marker or final sample is inconsistent")
    pattern = re.compile(
        r"timestep:\s*(\d+).*?energy:\s*~([0-9.e+-]+)\s*"
        r"\(\s*([+-]?)\s*(\d+\.\d{2})\s*db\s*\)", re.IGNORECASE)
    peak_lower = 0.0
    matched_steps = set()
    for match in pattern.finditer(log_text):
        step = int(match.group(1))
        if step not in samples or step in matched_steps:
            raise RuntimeError("Solver energy log and samples disagree")
        logged_energy = Decimal(match.group(2))
        logged_rounding = Decimal("0.5").scaleb(logged_energy.as_tuple().exponent)
        if (float(logged_energy + logged_rounding) < samples[step][0]
            or float(logged_energy - logged_rounding) > samples[step][1]):
            raise RuntimeError("Solver energy log and samples disagree")
        db = float(match.group(4)) * (-1 if match.group(3) == "-" else 1)
        if db > 0.005:
            raise RuntimeError("Invalid positive normalized energy")
        if step == expected_steps and db != float(final_db):
            raise RuntimeError("Final logged energy differs from solver marker")
        peak_lower = max(peak_lower, samples[step][0] / (10 ** ((db + .005) / 10)))
        matched_steps.add(step)
    if expected_steps not in matched_steps or peak_lower <= 0:
        raise RuntimeError("Cannot bound the solver's peak energy")
    return samples[max(samples)][1] / peak_lower


def _validate_incident_spectrum(incident, voltage, current, source_field, source_length_m):
    """Validate pulse voltage DFTs against a nominal source-voltage integral."""
    import numpy as np

    if not math.isfinite(source_length_m) or source_length_m <= 0:
        raise ValueError("Source length must be finite and positive")
    incident, voltage, current, source = map(np.asarray, (incident, voltage, current, source_field))
    source = source * source_length_m
    if (incident.ndim != 1 or not incident.size
        or any(value.shape != incident.shape or not np.all(np.isfinite(value))
               for value in (incident, voltage, current, source))):
        raise RuntimeError("Excitation or port spectrum is invalid")
    magnitude = np.abs(incident)
    if (np.max(magnitude) == 0 or np.min(magnitude) < .01 * np.max(magnitude)
        or np.any(np.abs(source) == 0)
        or np.any(magnitude < 1e-4 * np.abs(source))
        or np.any(magnitude <= 1000 * np.finfo(np.float32).eps
                  * (np.abs(voltage) + 50 * np.abs(current)))):
        raise RuntimeError("Excitation spectrum is too weak or numerically ill-conditioned")
    return {"minimum_relative_band_amplitude": float(np.min(magnitude) / np.max(magnitude)),
            "minimum_incident_to_nominal_source_voltage_spectrum": float(np.min(magnitude / np.abs(source)))}


def _mesh_convergence_diagnostic(frequencies, matrices, plot_path):
    """Record failed mesh comparisons without exporting an unvalidated network."""
    import matplotlib.pyplot as plt
    import numpy as np

    pairs = ((0, 1, "coarse / medium"), (1, 2, "medium / fine"),
             (0, 2, "coarse / fine"))
    curves = [
        np.max(np.abs(matrices[a] - matrices[b])
               / np.maximum(np.maximum(np.abs(matrices[a]), np.abs(matrices[b])), 1e-12),
               axis=(1, 2))
        for a, b, _ in pairs
    ]
    changes = [float(np.max(curve)) for curve in curves]
    if max(changes) > .05:
        fig, ax = plt.subplots(figsize=(8, 5))
        for curve, (_, _, label) in zip(curves, pairs):
            ax.semilogx(frequencies, curve * 100, label=label)
        ax.axhline(5, color="black", linestyle="--", label="5% gate")
        ax.set(xlabel="Frequency (Hz)", ylabel="Maximum complex S relative change (%)",
               title="UNVALIDATED: mesh gate failed")
        ax.grid(True, which="both")
        ax.legend()
        fig.suptitle(CANDIDATE_STAMP, fontsize=8)
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
    return changes


def _assemble_network_waves(excitations):
    """Solve B = S A with a float32-aware inversion-conditioning screen."""
    import numpy as np

    if len(excitations) != 2:
        raise ValueError("Exactly two port excitations are required")
    waves = [np.asarray(value, dtype=complex) for value in excitations]
    if (waves[0].ndim != 3 or waves[0].shape[1:] != (2, 2)
        or not waves[0].shape[0] or waves[1].shape != waves[0].shape
        or any(not np.all(np.isfinite(value)) for value in waves)):
        raise ValueError("Invalid incident/reflected port waves")
    incident = np.stack([value[:, 0, :] for value in waves], axis=2)
    reflected = np.stack([value[:, 1, :] for value in waves], axis=2)
    condition = np.linalg.cond(incident)
    if (not np.all(np.isfinite(condition))
        or np.any(condition * np.finfo(np.float32).eps > 1e-4)):
        raise RuntimeError("Incident-wave matrix is singular or ill-conditioned")
    matrix = np.swapaxes(np.linalg.solve(
        np.swapaxes(incident, 1, 2), np.swapaxes(reflected, 1, 2)), 1, 2)
    if not np.all(np.isfinite(matrix)):
        raise RuntimeError("Non-finite S parameters")
    return matrix


def _run_candidate_excitation(board, holes, run_path, spacing_mm, excited_port, frequencies,
                              *, diagnostic_steps=None, padding_mm=(10, 10, 10),
                              end_criterion=END_CRITERION, squares=None, z_spacing_mm=.4):
    import numpy as np
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    benchmark = _benchmark_module()
    run_path.mkdir()
    csx = ContinuousStructure()
    timestep_limit = diagnostic_steps or MAX_TIMESTEPS
    if not math.isfinite(end_criterion) or not 0 < end_criterion <= END_CRITERION:
        raise ValueError("Energy criterion cannot be weaker than the baseline")
    fdtd = openEMS(NrTS=timestep_limit, EndCriteria=end_criterion)
    fdtd.SetCSX(csx)
    fdtd.SetGaussExcite(1.05e9, 1.9e9)
    fdtd.SetBoundaryCond(["MUR" if squares is None else "PML_8"] * 6)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1.0)
    xmin, ymin, xmax, ymax = board.crop_bbox_m
    if len(padding_mm) != 3 or any(not math.isfinite(v) or v <= 0 for v in padding_mm):
        raise ValueError("Boundary padding must contain three finite positive millimetre values")
    pad_x, pad_y, pad_z = (value / 1000 for value in padding_mm)
    substrate = csx.AddMaterial("assumed_FR4", epsilon=[4.2] * 3,
                                kappa=[2 * math.pi * 1.05e9 * 8.8541878128e-12 * 4.2 * 0.02] * 3)
    substrate.AddBox(start=[xmin, ymin, 0], stop=[xmax, ymax, 0.0016], priority=0)
    _add_candidate_copper(csx, board)
    hole_air = csx.AddMaterial("plated_hole_air", epsilon=[1.0] * 3)
    if squares is None:
        barrel = csx.AddMetal("assumed_25um_PTH_barrels")
        for x, y, radius in holes:
            hole_air.AddCylinder([x, y, 0], [x, y, .0016], radius, priority=2)
            barrel.AddCylindricalShell([x, y, 0], [x, y, .0016], radius + 12.5e-6,
                                       25e-6, priority=10)
    else:
        barrel = csx.AddMetal("ideal_square_PTH_walls")
        for opening in squares:
            x0, y0, x1, y1 = opening.bounds
            hole_air.AddBox([x0, y0, 0], [x1, y1, .0016], priority=2)
            wall_half = 10e-6
            for start, stop in (
                ([x0 - wall_half, y0, 0], [x0 + wall_half, y1, .0016]),
                ([x1 - wall_half, y0, 0], [x1 + wall_half, y1, .0016]),
                ([x0, y0 - wall_half, 0], [x1, y0 + wall_half, .0016]),
                ([x0, y1 - wall_half, 0], [x1, y1 + wall_half, .0016]),
            ):
                barrel.AddBox(start, stop, priority=10)
    ports = []
    for number, (start, stop) in enumerate(PORTS, 1):
        s = [start[0] / 1000, (start[1] - PORT_HALF_WIDTH_MM) / 1000, start[2] / 1000]
        t = [stop[0] / 1000, (stop[1] + PORT_HALF_WIDTH_MM) / 1000, stop[2] / 1000]
        ports.append(fdtd.AddLumpedPort(number, 50, s, t, "x",
                                        excite=int(number == excited_port), priority=9))
    if squares is None:
        anchors = {
            "x": [xmin - pad_x, xmin, xmax, xmax + pad_x] + [p[0] / 1000 for pair in PORTS for p in pair],
            "y": [ymin - pad_y, ymin, ymax, ymax + pad_y] +
                 [(p[1] + d) / 1000 for pair in PORTS for p in pair
                  for d in (-PORT_HALF_WIDTH_MM, 0, PORT_HALF_WIDTH_MM)],
        }
        anchors["x"].extend(_cluster_hole_centers([x for x, _, _ in holes]))
        anchors["y"].extend(_cluster_hole_centers([y for _, y, _ in holes]))
        for x, y, radius in holes:
            anchors["x"].extend([x - radius - 12.5e-6, x + radius + 12.5e-6])
            anchors["y"].extend([y - radius - 12.5e-6, y + radius + 12.5e-6])
        for axis in "xy":
            grid.AddLine(axis, _graded_axis(anchors[axis], spacing_mm / 1000))
        _validate_barrel_mesh(holes, grid.GetLines("x"), grid.GetLines("y"))
        grid.AddLine("z", np.linspace(0, .0016, 9))
        grid.AddLine("z", [p[2] / 1000 for pair in PORTS for p in pair])
        grid.AddLine("z", [-pad_z, .0016 + pad_z])
        grid.SmoothMeshLines("z", spacing_mm / 1000, 1.4)
    else:
        grid.AddLine("x", _healed_axis(xmin, xmax, spacing_mm / 1000, pad_x))
        grid.AddLine("y", _healed_axis(ymin, ymax, spacing_mm / 1000, pad_y))
        grid.AddLine("z", _healed_axis(0, .0016, z_spacing_mm / 1000, pad_z))
        for axis, low, high in (("x", xmin, xmax), ("y", ymin, ymax), ("z", 0, .0016)):
            lines = grid.GetLines(axis)
            if len(lines) < 18 or lines[8] > low - .003 or lines[-9] < high + .003:
                raise RuntimeError(f"PML interface is less than 3 mm from the {axis} crop")
    for axis in "xyz":
        _check_mesh_grading(grid.GetLines(axis))
    counts = [len(grid.GetLines(axis)) for axis in "xyz"]
    cells = math.prod(n - 1 for n in counts)
    csx.Write2XML(str(run_path / "geometry.xml"))
    if cells > 3_000_000:
        raise RuntimeError(f"Mesh has {cells} cells, exceeding the 3,000,000-cell resource cap")
    updates = cells * timestep_limit
    if updates > 250_000_000_000:
        raise RuntimeError(
            f"Mesh has {cells} cells ({counts} lines); the {timestep_limit}-step cap "
            f"allows {updates:,} cell-updates, exceeding the 250,000,000,000 resource budget"
        )
    log_path = run_path / "solver.log"
    old_dir = Path.cwd()
    out, err = os.dup(1), os.dup(2)
    try:
        with log_path.open("w", encoding="utf-8", buffering=1) as log:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            code = fdtd.Run(str(run_path), cleanup=False, verbose=1, numThreads=4,
                            dump_statistics=True, disable_dumps=True,
                            debug_PEC=True)
    finally:
        os.dup2(out, 1)
        os.dup2(err, 2)
        os.close(out)
        os.close(err)
        os.chdir(old_dir)
    stats = benchmark._parse_solver_stats(run_path)
    energy = stats.get("sampled_final_energy_to_peak_ratio")
    marker = f"end-criteria of {10 * math.log10(end_criterion):.2f}db reached"
    log_text = log_path.read_text(encoding="utf-8", errors="replace").lower()
    energy_bound = (_energy_upper_bound(log_text, run_path / "openEMS_run_stats.txt",
                                       stats.get("timestep_count"), end_criterion)
                    if marker in log_text else None)
    rlc_match = re.search(r"series/parallel lumped rlc load\s*-+\s*active cells\s*:\s*(\d+)", log_text)
    diagnostics = {
        "stamp": CANDIDATE_STAMP,
        "solver_statistics": stats,
        "configured_timestep_limit": timestep_limit,
        "energy_criterion": end_criterion,
        "final_energy_to_true_peak_upper_bound": energy_bound,
        "end_marker_present": marker in log_text,
        "excitation_truncated": "cutting to max number of timesteps" in log_text,
        "unused_primitive_warnings": log_text.count("unused primitive"),
        "source_registered": bool(re.search(r"voltage excitations\s*:\s*[1-9]", log_text)),
        "lumped_rlc_extension_active_cells": int(rlc_match.group(1)) if rlc_match else None,
        "rlc_extension_interpretation": (
            "openEMS v0.37.0 routes parallel pure-R elements through the regular engine, "
            "not the lumped-RLC extension; an extension count of zero does not prove port calibration. "
            "See https://github.com/thliebig/openEMS/blob/v0.37.0/FDTD/extensions/operator_ext_lumpedRLC.cpp"
        ),
        "copper_midpoint_screen": _sample_yee_midpoints(board, run_path / "geometry.xml"),
    }
    diagnostics["pec_edge_audit"] = _audit_pec_edges(
        board, run_path / "geometry.xml", run_path / "PEC_dump.vtp")
    diagnostics["barrel_edge_audit"] = (
        _audit_barrel_edges(holes, run_path / "geometry.xml", run_path / "PEC_dump.vtp")
        if squares is None else _square_barrel_audit(
            squares, run_path / "geometry.xml", run_path / "PEC_dump.vtp")
    )
    (run_path / "diagnostic_summary.json").write_text(
        json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
    if (code not in (None, 0) or not isinstance(stats.get("timestep_count"), int)
        or stats["timestep_count"] >= timestep_limit or energy is None
        or not math.isfinite(energy) or energy_bound is None or energy_bound > end_criterion
        or not diagnostics["end_marker_present"] or diagnostics["excitation_truncated"]
        or not diagnostics["source_registered"]):
        raise RuntimeError(f"Strict energy-stop gate failed: {stats}; see {log_path}")
    if diagnostic_steps is not None:
        raise RuntimeError(f"Diagnostic-only run cannot be postprocessed: {stats}")
    if diagnostics["unused_primitive_warnings"]:
        raise RuntimeError("Unused copper primitives require mesh-resolution review before postprocessing")
    _require_pec_fidelity(diagnostics)
    for port in ports:
        port.CalcPort(str(run_path), frequencies)
    from openEMS.utilities import DFT_time2freq

    incident = np.asarray(ports[excited_port - 1].uf_inc)
    waveform = np.loadtxt(run_path / "et")
    if waveform.ndim != 2 or waveform.shape[1] != 2 or len(waveform) < 2:
        raise RuntimeError("Invalid unit-source waveform")
    port_start, port_stop = PORTS[excited_port - 1]
    source_length_m = abs(port_stop[0] - port_start[0]) / 1000
    source = DFT_time2freq(waveform[:, 0], waveform[:, 1], frequencies)
    spectrum = _validate_incident_spectrum(
        incident, ports[excited_port - 1].uf_tot, ports[excited_port - 1].if_tot,
        source, source_length_m)
    waves = np.stack([
        np.stack([np.asarray(port.uf_inc) for port in ports], axis=1),
        np.stack([np.asarray(port.uf_ref) for port in ports], axis=1),
    ], axis=1)
    if not np.all(np.isfinite(waves)):
        raise RuntimeError("Non-finite port waves")
    return waves, {"cells": cells, "mesh_line_counts": counts, "solver": stats,
                   "final_energy_to_true_peak_upper_bound": energy_bound,
                   "incident_spectrum": spectrum}


def run_candidate(args, app_root, input_root):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import skrf
    from emc_sim.network_checks import check_passivity, check_reciprocity

    layer_map = json.loads(args.layer_map.read_text(encoding="utf-8"))
    stackup = json.loads(args.stackup.read_text(encoding="utf-8"))
    configuration = validate_layer_configuration(
        layer_map, stackup, base_directory=input_root, allow_candidate=True,
    )
    candidate = input_root / "MAIN_OMRON" / "MCP_CANDIDATE_20261121_1753"
    _validate_candidate_configuration(configuration, stackup, candidate)
    original, board, holes, squares, healing_metrics = _healed_candidate_board(configuration)
    original = _with_port_fixtures(original)
    board = _with_port_fixtures(board)
    probe_file = candidate / "gerbers" / "FlyingProbeTesting.json"
    run = create_run_directory(app_root / "runs" / "pcb_em",
        datetime.now(timezone.utc).strftime("candidate_%Y%m%dT%H%M%S%fZ"))
    shutil.copy2(Path(__file__), run / "workflow.py")
    assumptions = [
        f"Candidate exports: {candidate}; 2026-11-19 stackup metadata: "
        f"{input_root / 'MAIN_OMRON' / 'MCP_LIVE_20261119_203444_LayerStackup.json'}. "
        "Archive linkage and manufacturing revision are unconfirmed.",
        "1.6 mm FR4, isotropic epsilon 4.2 and loss tangent 0.02 at 1.05 GHz; 1 oz copper metadata, modeled as zero-thickness PEC sheets.",
        "Bottom Gerber import normalized one self-touching region and removed two zero-length boundary edges; geometry needs independent visual review.",
        "L1–U1 crop [16, -104, 42, -88.8] mm; 15.2 mm baseline air padding and PML_8 boundaries. Enclosure, cables, copper outside the crop and all component bodies are omitted.",
        "Copper coordinates snapped to a 0.10 mm grid, followed by a 0.001 mm outward edge bias; this changes modeled copper and does not guarantee every feature is at least 0.10 mm wide.",
        "Circular drills are approximated as square openings snapped to a 0.40 mm grid; ideal PEC barrel walls are 0.020 mm wide. Original and healed planar-island and hole-attachment topology are compared, not assumed.",
        "Coarse and medium/fine XY grid cells are at least 0.40 and 0.20 mm, respectively, with geometric air grading.",
        "L1, C2, CY1 and all other components are unpopulated in the 3D geometry. The modeled pre-/post-L1 response is differential only, not a complete common-mode or four-conductor network.",
        "Differential 50 ohm lumped ports are L1.1–L1.4 and U1.1–U1.2; four small, idealized PEC fixture strips connect the ports to the corresponding pads. No reference plane is added.",
        "Each two-port matrix is solved from both measured incident/reflected wave vectors (B = S A); unexcited-port incident waves are not assumed to be zero.",
        "Source-spectrum screening integrates the nominal unit electric-field excitation over the port length; it is not a calibrated terminal source voltage.",
        "CY1 lies on the converter secondary and cannot be included in a primary differential two-port without a justified converter coupling model.",
        "Requested postprocessing band: 30 MHz–1 GHz; no RF response is inferred from a truncated excitation.",
    ]
    metadata = {
        "stamp": CANDIDATE_STAMP, "candidate": str(input_root / "MAIN_OMRON" / "MCP_CANDIDATE_20261121_1753"),
        "assumptions": assumptions, "crop_bbox_m": board.crop_bbox_m,
        "geometry_healing": {"snap_m": .0001, "hole_grid_m": .0004,
                             "edge_bias_m": 1e-6, "barrel_wall_m": 20e-6,
                             "layer_metrics": healing_metrics},
        "source_hashes": {str(p): sha256_file(p) for p in [
            *configuration.gerber_sources.values(),
            *(Path(d.source) for d in configuration.drill_sources),
            probe_file,
            candidate / "candidate_evidence.json",
            *candidate.glob("*Gerbers.zip"), *candidate.glob("*Netlist.pads"),
            *candidate.glob("*PnP.csv"),
            input_root / "MAIN_OMRON" / "MCP_LIVE_20261119_203444_LayerStackup.json",
            input_root / "BOM_MAIN_OMRON_PCB_MAIN_OMRON_2026-11-19.csv",
            args.layer_map, args.stackup, args.manifest, Path(__file__),
            EMC_ROOT / "emc_sim" / "candidate_healing.py",
            EMC_ROOT / "emc_sim" / "dm_filter_cosim.py"]},
        "solver_status": "not_started", "solver_end_criteria_reached": False,
        "mesh_convergence": {"passed": False}, "passivity": {"passed": False},
        "time_convergence": {"passed": False, "reason": "Not evaluated"},
        "boundary_convergence": {"passed": False, "reason": "Not evaluated"},
        "frequency_sweep_hz": {"start": FREQUENCY_BAND_HZ[0], "stop": FREQUENCY_BAND_HZ[1],
                               "points": FREQUENCY_POINTS, "spacing": "geometric"},
        "diagnostic_timestep_limit": args.diagnostic_steps,
        "diagnostic_only": args.diagnostic_steps is not None,
        "runs": [],
    }
    status = 1
    result = "No valid EM network or co-simulation result was produced."
    try:
        fig, ax = plt.subplots(figsize=(8, 5))
        for layer, color in zip(board.layers, ("tab:red", "tab:blue")):
            for polygon in layer.polygons:
                for ring in (polygon.exterior, *polygon.interiors):
                    x, y = ring.xy
                    ax.plot(np.asarray(x) * 1000, np.asarray(y) * 1000, color=color, linewidth=.5)
        ax.set_aspect("equal")
        ax.set_xlabel("Gerber X (mm)")
        ax.set_ylabel("Gerber Y (mm)")
        fig.suptitle(CANDIDATE_STAMP, fontsize=8)
        fig.savefig(run / "copper_overlay.png", dpi=150)
        plt.close(fig)
        (run / "geometry_overlay.json").write_text(json.dumps(
            {"stamp": CANDIDATE_STAMP, "geometry": board.overlay_data()}, allow_nan=False),
            encoding="utf-8")
        metadata["plated_hole_count"] = len(holes)
        _validate_port_geometry(original, probe_file, holes)
        _validate_port_geometry(board, probe_file, holes)
        frequencies = _candidate_frequencies()
        matrices = []
        for label, spacing, z_spacing in (("coarse", .4, .4), ("medium", .2, .4),
                                           ("fine", .2, .2)):
            columns = []
            for excited in (1, 2):
                waves, statistics = _run_candidate_excitation(
                    board, holes, run / f"{label}_port{excited}", spacing, excited, frequencies,
                    diagnostic_steps=args.diagnostic_steps, padding_mm=HEALED_PADDING_MM,
                    squares=squares, z_spacing_mm=z_spacing)
                columns.append(waves)
                metadata["runs"].append({"mesh": label, "excited_port": excited, **statistics})
            matrices.append(_assemble_network_waves(columns))
        metadata["solver_status"] = "end_criteria_reached"
        metadata["solver_end_criteria_reached"] = True
        changes = _mesh_convergence_diagnostic(frequencies, matrices, run / "mesh_change_diagnostic.png")
        metadata["mesh_convergence"] = {"passed": max(changes) <= .05, "pairwise_max_relative_changes": changes,
                                        "tolerance": .05}
        if not metadata["mesh_convergence"]["passed"]:
            raise RuntimeError(f"Mesh convergence gate failed: {changes}")
        mesh_passivity, mesh_reciprocity = {}, {}
        for label, matrix in zip(("coarse", "medium", "fine"), matrices):
            network = skrf.Network(frequency=skrf.Frequency.from_f(frequencies, unit="hz"),
                                   s=matrix, z0=50, s_def="power")
            mesh_passivity[label] = check_passivity(network, run_metadata=metadata)
            mesh_reciprocity[label] = check_reciprocity(network, run_metadata=metadata)
        metadata["passivity"] = {"passed": all(mesh_passivity.values()), "meshes": mesh_passivity}
        metadata["reciprocity"] = {"passed": all(mesh_reciprocity.values()),
                                   "meshes": mesh_reciprocity, "absolute_tolerance": 1e-9}
        if not metadata["passivity"]["passed"]:
            raise RuntimeError("Full S-matrix passivity gate failed")
        if not metadata["reciprocity"]["passed"]:
            raise RuntimeError("S-matrix reciprocity gate failed")
        expanded = {}
        boundary_padding = {"expanded_x": (20.2, 15.2, 15.2),
                            "expanded_y": (15.2, 20.2, 15.2),
                            "expanded_z": (15.2, 15.2, 20.2)}
        for case, padding in boundary_padding.items():
            columns = []
            for excited in (1, 2):
                waves, statistics = _run_candidate_excitation(
                    board, holes, run / f"{case}_port{excited}", .2, excited,
                    frequencies, padding_mm=padding, squares=squares)
                columns.append(waves)
                metadata["runs"].append({"boundary": case, "excited_port": excited, **statistics})
            candidate_matrix = _assemble_network_waves(columns)
            candidate_network = skrf.Network(
                frequency=skrf.Frequency.from_f(frequencies, unit="hz"),
                s=candidate_matrix, z0=50, s_def="power")
            if not check_passivity(candidate_network, run_metadata=metadata):
                raise RuntimeError(f"Boundary case {case} failed full S-matrix passivity")
            expanded[case] = candidate_matrix
        metadata["boundary_convergence"] = _boundary_convergence(
            matrices[1], expanded, reference_padding=HEALED_PADDING_MM,
            expanded_padding=boundary_padding)
        if not metadata["boundary_convergence"]["passed"]:
            raise RuntimeError("Independent boundary sensitivity gate failed")
        tighter_columns = []
        for excited in (1, 2):
            waves, statistics = _run_candidate_excitation(
                board, holes, run / f"tighter_energy_port{excited}", .2, excited,
                frequencies, end_criterion=END_CRITERION / 10,
                padding_mm=HEALED_PADDING_MM, squares=squares)
            baseline = next(item for item in metadata["runs"]
                            if item.get("mesh") == "medium" and item["excited_port"] == excited)
            if statistics["solver"]["timestep_count"] <= baseline["solver"]["timestep_count"]:
                raise RuntimeError("Tighter energy case did not run longer than the baseline")
            tighter_columns.append(waves)
            metadata["runs"].append({"time_case": "tighter_energy", "excited_port": excited, **statistics})
        tighter_matrix = _assemble_network_waves(tighter_columns)
        tighter_network = skrf.Network(
            frequency=skrf.Frequency.from_f(frequencies, unit="hz"),
            s=tighter_matrix, z0=50, s_def="power")
        if not check_passivity(tighter_network, run_metadata=metadata):
            raise RuntimeError("Tighter energy case failed full S-matrix passivity")
        time_change = float(np.max(
            np.abs(tighter_matrix - matrices[1])
            / np.maximum(np.maximum(np.abs(tighter_matrix), np.abs(matrices[1])), 1e-12)))
        metadata["time_convergence"] = {
            "passed": time_change <= .05, "tolerance": .05,
            "maximum_relative_change": time_change,
            "baseline_end_criterion": END_CRITERION,
            "tighter_end_criterion": END_CRITERION / 10,
        }
        if not metadata["time_convergence"]["passed"]:
            raise RuntimeError("Independent duration convergence gate failed")
        _require_release_gates(metadata)
        from scipy.signal import find_peaks
        from emc_sim.dm_filter_cosim import cosimulate_dm_filter

        bypass = skrf.Network(
            frequency=skrf.Frequency.from_f(frequencies, unit="hz"),
            s=matrices[1], z0=50, s_def="power")
        cosim = cosimulate_dm_filter(
            bypass, run_metadata=metadata, candidate_export=str(candidate),
            frequency_band_hz=FREQUENCY_BAND_HZ, pre_post_polarity_confirmed=True)
        peaks, _ = find_peaks(np.abs(cosim.voltage_transfer))
        metadata["cosimulation"] = {
            "scope": "idealized differential L1 and C2 only; CY1 and converter excluded",
            "assumptions": vars(cosim.assumptions),
            "sampled_response_maxima_hz": frequencies[peaks].tolist(),
            "limitation": cosim.limitation,
        }
        metadata["representative_results"] = [
            {"frequency_hz": float(frequencies[index]),
             "s11_db": float(20 * np.log10(max(abs(matrices[1][index, 0, 0]), 1e-15))),
             "s21_db": float(20 * np.log10(max(abs(matrices[1][index, 1, 0]), 1e-15))),
             "dm_voltage_transfer_db": float(20 * np.log10(max(abs(cosim.voltage_transfer[index]), 1e-15)))}
            for index in (0, len(frequencies) // 2, len(frequencies) - 1)
        ]
        bypass.write_touchstone(str(run / "candidate_bypass"))
        touchstone = run / "candidate_bypass.s2p"
        touchstone.write_text(
            "! " + CANDIDATE_STAMP + "\n" + touchstone.read_text(encoding="utf-8"),
            encoding="utf-8")
        fig, ax = plt.subplots(figsize=(8, 5))
        for i, j in ((0, 0), (1, 0), (0, 1), (1, 1)):
            ax.semilogx(frequencies, 20 * np.log10(np.maximum(np.abs(matrices[1][:, i, j]), 1e-15)),
                        label=f"S{i + 1}{j + 1}")
        ax.set(xlabel="Frequency (Hz)", ylabel="Magnitude (dB)")
        ax.grid(True, which="both")
        ax.legend()
        fig.suptitle(CANDIDATE_STAMP, fontsize=8)
        fig.savefig(run / "candidate_bypass_sparameters.png", dpi=150)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.semilogx(frequencies, 20 * np.log10(np.maximum(np.abs(cosim.voltage_transfer), 1e-15)))
        ax.set(xlabel="Frequency (Hz)", ylabel="Loaded DM voltage transfer (dB)")
        ax.grid(True, which="both")
        fig.suptitle(CANDIDATE_STAMP, fontsize=8)
        fig.savefig(run / "candidate_dm_cosimulation.png", dpi=150)
        plt.close(fig)
        status = 0
        result = (
            "Converged passive reciprocal candidate bypass two-port and idealized L1/C2 differential "
            "co-simulation saved as candidate_bypass.s2p, candidate_bypass_sparameters.png and "
            "candidate_dm_cosimulation.png. CY1 and converter coupling are not modeled. "
            f"Sampled co-simulation response maxima: {frequencies[peaks].tolist()} Hz."
        )
    except (OSError, ValueError, RuntimeError) as exc:
        summaries = list(run.glob("*/diagnostic_summary.json"))
        if summaries:
            summary = max(summaries, key=lambda path: path.stat().st_mtime_ns)
            metadata["diagnostic"] = json.loads(summary.read_text(encoding="utf-8"))
            metadata["diagnostic_path"] = str(summary.relative_to(run))
            if not metadata["solver_end_criteria_reached"]:
                metadata["solver_status"] = (
                    "diagnostic_end_criterion_reached"
                    if args.diagnostic_steps and metadata["diagnostic"]["end_marker_present"]
                    else "diagnostic_capped" if args.diagnostic_steps else "solver_failed"
                )
        metadata["failure"] = f"{type(exc).__name__}: {exc}"
        result += " Blocker: " + metadata["failure"]
        if "diagnostic" in metadata:
            diag = metadata["diagnostic"]
            result += (
                f" Excitation truncated: {diag['excitation_truncated']}; "
                f"unused primitive warnings: {diag['unused_primitive_warnings']}. "
                "The candidate midpoint screen does not establish copper shape or connectivity."
            )
    finally:
        write_run_metadata(run, metadata)
        simulations = []
        calculations = []
        if "representative_results" in metadata:
            simulations.append(
                f"Representative modeled bypass S-parameters and loaded DM transfer: "
                f"{metadata['representative_results']}. See candidate_bypass.s2p and plots.")
        if "diagnostic" in metadata:
            diagnostic = metadata["diagnostic"]
            stats = diagnostic["solver_statistics"]
            simulations.append(
                f"openEMS {'bounded diagnostic only' if args.diagnostic_steps else 'solver attempt'}; not valid RF data. "
                f"Steps: {stats.get('timestep_count')}/{diagnostic['configured_timestep_limit']}; "
                f"timestep: {stats.get('actual_timestep_s')} s; "
                f"duration: {stats.get('numerical_duration_s')} s; "
                f"solver-reported cells: {stats.get('cell_count')}; "
                f"solver time: {stats.get('solver_wall_time_s')} s; "
                f"energy end marker: {diagnostic['end_marker_present']}; "
                f"excitation truncated: {diagnostic['excitation_truncated']}; "
                f"unused primitive warnings: {diagnostic['unused_primitive_warnings']}. "
                f"See {Path(metadata['diagnostic_path']).parent}/solver.log and "
                f"{metadata['diagnostic_path']}."
            )
            if diagnostic["unused_primitive_warnings"]:
                simulations.append("Unused primitives remain unresolved and block network post-processing.")
            audit = diagnostic.get("pec_edge_audit")
            if audit:
                for layer, directions in audit["layers"].items():
                    for direction, counts in directions.items():
                        calculations.append(
                            f"PEC midpoint screen {layer}/{direction}: "
                            f"{counts['missing_expected_midpoints']} missing of "
                            f"{counts['expected_copper_midpoints']} expected; "
                            f"{counts['extra_pec_midpoints_outside_copper']} extra, "
                            f"{counts['extra_within_idealized_port_boxes']} within idealized port boxes. "
                            "This does not prove sub-cell fidelity or resolve unused primitive warnings."
                        )
            barrel_audit = diagnostic.get("barrel_edge_audit")
            if barrel_audit:
                calculations.append(
                    f"Barrel PEC cardinal-edge screen: {barrel_audit['missing_segments']} missing of "
                    f"{barrel_audit['expected_segments']} expected segments across "
                    f"{barrel_audit['hole_count']} holes. This does not prove real barrel fidelity or copper connectivity."
                )
        if (run / "mesh_change_diagnostic.png").exists():
            simulations.append(
                "Unvalidated mesh comparison: mesh_change_diagnostic.png. "
                "This diagnostic is not an extractable or converged RF network.")
        write_report(run,
            question=CANDIDATE_STAMP + " — Can a local differential PCB network be extracted and used in a BOM co-simulation?",
            evidence={"assumptions": assumptions, "calculations": calculations, "simulations": simulations, "measurements": []},
            result=CANDIDATE_STAMP + "\n\n" + result,
            limitations=["No compliance or safety conclusion.", "Mesh and boundary convergence must be demonstrated; energy stop alone is insufficient.",
                         "Results depend on idealized local port and plated-barrel geometry.",
                         "No RF inference may be drawn from a truncated excitation."],
        )
    print(f"{CANDIDATE_STAMP}\nRun: {run}\n{result}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=EMC_ROOT / "smart_power_strip" / "configs" / "revision_manifest.json",
    )
    parser.add_argument("--allow-candidate", "--candidate", dest="allow_candidate",
                        action="store_true", help="Run the explicitly selected exploratory candidate")
    duration = parser.add_mutually_exclusive_group()
    duration.add_argument("--diagnostic-steps", type=int, choices=range(1, 40001), metavar="N",
                          help="Diagnostic-only cap up to 40000 steps; never release network results")
    duration.add_argument("--full-solve", action="store_true",
                          help="Attempt the full gated solve subject to resource limits")
    parser.add_argument(
        "--layer-map",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--stackup",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    app_root = EMC_ROOT / "smart_power_strip"
    input_root = app_root / "inputs" / "locked_rev"
    config_root = app_root / "configs"
    if args.layer_map is None:
        args.layer_map = config_root / ("layer_map.json" if args.allow_candidate else "layer_map_template.json")
    if args.stackup is None:
        args.stackup = config_root / ("stackup.json" if args.allow_candidate else "stackup_template.json")
    try:
        if args.allow_candidate:
            verify_manifest(args.manifest, allow_candidate=True, input_root=app_root)
            return run_candidate(args, app_root, input_root)
        manifest = verify_manifest(args.manifest, input_root=app_root)
        layer_map = json.loads(args.layer_map.read_text(encoding="utf-8"))
        stackup = json.loads(args.stackup.read_text(encoding="utf-8"))
        configuration = validate_layer_configuration(
            layer_map,
            stackup,
            base_directory=input_root,
        )
        manifest_paths = {
            Path(entry["path"]).as_posix().casefold()
            for entry in manifest["files"]
        }
        missing_hashes = [
            (Path("inputs") / "locked_rev" / path).as_posix()
            for path in configuration.input_paths
            if (Path("inputs") / "locked_rev" / path).as_posix().casefold()
            not in manifest_paths
        ]
        if missing_hashes:
            raise GerberImportError(
                "configured Gerber/stackup/drill inputs are not listed in the "
                f"revision manifest: {missing_hashes}"
            )
        board = import_gerbers(
            configuration.gerber_sources,
            configuration.copper_layers,
            drill_sources=configuration.drill_sources,
            crop_bbox_m=configuration.crop_bbox_m,
        )
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=EMC_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=EMC_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        run_directory = create_run_directory(app_root / "runs" / "pcb_em")
        write_overlay_png(board, run_directory / "copper_overlay.png")
        (run_directory / "geometry_overlay.json").write_text(
            json.dumps(board.overlay_data(), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        input_hashes = {
            entry["path"]: entry["sha256"] for entry in manifest["files"]
        }
        run_metadata = {
            "scope": "verified 2D copper and Excellon drill/slot import and overlay only",
            "project_id": manifest["project_id"],
            "revision": manifest["revision"],
            "git_commit": git_commit,
            "worktree_dirty": bool(git_status.strip()),
            "solver": None,
            "solver_status": "not_run",
            "source_hashes": input_hashes,
            "manifest_sha256": sha256_file(args.manifest),
            "workflow_sha256": sha256_file(Path(__file__)),
            "tool_versions": {
                "python": sys.version.split()[0],
                "gerbonara": version("gerbonara"),
                "shapely": version("shapely"),
                "matplotlib": version("matplotlib"),
            },
            "layers": [
                {
                    "name": layer.name,
                    "z_m": layer.z_m,
                    "thickness_m_metadata_only": layer.thickness_m,
                    "polygon_count": len(layer.polygons),
                }
                for layer in board.layers
            ],
            "drill_files": [
                {
                    "name": drill.name,
                    "source_file": drill.source_label,
                    "from_layer": drill.from_layer,
                    "to_layer": drill.to_layer,
                    "affected_layers": list(drill.affected_layers),
                    "hit_count": drill.hit_count,
                    "slot_count": drill.slot_count,
                    "tool_diameters_m": list(drill.tool_diameters_m),
                    "plating_status": drill.plating_status,
                }
                for drill in board.drill_files
            ],
            "crop_bbox_m": board.crop_bbox_m,
            "arc_tolerance_m": board.arc_tolerance_m,
            "measurements": [],
        }
        write_run_metadata(run_directory, run_metadata)
        write_report(
            run_directory,
            question="Do the configured Gerber and Excellon inputs produce a traceable 2D copper/drill overlay for visual review?",
            evidence={
                "assumptions": [
                    "Layer elevations and thickness metadata are taken only from the verified stackup configuration.",
                    "Drill hits and slots are subtracted only across their explicitly configured inclusive copper-layer spans.",
                ],
                "calculations": [],
                "simulations": [],
                "measurements": [],
            },
            result=(
                "A 2D copper and drill/slot overlay was generated for manual visual review. "
                "No openEMS simulation was run."
            ),
            limitations=[
                "Drill hits and slots are imported, but via barrels and their plating are not modeled.",
                "Copper thickness is metadata only; CSXCAD conversion uses PEC sheets.",
                "No dielectric, source, port, boundary, mesh, or electromagnetic response was modeled.",
            ],
        )
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        ValueError,
        GerberImportError,
    ) as exc:
        parser.exit(2, f"PCB EM extraction blocked: {exc}\n")
    parser.exit(
        0,
        f"Copper and drill geometry overlay written to {run_directory}; inspect it against "
        "the matched fabrication data. No openEMS simulation was run.\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
