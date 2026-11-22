import json
from pathlib import Path

import pytest
from shapely.geometry import box

from emc_sim.candidate_healing import heal_candidate_copper
from emc_sim.gerber_import import (
    BoardGeometry,
    GerberImportError,
    LayerGeometry,
    import_gerbers,
    validate_layer_configuration,
)


def test_healing_preserves_candidate_islands_and_plated_hole_attachments():
    root = Path(__file__).resolve().parents[1] / "smart_power_strip"
    configs = root / "configs"
    configuration = validate_layer_configuration(
        json.loads((configs / "layer_map.json").read_text()),
        json.loads((configs / "stackup.json").read_text()),
        base_directory=root / "inputs" / "locked_rev",
        allow_candidate=True,
    )
    kwargs = {"crop_bbox_m": configuration.crop_bbox_m}
    uncut = import_gerbers(configuration.gerber_sources, configuration.copper_layers, **kwargs)
    board = import_gerbers(configuration.gerber_sources, configuration.copper_layers,
                           drill_sources=configuration.drill_sources, **kwargs)
    holes = []
    for drill in board.drill_files:
        for geometry in getattr(drill.geometry, "geoms", (drill.geometry,)):
            if not geometry.is_empty:
                xmin, ymin, xmax, ymax = geometry.bounds
                holes.append(((xmin + xmax) / 2, (ymin + ymax) / 2, (xmax - xmin) / 2))
    healed, squares, metrics = heal_candidate_copper(board, uncut, holes)
    assert len(squares) == len(holes)
    assert all(value["islands_before"] == value["islands_after"] for value in metrics.values())
    assert all(value["symmetric_difference_area_m2"] > 0 for value in metrics.values())
    assert all(layer.geometry.is_valid for layer in healed.layers)


def test_healing_rejects_merging_copper_islands():
    a = box(0, 0, .001, .001).union(box(.00104, 0, .002, .001))
    layer = LayerGeometry("Top", 0, 1e-6, a, None, 1e-6)
    board = BoardGeometry((layer,), None, 1e-6)
    with pytest.raises(GerberImportError, match="merges"):
        heal_candidate_copper(board, board, [(.01, .01, .0005)])


def test_healing_rejects_overlapping_snapped_holes():
    layer = LayerGeometry("Top", 0, 1e-6, box(0, 0, .01, .01), None, 1e-6)
    board = BoardGeometry((layer,), None, 1e-6)
    with pytest.raises(GerberImportError, match="touch or overlap"):
        heal_candidate_copper(board, board, [(.002, .002, .0005), (.0025, .002, .0005)])
