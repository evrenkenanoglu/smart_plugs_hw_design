"""Explicit, topology-checked geometry approximations for candidate FDTD models."""

from __future__ import annotations

import math
from dataclasses import replace

import shapely
from shapely.geometry import Point, box
from shapely.ops import unary_union

from emc_sim.gerber_import import GerberImportError


def _parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    raise GerberImportError("Healed copper must consist of polygons")


def heal_candidate_copper(board, uncut_board, holes, *, snap_m=0.0001,
                          hole_grid_m=0.0002, edge_bias_m=1e-6):
    """Snap copper and approximate circular plated holes with grid-aligned squares.

    The topology check is deliberately conservative: no original island may
    split, disappear, or merge, and each plated hole must retain its original
    layer attachments. It does not prove sub-grid RF accuracy.
    """
    if (not math.isfinite(snap_m) or not math.isfinite(hole_grid_m)
        or not math.isfinite(edge_bias_m) or edge_bias_m < 0 or edge_bias_m >= snap_m / 2
        or snap_m <= 0 or hole_grid_m <= 0
        or not math.isclose(hole_grid_m / snap_m, round(hole_grid_m / snap_m),
                            abs_tol=1e-9)):
        raise ValueError("Hole grid must be a positive integer multiple of the copper snap grid")
    if not holes:
        raise GerberImportError("Cannot heal a candidate without plated holes")
    if tuple(layer.name for layer in board.layers) != tuple(
            layer.name for layer in uncut_board.layers):
        raise GerberImportError("Drilled and uncut layers do not match")
    squares = []
    for x, y, radius in holes:
        if not all(math.isfinite(v) for v in (x, y, radius)) or radius <= 0:
            raise GerberImportError("Invalid plated-hole coordinates")
        center_x = round(x / hole_grid_m) * hole_grid_m
        center_y = round(y / hole_grid_m) * hole_grid_m
        half = max(hole_grid_m, round(radius / math.sqrt(2) / hole_grid_m) * hole_grid_m)
        squares.append(box(center_x - half, center_y - half,
                           center_x + half, center_y + half))
    for i, first in enumerate(squares):
        if any(first.intersects(second) for second in squares[i + 1:]):
            raise GerberImportError("Simplified plated holes touch or overlap")
    openings = unary_union(squares)
    layers, metrics = [], {}
    for original, uncut in zip(board.layers, uncut_board.layers):
        if original.z_m != uncut.z_m or original.thickness_m != uncut.thickness_m:
            raise GerberImportError("Drilled and uncut stackups do not match")
        original_parts = list(original.polygons)
        snapped = shapely.set_precision(uncut.geometry, snap_m)
        healed = snapped.difference(openings)
        if edge_bias_m:
            healed = shapely.set_precision(healed, 0).buffer(edge_bias_m, join_style="mitre")
        new_parts = _parts(healed)
        old_to_new = [
            [j for j, new in enumerate(new_parts) if old.intersection(new).area > 1e-14]
            for old in original_parts
        ]
        new_to_old = [
            [i for i, old in enumerate(original_parts) if old.intersection(new).area > 1e-14]
            for new in new_parts
        ]
        if any(len(mapping) != 1 for mapping in old_to_new + new_to_old):
            raise GerberImportError(f"Healing splits, merges, or removes {original.name} copper islands")
        for (x, y, radius), opening in zip(holes, squares):
            old_contact = Point(x, y).buffer(radius + 25e-6)
            before = {old_to_new[i][0] for i, copper in enumerate(original_parts)
                      if copper.distance(old_contact) < 1e-9}
            after = {i for i, copper in enumerate(new_parts)
                     if copper.distance(opening.boundary) < 1e-9}
            if before != after:
                raise GerberImportError(
                    f"Healing changes {original.name} plated-hole attachment at {x}, {y}")
        metrics[original.name] = {
            "islands_before": len(original_parts),
            "islands_after": len(new_parts),
            "symmetric_difference_area_m2": original.geometry.symmetric_difference(healed).area,
            "original_copper_area_m2": original.geometry.area,
            "healed_copper_area_m2": healed.area,
        }
        layers.append(replace(original, geometry=healed))
    return replace(board, layers=tuple(layers)), tuple(squares), metrics
