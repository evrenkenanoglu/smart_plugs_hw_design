from pathlib import Path

import pytest

pytest.importorskip("gerbonara")
pytest.importorskip("shapely")

from shapely.geometry import Point

from emc_sim.gerber_import import (
    CopperLayerSpec,
    DrillSourceSpec,
    ExcellonText,
    GerberImportError,
    GerberText,
    add_copper_layer_to_csx,
    import_gerbers,
    validate_layer_configuration,
    write_overlay_png,
    _primitive_polygon,
)


TRACE_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
%ADD10C,0.2*%
D10*
X000000Y000000D02*
X010000Y000000D01*
M02*
"""

REGION_WITH_CUTOUT_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
%LPD*%
G36*
X000000Y000000D02*
X020000Y000000D01*
X020000Y010000D01*
X000000Y010000D01*
X000000Y000000D01*
G37*
%LPC*%
G36*
X005000Y002500D02*
X015000Y002500D01*
X015000Y007500D01*
X005000Y007500D01*
X005000Y002500D01*
G37*
%LPD*%
M02*
"""

SELF_TOUCHING_REGION_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
G36*
X010000Y010000D02*
X020000Y010000D01*
X020000Y020000D01*
X010000Y020000D01*
X010000Y010000D01*
X000000Y010000D01*
X000000Y000000D01*
X010000Y000000D01*
X010000Y010000D01*
G37*
M02*
"""

NEGATIVE_IMAGE_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
%IPNEG*%
%ADD10C,0.2*%
D10*
X000000Y000000D03*
M02*
"""

NONCIRCULAR_TRACE_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
%ADD10R,0.2X0.1*%
D10*
X000000Y000000D02*
X010000Y000000D01*
M02*
"""

DRILL_TEST_COPPER_GERBER = """\
%FSLAX24Y24*%
%MOMM*%
G36*
X000000Y000000D02*
X040000Y000000D01*
X040000Y030000D01*
X000000Y030000D01*
X000000Y000000D01*
G37*
M02*
"""

DRILL_AND_G85_SLOT_EXCELLON = """\
M48
;FILE_FORMAT=2:4
METRIC,TZ
T01C0.600
%
T01
X010000Y010000
X020000Y010000G85X030000Y010000
M30
"""

AMBIGUOUS_EXCELLON = """\
M48
METRIC
T01C0.600
%
T01
X010000Y010000
M30
"""

AMBIGUOUS_TOOL_DIAMETER_EXCELLON = """\
M48
METRIC
T01C0600
%
T01
X1.000Y1.000
M30
"""


def test_imports_simple_trace_with_explicit_map_stackup_and_crop():
    crop = (0.00025, -0.00005, 0.00075, 0.00005)
    board = import_gerbers(
        {"Top Copper": GerberText(TRACE_GERBER, "trace fixture")},
        [CopperLayerSpec("Top Copper", z_m=0.0012, thickness_m=35e-6)],
        crop_bbox_m=crop,
    )

    layer = board.layer("Top Copper")
    assert layer.geometry.bounds == pytest.approx(crop)
    assert layer.geometry.area == pytest.approx(5e-8)
    assert layer.z_m == pytest.approx(0.0012)
    assert layer.thickness_m == pytest.approx(35e-6)
    overlay = board.overlay_data()
    assert overlay["units"] == "m"
    assert overlay["layers"][0]["name"] == "Top Copper"
    assert overlay["layers"][0]["polygons"][0]["holes"] == []


def test_dark_region_and_clear_region_preserve_cutout_and_convert_at_layer_z():
    board = import_gerbers(
        {"Inner Copper": GerberText(REGION_WITH_CUTOUT_GERBER, "region fixture")},
        [CopperLayerSpec("Inner Copper", z_m=0.00042, thickness_m=18e-6)],
    )
    layer = board.layer("Inner Copper")
    assert layer.geometry.area == pytest.approx(1.5e-6)
    assert layer.geometry.contains(Point(0.00025, 0.0005))
    assert not layer.geometry.contains(Point(0.001, 0.0005))
    assert len(layer.polygons) == 1
    assert len(layer.polygons[0].interiors) == 1
    assert len(layer.overlay_data()["polygons"][0]["holes"]) == 1

    class CaptureMetal:
        def __init__(self):
            self.polygons = []

        def AddPolygon(self, points, *, norm_dir, elevation, priority):
            self.polygons.append((points, norm_dir, elevation, priority))

    class CaptureStructure:
        def __init__(self):
            self.names = []
            self.metal = CaptureMetal()

        def AddMetal(self, name):
            self.names.append(name)
            return self.metal

    structure = CaptureStructure()
    metal = add_copper_layer_to_csx(
        structure, layer, priority=7, property_name="configured copper"
    )
    assert metal is structure.metal
    assert structure.names == ["configured copper"]
    assert structure.metal.polygons
    emitted_area = 0.0
    for points, norm_dir, elevation, priority in structure.metal.polygons:
        assert len(points) == 2
        x_values, y_values = points
        assert len(x_values) == len(y_values) >= 3
        assert norm_dir == "z"
        assert elevation == pytest.approx(0.00042)
        assert priority == 7
        emitted_area += abs(
            sum(
                x_values[index] * y_values[(index + 1) % len(x_values)]
                - x_values[(index + 1) % len(x_values)] * y_values[index]
                for index in range(len(x_values))
            )
        ) / 2
    assert emitted_area == pytest.approx(layer.geometry.area)


def test_self_touching_g36_region_is_decomposed_without_losing_copper():
    with pytest.warns(RuntimeWarning, match="make_valid\\(linework\\)"):
        board = import_gerbers(
            {
                "Bottom Copper": GerberText(
                    SELF_TOUCHING_REGION_GERBER, "touching region"
                )
            },
            [CopperLayerSpec("Bottom Copper", z_m=0.0, thickness_m=35e-6)],
        )
    geometry = board.layer("Bottom Copper").geometry

    assert geometry.is_valid
    assert geometry.area == pytest.approx(2e-6)
    assert geometry.contains(Point(0.0015, 0.0015))
    assert geometry.contains(Point(0.0005, 0.0005))
    assert not geometry.contains(Point(0.0015, 0.0005))


def test_arc_stroke_with_zero_radius_boundary_edge_preserves_copper():
    from gerbonara.graphic_primitives import Arc

    primitive = Arc(
        x1=61.595,
        y1=-87.6046,
        x2=61.66684,
        y2=-87.57484,
        cx=61.595,
        cy=-87.503,
        clockwise=False,
        width=0.2032,
        polarity_dark=True,
    )

    topology_changes = {
        "normalized_regions": 0,
        "removed_zero_length_edges": 0,
    }
    geometry = _primitive_polygon(
        primitive,
        tolerance_mm=0.001,
        topology_changes=topology_changes,
    )

    assert geometry.is_valid
    assert geometry.area > 0
    assert topology_changes["removed_zero_length_edges"] == 1


def test_excellon_hit_and_slot_are_subtracted_only_across_explicit_span():
    gerber = GerberText(DRILL_TEST_COPPER_GERBER, "drill copper fixture")
    board = import_gerbers(
        {
            "Top": gerber,
            "Middle": gerber,
            "Bottom": gerber,
        },
        [
            CopperLayerSpec("Top", z_m=0.0, thickness_m=35e-6),
            CopperLayerSpec("Middle", z_m=0.0008, thickness_m=18e-6),
            CopperLayerSpec("Bottom", z_m=0.0016, thickness_m=35e-6),
        ],
        drill_sources=[
            DrillSourceSpec(
                name="PTH",
                source=ExcellonText(DRILL_AND_G85_SLOT_EXCELLON, "pth fixture"),
                from_layer="Top",
                to_layer="Middle",
            )
        ],
    )

    top = board.layer("Top")
    middle = board.layer("Middle")
    bottom = board.layer("Bottom")
    assert top.geometry.area == pytest.approx(middle.geometry.area)
    assert top.geometry.area < bottom.geometry.area
    assert bottom.geometry.area == pytest.approx(12e-6)
    assert not top.geometry.contains(Point(0.001, 0.001))
    assert not middle.geometry.contains(Point(0.0025, 0.001))
    assert bottom.geometry.contains(Point(0.001, 0.001))

    drill = board.drill_files[0]
    assert drill.from_layer == "Top"
    assert drill.to_layer == "Middle"
    assert drill.affected_layers == ("Top", "Middle")
    assert drill.hit_count == 1
    assert drill.slot_count == 1
    assert drill.tool_diameters_m == pytest.approx((0.0006,))
    assert drill.plating_status == "unknown"
    metadata = board.overlay_data()["drill_files"][0]
    assert metadata["source_file"] == "pth fixture"
    assert metadata["affected_layers"] == ["Top", "Middle"]
    assert metadata["hit_count"] == 1
    assert metadata["slot_count"] == 1
    assert metadata["polygons"]


def test_real_csxcad_writes_imported_cutout_geometry(tmp_path):
    csxcad = pytest.importorskip("CSXCAD")
    board = import_gerbers(
        {"Inner Copper": GerberText(REGION_WITH_CUTOUT_GERBER, "region fixture")},
        [CopperLayerSpec("Inner Copper", z_m=0.00042, thickness_m=18e-6)],
    )
    structure = csxcad.ContinuousStructure()
    add_copper_layer_to_csx(structure, board.layer("Inner Copper"))

    output = tmp_path / "gerber_cutout.xml"
    structure.Write2XML(str(output))

    assert output.is_file()
    assert output.stat().st_size > 0


def test_real_csxcad_writes_excellon_subtracted_geometry(tmp_path):
    csxcad = pytest.importorskip("CSXCAD")
    board = import_gerbers(
        {"Top": GerberText(DRILL_TEST_COPPER_GERBER, "drill copper fixture")},
        [CopperLayerSpec("Top", z_m=0.0, thickness_m=35e-6)],
        drill_sources=[
            DrillSourceSpec(
                name="PTH",
                source=ExcellonText(DRILL_AND_G85_SLOT_EXCELLON, "pth fixture"),
                from_layer="Top",
                to_layer="Top",
            )
        ],
    )
    structure = csxcad.ContinuousStructure()
    add_copper_layer_to_csx(structure, board.layer("Top"))

    output = tmp_path / "gerber_excellon.xml"
    structure.Write2XML(str(output))

    assert output.is_file()
    assert output.stat().st_size > 0


def test_overlay_png_is_labeled_as_geometry_only(tmp_path):
    pytest.importorskip("matplotlib")
    board = import_gerbers(
        {"Top": GerberText(TRACE_GERBER, "trace fixture")},
        [CopperLayerSpec("Top", z_m=0.0, thickness_m=35e-6)],
    )
    output = write_overlay_png(board, tmp_path / "overlay.png")

    assert output.is_file()
    assert output.stat().st_size > 0
    with pytest.raises(GerberImportError, match="overwrite"):
        write_overlay_png(board, output)


def test_layer_map_and_stackup_must_match_and_neither_is_inferred():
    gerbers = {"Top": GerberText(TRACE_GERBER)}
    with pytest.raises(GerberImportError, match="exactly the same"):
        import_gerbers(gerbers, [CopperLayerSpec("Bottom", 0.0, 35e-6)])
    with pytest.raises(GerberImportError, match="layer map"):
        import_gerbers({}, [CopperLayerSpec("Top", 0.0, 35e-6)])
    with pytest.raises(GerberImportError, match="stackup"):
        import_gerbers(gerbers, [])


def test_negative_image_polarity_fails_closed():
    with pytest.raises(GerberImportError, match="IPNEG"):
        import_gerbers(
            {"Top": GerberText(NEGATIVE_IMAGE_GERBER)},
            [CopperLayerSpec("Top", 0.0, 35e-6)],
        )


def test_non_circular_trace_aperture_fails_closed():
    with pytest.raises(GerberImportError, match="non-circular aperture"):
        import_gerbers(
            {"Top": GerberText(NONCIRCULAR_TRACE_GERBER)},
            [CopperLayerSpec("Top", 0.0, 35e-6)],
        )


def test_ambiguous_fixed_width_excellon_format_fails_closed():
    with pytest.raises(GerberImportError, match="explicit integer/fraction format"):
        import_gerbers(
            {"Top": GerberText(DRILL_TEST_COPPER_GERBER)},
            [CopperLayerSpec("Top", 0.0, 35e-6)],
            drill_sources=[
                DrillSourceSpec(
                    name="PTH",
                    source=ExcellonText(AMBIGUOUS_EXCELLON),
                    from_layer="Top",
                    to_layer="Top",
                )
            ],
        )


def test_ambiguous_fixed_width_tool_diameter_fails_closed():
    with pytest.raises(GerberImportError, match="fixed-width Excellon"):
        import_gerbers(
            {"Top": GerberText(DRILL_TEST_COPPER_GERBER)},
            [CopperLayerSpec("Top", 0.0, 35e-6)],
            drill_sources=[
                DrillSourceSpec(
                    name="PTH",
                    source=ExcellonText(AMBIGUOUS_TOOL_DIAMETER_EXCELLON),
                    from_layer="Top",
                    to_layer="Top",
                )
            ],
        )


def test_crop_and_stackup_reject_nonfinite_or_invalid_values():
    with pytest.raises(GerberImportError, match="strictly increasing"):
        import_gerbers(
            {"Top": GerberText(TRACE_GERBER)},
            [CopperLayerSpec("Top", 0.0, 35e-6)],
            crop_bbox_m=(0.0, 0.0, 0.0, 1.0),
        )
    with pytest.raises(GerberImportError, match="thickness_m"):
        CopperLayerSpec("Top", 0.0, 0.0)


def test_excellon_accepts_easyeda_body_absolute_mode_without_allowing_incremental():
    source = DRILL_AND_G85_SLOT_EXCELLON.replace("%\n", "%\nG05\nG90\n")
    args = (
        {"Top": GerberText(DRILL_TEST_COPPER_GERBER)},
        [CopperLayerSpec("Top", 0.0, 35e-6)],
    )
    def drill(text):
        return [DrillSourceSpec("PTH", ExcellonText(text), "Top", "Top")]

    board = import_gerbers(*args, drill_sources=drill(source))
    assert board.drill_files[0].hit_count == 1
    assert board.drill_files[0].slot_count == 1
    with pytest.raises(GerberImportError, match="incremental"):
        import_gerbers(*args, drill_sources=drill(source.replace("G90\n", "G91\nG90\n")))


def _verified_config(input_root):
    (input_root / "top.gbr").write_text(TRACE_GERBER, encoding="utf-8")
    (input_root / "stackup.csv").write_text("verified source", encoding="utf-8")
    layer_map = {
        "verified": True,
        "source_revision": "rev-a",
        "layers": [{"name": "Top", "gerber_file": "top.gbr"}],
        "crop_mm": [0.0, -0.5, 1.0, 0.5],
    }
    stackup = {
        "verified": True,
        "source_revision": "rev-a",
        "source_file": "stackup.csv",
        "board_thickness_mm": 1.6,
        "dielectrics": [],
        "copper_layers": [
            {"name": "Top", "z_mm": 0.0, "thickness_mm": 0.035}
        ],
    }
    return layer_map, stackup


def test_validate_layer_configuration_requires_verified_same_revision_inputs(tmp_path):
    layer_map, stackup = _verified_config(tmp_path)

    configuration = validate_layer_configuration(
        layer_map, stackup, base_directory=tmp_path
    )
    assert configuration.input_paths == (Path("top.gbr"), Path("stackup.csv"))
    assert configuration.gerber_sources["Top"] == (tmp_path / "top.gbr").resolve()
    assert len(configuration.copper_layers) == 1
    assert configuration.copper_layers[0].name == "Top"
    assert configuration.copper_layers[0].z_m == pytest.approx(0.0)
    assert configuration.copper_layers[0].thickness_m == pytest.approx(35e-6)
    assert configuration.drill_sources == ()

    stackup["source_revision"] = "rev-b"
    with pytest.raises(GerberImportError, match="source revisions"):
        validate_layer_configuration(layer_map, stackup, base_directory=tmp_path)


def test_candidate_layer_configuration_requires_explicit_opt_in_and_matching_identity(tmp_path):
    layer_map, stackup = _verified_config(tmp_path)
    layer_map["verified"] = stackup["verified"] = False
    with pytest.raises(GerberImportError, match="explicitly verified"):
        validate_layer_configuration(layer_map, stackup, base_directory=tmp_path)
    validate_layer_configuration(
        layer_map, stackup, base_directory=tmp_path, allow_candidate=True
    )
    stackup["source_revision"] = "different-candidate"
    with pytest.raises(GerberImportError, match="source revisions"):
        validate_layer_configuration(
            layer_map, stackup, base_directory=tmp_path, allow_candidate=True
        )


def test_candidate_layer_configuration_still_requires_geometry(tmp_path):
    layer_map, stackup = _verified_config(tmp_path)
    layer_map["verified"] = stackup["verified"] = False
    layer_map["layers"][0]["gerber_file"] = "../escape.gbr"
    with pytest.raises(GerberImportError, match="must stay under"):
        validate_layer_configuration(
            layer_map, stackup, base_directory=tmp_path, allow_candidate=True
        )


def test_validate_layer_configuration_returns_verified_drill_file_and_span(tmp_path):
    layer_map, stackup = _verified_config(tmp_path)
    (tmp_path / "pth.drl").write_text(DRILL_AND_G85_SLOT_EXCELLON, encoding="ascii")
    layer_map["crop_mm"] = None
    layer_map["drill_files"] = [
        {
            "name": "PTH",
            "excellon_file": "pth.drl",
            "from_layer": "Top",
            "to_layer": "Top",
        }
    ]

    configuration = validate_layer_configuration(
        layer_map, stackup, base_directory=tmp_path
    )

    assert configuration.input_paths == (
        Path("top.gbr"),
        Path("stackup.csv"),
        Path("pth.drl"),
    )
    assert len(configuration.drill_sources) == 1
    drill = configuration.drill_sources[0]
    assert drill.name == "PTH"
    assert drill.source == (tmp_path / "pth.drl").resolve()
    assert drill.from_layer == "Top"
    assert drill.to_layer == "Top"
    board = import_gerbers(
        configuration.gerber_sources,
        configuration.copper_layers,
        drill_sources=configuration.drill_sources,
        crop_bbox_m=configuration.crop_bbox_m,
    )
    assert board.drill_files[0].hit_count == 1
    assert board.drill_files[0].slot_count == 1


@pytest.mark.parametrize(
    ("span", "message"),
    [
        ({"from_layer": "Top", "to_layer": "Missing"}, "explicitly name"),
        ({"from_layer": "Bottom", "to_layer": "Top"}, "reversed"),
    ],
)
def test_layer_configuration_rejects_unverified_drill_spans(
    tmp_path, span, message
):
    layer_map, stackup = _verified_config(tmp_path)
    (tmp_path / "pth.drl").write_text(DRILL_AND_G85_SLOT_EXCELLON, encoding="ascii")
    stackup["copper_layers"].append(
        {"name": "Bottom", "z_mm": 1.6, "thickness_mm": 0.035}
    )
    (tmp_path / "bottom.gbr").write_text(TRACE_GERBER, encoding="ascii")
    layer_map["layers"].append(
        {"name": "Bottom", "gerber_file": "bottom.gbr"}
    )
    layer_map["drill_files"] = [
        {
            "name": "PTH",
            "excellon_file": "pth.drl",
            **span,
        }
    ]

    with pytest.raises(GerberImportError, match=message):
        validate_layer_configuration(layer_map, stackup, base_directory=tmp_path)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("../escape.gbr", "must stay under"),
        ("missing.gbr", "does not exist"),
    ],
)
def test_layer_configuration_rejects_untrusted_paths(tmp_path, value, message):
    layer_map, stackup = _verified_config(tmp_path)
    layer_map["layers"][0]["gerber_file"] = value
    with pytest.raises(GerberImportError, match=message):
        validate_layer_configuration(layer_map, stackup, base_directory=tmp_path)


def test_layer_configuration_requires_explicit_copper_stackup(tmp_path):
    layer_map, stackup = _verified_config(tmp_path)
    stackup["copper_layers"][0]["thickness_mm"] = True
    with pytest.raises(GerberImportError, match="positive thickness_mm"):
        validate_layer_configuration(layer_map, stackup, base_directory=tmp_path)
