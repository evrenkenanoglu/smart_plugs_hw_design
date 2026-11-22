"""Explicit, fail-closed Gerber copper import and CSXCAD conversion.

All public geometry coordinates and stackup elevations are in metres (SI).
Gerbonara coordinates are converted from millimetres. Circular boundaries are
polygonized with a caller-visible maximum chord error; the default is 1 um.
CSXCAD ``AddPolygon`` output is a zero-thickness sheet at the configured z;
``thickness_m`` is retained as stackup metadata and is not extruded.

This module does not infer a ground/reference plane or board outline. Its
Shapely geometries and overlay data are 2D inspection aids, not certification
evidence or a complete electromagnetic model.
"""

from __future__ import annotations

import math
import os
import re
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GerberImportError(ValueError):
    """Raised when Gerber data or explicit physical-layer configuration is unsupported."""


@dataclass(frozen=True)
class CopperLayerSpec:
    """Explicit copper-layer stackup data; ``z_m`` is its sheet elevation."""

    name: str
    z_m: float
    thickness_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise GerberImportError("copper layer name must be a non-empty string")
        if not _is_finite_number(self.z_m):
            raise GerberImportError(f"{self.name}.z_m must be a finite SI value")
        if not _is_finite_number(self.thickness_m) or self.thickness_m <= 0:
            raise GerberImportError(
                f"{self.name}.thickness_m must be a finite positive SI value"
            )
        if not math.isfinite(float(self.z_m) + float(self.thickness_m)):
            raise GerberImportError(f"{self.name} stackup extent must be finite")


@dataclass(frozen=True)
class GerberText:
    """In-memory Gerber source, useful for generated inputs and synthetic tests."""

    text: str
    label: str = "<memory Gerber>"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise GerberImportError("in-memory Gerber text must be a non-empty string")
        if not isinstance(self.label, str) or not self.label.strip():
            raise GerberImportError("Gerber source label must be a non-empty string")


@dataclass(frozen=True)
class ExcellonText:
    """In-memory Excellon source for generated inputs and synthetic tests."""

    text: str
    label: str = "<memory Excellon>"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise GerberImportError("in-memory Excellon text must be a non-empty string")
        if not isinstance(self.label, str) or not self.label.strip():
            raise GerberImportError("Excellon source label must be a non-empty string")


@dataclass(frozen=True)
class DrillSourceSpec:
    """One Excellon file and its explicit inclusive copper-layer span."""

    name: str
    source: str | os.PathLike[str] | ExcellonText
    from_layer: str
    to_layer: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise GerberImportError("drill source name must be a non-empty string")
        if not isinstance(self.source, (str, os.PathLike, ExcellonText)):
            raise GerberImportError(
                f"drill source {self.name!r} must be a path or ExcellonText"
            )
        if not isinstance(self.from_layer, str) or not self.from_layer.strip():
            raise GerberImportError(
                f"drill source {self.name!r} needs an explicit from_layer"
            )
        if not isinstance(self.to_layer, str) or not self.to_layer.strip():
            raise GerberImportError(
                f"drill source {self.name!r} needs an explicit to_layer"
            )


@dataclass(frozen=True)
class ValidatedLayerConfiguration:
    """Revision-locked paths and typed geometry configuration for an import."""

    gerber_sources: Mapping[str, Path]
    copper_layers: tuple[CopperLayerSpec, ...]
    drill_sources: tuple[DrillSourceSpec, ...]
    input_paths: tuple[Path, ...]
    crop_bbox_m: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class LayerGeometry:
    """One explicitly mapped layer and its final crop-clipped 2D copper geometry."""

    name: str
    z_m: float
    thickness_m: float
    geometry: Any
    crop_bbox_m: tuple[float, float, float, float] | None
    arc_tolerance_m: float

    @property
    def polygons(self) -> tuple[Any, ...]:
        """Return exterior polygons; interior rings remain attached as cutouts."""
        return tuple(_polygon_parts(self.geometry))

    def overlay_data(self) -> dict[str, Any]:
        """Return layer polygons and holes as JSON-friendly 2D coordinates in metres."""
        return _layer_overlay_data(self)


@dataclass(frozen=True)
class DrillGeometry:
    """Parsed 2D drill hits and slots for one explicitly configured layer span."""

    name: str
    source_label: str
    from_layer: str
    to_layer: str
    affected_layers: tuple[str, ...]
    hit_count: int
    slot_count: int
    tool_diameters_m: tuple[float, ...]
    plating_status: str
    geometry: Any

    def overlay_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_file": self.source_label,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "affected_layers": list(self.affected_layers),
            "hit_count": self.hit_count,
            "slot_count": self.slot_count,
            "tool_diameters_m": list(self.tool_diameters_m),
            "plating_status": self.plating_status,
            "polygons": _geometry_overlay_polygons(self.geometry),
        }


@dataclass(frozen=True)
class BoardGeometry:
    """Imported 2D copper overlays in the caller's explicit stackup order."""

    layers: tuple[LayerGeometry, ...]
    crop_bbox_m: tuple[float, float, float, float] | None
    arc_tolerance_m: float
    drill_files: tuple[DrillGeometry, ...] = ()

    def layer(self, name: str) -> LayerGeometry:
        """Get a mapped layer by its configured name."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise KeyError(name)

    def overlay_data(self) -> dict[str, Any]:
        """Return a simple 2D overlay structure suitable for plotting or inspection."""
        return {
            "units": "m",
            "coordinate_system": "Gerber X/Y; origin unchanged; positive Y upward",
            "crop_bbox_m": self.crop_bbox_m,
            "arc_tolerance_m": self.arc_tolerance_m,
            "layers": [layer.overlay_data() for layer in self.layers],
            "drill_files": [drill.overlay_data() for drill in self.drill_files],
        }


def import_gerbers(
    layer_map: Mapping[str, str | os.PathLike[str] | GerberText],
    stackup: Sequence[CopperLayerSpec] | Mapping[str, CopperLayerSpec | Mapping[str, Any]],
    *,
    drill_sources: Sequence[DrillSourceSpec] = (),
    crop_bbox_m: Sequence[float] | None = None,
    arc_tolerance_m: float = 1e-6,
) -> BoardGeometry:
    """Import Gerber copper and explicitly spanned Excellon holes and slots.

    ``layer_map`` maps each physical copper-layer name to exactly one Gerber
    path (or :class:`GerberText` for in-memory inputs). ``stackup`` must define
    the same names with explicit ``z_m`` and ``thickness_m`` values. No layer
    role, reference plane, or missing layer is inferred. Each optional drill
    source must specify an inclusive ``from_layer``/``to_layer`` span; no
    through, blind, or buried span is inferred from filenames or drill data.

    Crop bounds are ``(xmin, ymin, xmax, ymax)`` in metres. Clear Gerber
    objects subtract from the preceding image. Excellon tools and coordinate
    formats must be parseable without external assumptions. Unsupported syntax,
    objects, or polarity forms raise :class:`GerberImportError`.
    """
    sources = _validate_layer_map(layer_map)
    layers = _normalize_stackup(stackup)
    source_names, stack_names = set(sources), {layer.name for layer in layers}
    if source_names != stack_names:
        missing = sorted(stack_names - source_names)
        unconfigured = sorted(source_names - stack_names)
        raise GerberImportError(
            "layer map and stackup must name exactly the same copper layers "
            f"(missing Gerbers: {missing}; missing stackup entries: {unconfigured})"
        )

    crop = _validate_crop_bbox(crop_bbox_m)
    tolerance = _validate_arc_tolerance(arc_tolerance_m)
    drill_specs = _normalize_drill_sources(drill_sources, layers)
    by_name = {layer.name: layer for layer in layers}
    imported_layers = list(
        _import_layer(
            name,
            sources[name],
            by_name[name],
            crop_bbox_m=crop,
            arc_tolerance_m=tolerance,
        )
        for name in (layer.name for layer in layers)
    )
    stackup_indices = {layer.name: index for index, layer in enumerate(layers)}
    imported_drills: list[DrillGeometry] = []
    for spec in drill_specs:
        first = stackup_indices[spec.from_layer]
        last = stackup_indices[spec.to_layer]
        affected = tuple(layer.name for layer in layers[first : last + 1])
        drill = _import_drill_source(
            spec,
            affected_layers=affected,
            crop_bbox_m=crop,
            arc_tolerance_m=tolerance,
        )
        imported_drills.append(drill)
        if drill.geometry.is_empty:
            continue
        for layer_index in range(first, last + 1):
            layer = imported_layers[layer_index]
            remaining = layer.geometry.difference(drill.geometry)
            if not remaining.is_valid:
                raise GerberImportError(
                    f"drill source {spec.name!r} produced invalid geometry on "
                    f"copper layer {layer.name!r}"
                )
            imported_layers[layer_index] = LayerGeometry(
                name=layer.name,
                z_m=layer.z_m,
                thickness_m=layer.thickness_m,
                geometry=_polygonal_union_from_geometry(remaining),
                crop_bbox_m=crop,
                arc_tolerance_m=tolerance,
            )
    return BoardGeometry(
        tuple(imported_layers),
        crop,
        tolerance,
        tuple(imported_drills),
    )


def add_copper_layer_to_csx(
    structure: Any,
    layer: LayerGeometry,
    *,
    priority: int = 10,
    property_name: str | None = None,
) -> Any:
    """Add one imported layer using CSXCAD ``AddPolygon([x_values, y_values])``.

    Layers with cutouts are decomposed into interior triangles before adding
    polygons, so clear areas are not filled. Every polygon uses the configured
    ``layer.z_m`` as its z-normal elevation. The copper thickness is metadata
    only; this function deliberately emits a 2D PEC sheet, not a copper volume.
    """
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise GerberImportError("CSXCAD priority must be an integer")
    if not layer.geometry.is_valid:
        raise GerberImportError(f"layer {layer.name} has invalid geometry")

    polygons = _csx_polygon_arrays(layer.geometry)
    if not polygons:
        raise GerberImportError(f"layer {layer.name} has no copper polygons")

    try:
        metal = structure.AddMetal(property_name or layer.name)
        for x_values, y_values in polygons:
            metal.AddPolygon(
                [x_values, y_values],
                norm_dir="z",
                elevation=layer.z_m,
                priority=priority,
            )
        return metal
    except GerberImportError:
        raise
    except Exception as exc:
        raise GerberImportError(
            f"CSXCAD polygon creation failed for layer {layer.name}: {exc}"
        ) from exc


def add_copper_to_csx(
    structure: Any, board: BoardGeometry, *, priority: int = 10
) -> tuple[Any, ...]:
    """Convert all imported copper layers to explicitly elevated CSXCAD sheets."""
    return tuple(
        add_copper_layer_to_csx(structure, layer, priority=priority)
        for layer in board.layers
        if not layer.geometry.is_empty
    )


def write_overlay_png(board: BoardGeometry, output_path: Path) -> Path:
    """Write a labeled, per-layer copper geometry preview without running FDTD."""
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as PlotPolygon
    except ImportError as exc:
        raise GerberImportError(
            "Gerber overlay PNG generation requires the optional matplotlib dependency"
        ) from exc

    output_path = Path(output_path).resolve()
    if output_path.exists():
        raise GerberImportError(f"Refusing to overwrite overlay image: {output_path}")
    if not board.layers:
        raise GerberImportError("cannot plot an empty copper board")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(
        1,
        len(board.layers),
        squeeze=False,
        figsize=(6.0 * len(board.layers), 5.0),
        layout="constrained",
    )
    colors = plt.get_cmap("tab10")
    for index, (axis, layer) in enumerate(zip(axes.ravel(), board.layers)):
        color = colors(index % 10)
        for polygon in layer.polygons:
            axis.add_patch(
                PlotPolygon(
                    list(polygon.exterior.coords),
                    closed=True,
                    facecolor=color,
                    edgecolor="black",
                    linewidth=0.35,
                )
            )
            for ring in polygon.interiors:
                axis.add_patch(
                    PlotPolygon(
                        list(ring.coords),
                        closed=True,
                        facecolor="white",
                        edgecolor="black",
                        linewidth=0.35,
                    )
                )
        for drill in board.drill_files:
            if layer.name not in drill.affected_layers:
                continue
            for polygon in _polygon_parts(drill.geometry):
                rings = (polygon.exterior, *polygon.interiors)
                for ring in rings:
                    x_values, y_values = ring.xy
                    axis.plot(
                        x_values,
                        y_values,
                        color="crimson",
                        linewidth=0.65,
                        linestyle="--",
                    )
        axis.set_aspect("equal", adjustable="datalim")
        axis.set_title(f"{layer.name} (z={layer.z_m:.6g} m)")
        axis.set_xlabel("X (m)")
        axis.set_ylabel("Y (m)")
        axis.autoscale_view()
        axis.grid(True, linewidth=0.25, alpha=0.4)
    figure.suptitle("Imported 2D copper and drills only - not an openEMS simulation")
    try:
        figure.savefig(output_path, dpi=180)
    except OSError as exc:
        raise GerberImportError(
            f"Could not write Gerber overlay {output_path}: {exc}"
        ) from exc
    finally:
        plt.close(figure)
    return output_path


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_layer_configuration(
    layer_map: Mapping[str, Any],
    stackup: Mapping[str, Any],
    *,
    base_directory: Path,
    allow_candidate: bool = False,
) -> ValidatedLayerConfiguration:
    """Validate Gerber, stackup, and explicit Excellon drill inputs.

    Drill entries use ``{name, excellon_file, from_layer, to_layer}``; their
    inclusive spans must refer to the explicitly ordered ``copper_layers``.
    ``input_paths`` are relative to ``base_directory`` for manifest checks,
    while returned source paths are resolved paths ready for import.
    Candidate mode permits explicitly unverified configurations, not missing
    geometry, source paths, or consistent candidate identifiers.
    """
    if not isinstance(layer_map, Mapping) or not isinstance(stackup, Mapping):
        raise GerberImportError("layer map and stackup must be JSON objects")
    if any(not isinstance(config.get("verified"), bool) for config in (layer_map, stackup)):
        raise GerberImportError("layer map and stackup must state verified as a boolean")
    if not allow_candidate and (
        layer_map["verified"] is not True or stackup["verified"] is not True
    ):
        raise GerberImportError("layer map and stackup must be explicitly verified")
    revision = layer_map.get("source_revision")
    if (
        not isinstance(revision, str)
        or not revision.strip()
        or revision.strip().upper() in {"UNCONFIRMED", "TODO", "TODO_VERIFY_FROM_STAGE_0"}
    ):
        raise GerberImportError("layer-map source_revision must be confirmed")
    if stackup.get("source_revision") != revision:
        raise GerberImportError("layer map and stackup source revisions do not match")

    raw_layers = layer_map.get("layers")
    raw_copper = stackup.get("copper_layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise GerberImportError("layer map must define at least one copper Gerber")
    if not isinstance(raw_copper, list) or not raw_copper:
        raise GerberImportError("stackup must define at least one copper layer")

    root = Path(base_directory).resolve()

    def resolve_input(filename: Any, description: str) -> tuple[Path, Path]:
        if not isinstance(filename, str) or not filename.strip():
            raise GerberImportError(f"{description} needs a non-empty path")
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise GerberImportError(
                f"{description} path must stay under locked input directory: {filename}"
            )
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise GerberImportError(
                f"{description} path escapes locked input directory: {filename}"
            ) from exc
        if not resolved.is_file():
            raise GerberImportError(f"Configured {description} does not exist: {filename}")
        return relative, resolved

    gerber_sources: dict[str, Path] = {}
    gerber_paths: list[Path] = []
    names: list[str] = []
    for entry in raw_layers:
        if not isinstance(entry, Mapping):
            raise GerberImportError("each layer-map entry must be an object")
        name = entry.get("name")
        filename = entry.get("gerber_file")
        if not isinstance(name, str) or not name.strip():
            raise GerberImportError("each mapped copper layer needs a name")
        relative, resolved = resolve_input(filename, f"Gerber for layer {name!r}")
        names.append(name)
        gerber_paths.append(relative)
        gerber_sources[name] = resolved
    if len(set(names)) != len(names):
        raise GerberImportError("layer-map copper names must be unique")

    stackup_names: list[str] = []
    copper_layers: list[CopperLayerSpec] = []
    for entry in raw_copper:
        if not isinstance(entry, Mapping):
            raise GerberImportError("each stackup copper layer must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise GerberImportError("each stackup copper layer needs a name")
        z_mm = entry.get("z_mm")
        thickness_mm = entry.get("thickness_mm")
        if (
            not _is_finite_number(z_mm)
            or not _is_finite_number(thickness_mm)
            or thickness_mm <= 0
        ):
            raise GerberImportError(
                f"stackup copper layer {name!r} needs finite z_mm and positive "
                "thickness_mm"
            )
        copper_layers.append(CopperLayerSpec(
            name=name,
            z_m=float(z_mm) * 1e-3,
            thickness_m=float(thickness_mm) * 1e-3,
        ))
        stackup_names.append(name)
    if len(set(stackup_names)) != len(stackup_names):
        raise GerberImportError("stackup copper-layer names must be unique")
    if set(names) != set(stackup_names):
        raise GerberImportError(
            "layer map and stackup must define exactly the same copper layers"
        )

    board_thickness = stackup.get("board_thickness_mm")
    if not _is_finite_number(board_thickness) or board_thickness <= 0:
        raise GerberImportError("stackup board_thickness_mm must be verified and positive")
    stackup_source = stackup.get("source_file")
    if not isinstance(stackup_source, str) or not stackup_source.strip():
        raise GerberImportError("stackup source_file must identify verified evidence")
    source_relative = Path(stackup_source)
    if source_relative.is_absolute() or ".." in source_relative.parts:
        raise GerberImportError(
            f"stackup source_file must stay under locked input directory: {stackup_source}"
        )
    source_path = (root / source_relative).resolve()
    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise GerberImportError(
            f"stackup source_file escapes locked input directory: {stackup_source}"
        ) from exc
    if not source_path.is_file():
        raise GerberImportError(
            f"Configured stackup evidence does not exist: {stackup_source}"
        )

    raw_drills = layer_map.get("drill_files", [])
    if not isinstance(raw_drills, list):
        raise GerberImportError("layer-map drill_files must be a list")
    stackup_indices = {name: index for index, name in enumerate(stackup_names)}
    drill_names: set[str] = set()
    drill_sources: list[DrillSourceSpec] = []
    drill_paths: list[Path] = []
    for entry in raw_drills:
        if not isinstance(entry, Mapping):
            raise GerberImportError("each drill-file entry must be an object")
        name = entry.get("name")
        from_layer = entry.get("from_layer")
        to_layer = entry.get("to_layer")
        if not isinstance(name, str) or not name.strip():
            raise GerberImportError("each drill file needs a non-empty name")
        if name in drill_names:
            raise GerberImportError(f"drill-file names must be unique: {name!r}")
        if (
            not isinstance(from_layer, str)
            or not isinstance(to_layer, str)
            or from_layer not in stackup_indices
            or to_layer not in stackup_indices
        ):
            raise GerberImportError(
                f"drill file {name!r} must explicitly name copper layers in its span"
            )
        if stackup_indices[from_layer] > stackup_indices[to_layer]:
            raise GerberImportError(
                f"drill file {name!r} has a reversed copper-layer span"
            )
        relative, resolved = resolve_input(
            entry.get("excellon_file"), f"Excellon drill file {name!r}"
        )
        drill_names.add(name)
        drill_paths.append(relative)
        drill_sources.append(
            DrillSourceSpec(
                name=name,
                source=resolved,
                from_layer=from_layer,
                to_layer=to_layer,
            )
        )

    crop_mm = layer_map.get("crop_mm")
    if crop_mm is not None:
        if (
            isinstance(crop_mm, (str, bytes))
            or not isinstance(crop_mm, Sequence)
            or len(crop_mm) != 4
            or any(not _is_finite_number(value) for value in crop_mm)
        ):
            raise GerberImportError("crop_mm must be four finite millimetre bounds")
        _validate_crop_bbox(tuple(float(value) * 1e-3 for value in crop_mm))
    return ValidatedLayerConfiguration(
        gerber_sources=gerber_sources,
        copper_layers=tuple(copper_layers),
        drill_sources=tuple(drill_sources),
        input_paths=tuple([*gerber_paths, source_relative, *drill_paths]),
        crop_bbox_m=(
            tuple(float(value) * 1e-3 for value in crop_mm)
            if crop_mm is not None
            else None
        ),
    )


def _validate_layer_map(
    layer_map: Mapping[str, str | os.PathLike[str] | GerberText],
) -> dict[str, str | os.PathLike[str] | GerberText]:
    if not isinstance(layer_map, Mapping) or not layer_map:
        raise GerberImportError("an explicit, non-empty Gerber layer map is required")
    result: dict[str, str | os.PathLike[str] | GerberText] = {}
    for name, source in layer_map.items():
        if not isinstance(name, str) or not name.strip():
            raise GerberImportError("each mapped copper layer needs a non-empty name")
        if not isinstance(source, (str, os.PathLike, GerberText)):
            raise GerberImportError(
                f"Gerber source for {name} must be a path or GerberText"
            )
        result[name] = source
    return result


def _normalize_stackup(
    stackup: Sequence[CopperLayerSpec]
    | Mapping[str, CopperLayerSpec | Mapping[str, Any]],
) -> tuple[CopperLayerSpec, ...]:
    if isinstance(stackup, Mapping):
        candidates: list[CopperLayerSpec] = []
        for name, value in stackup.items():
            if isinstance(value, CopperLayerSpec):
                if value.name != name:
                    raise GerberImportError(
                        f"stackup key {name!r} does not match layer {value.name!r}"
                    )
                candidates.append(value)
            elif isinstance(value, Mapping):
                candidates.append(
                    CopperLayerSpec(
                        name=name,
                        z_m=value.get("z_m"),
                        thickness_m=value.get("thickness_m"),
                    )
                )
            else:
                raise GerberImportError(
                    f"stackup entry {name!r} needs explicit z_m and thickness_m"
                )
    elif isinstance(stackup, Sequence) and not isinstance(stackup, (str, bytes)):
        candidates = list(stackup)
    else:
        raise GerberImportError("an explicit copper-layer stackup is required")

    if not candidates:
        raise GerberImportError("stackup must define at least one copper layer")
    if any(not isinstance(layer, CopperLayerSpec) for layer in candidates):
        raise GerberImportError("stackup entries must be CopperLayerSpec values")
    names = [layer.name for layer in candidates]
    if len(set(names)) != len(names):
        raise GerberImportError("stackup copper-layer names must be unique")
    return tuple(candidates)


def _normalize_drill_sources(
    drill_sources: Sequence[DrillSourceSpec],
    stackup: Sequence[CopperLayerSpec],
) -> tuple[DrillSourceSpec, ...]:
    if not isinstance(drill_sources, Sequence) or isinstance(
        drill_sources, (str, bytes)
    ):
        raise GerberImportError("drill_sources must be a sequence of DrillSourceSpec")
    indices = {layer.name: index for index, layer in enumerate(stackup)}
    seen: set[str] = set()
    result: list[DrillSourceSpec] = []
    for spec in drill_sources:
        if not isinstance(spec, DrillSourceSpec):
            raise GerberImportError("each drill source must be a DrillSourceSpec")
        if spec.name in seen:
            raise GerberImportError(f"duplicate drill source name: {spec.name}")
        if spec.from_layer not in indices or spec.to_layer not in indices:
            raise GerberImportError(
                f"drill source {spec.name!r} must explicitly name copper "
                "layers in its span"
            )
        if indices[spec.from_layer] > indices[spec.to_layer]:
            raise GerberImportError(
                f"drill source {spec.name!r} has a reversed copper-layer span"
            )
        seen.add(spec.name)
        result.append(spec)
    return tuple(result)


def _validate_crop_bbox(
    crop_bbox_m: Sequence[float] | None,
) -> tuple[float, float, float, float] | None:
    if crop_bbox_m is None:
        return None
    if (
        isinstance(crop_bbox_m, (str, bytes))
        or not isinstance(crop_bbox_m, Sequence)
        or len(crop_bbox_m) != 4
    ):
        raise GerberImportError(
            "crop_bbox_m must be (xmin, ymin, xmax, ymax) in metres"
        )
    if any(not _is_finite_number(value) for value in crop_bbox_m):
        raise GerberImportError("crop_bbox_m bounds must be finite numeric values")
    xmin, ymin, xmax, ymax = (float(value) for value in crop_bbox_m)
    if xmin >= xmax or ymin >= ymax:
        raise GerberImportError("crop_bbox_m bounds must be strictly increasing")
    return xmin, ymin, xmax, ymax


def _validate_arc_tolerance(value: float) -> float:
    if not _is_finite_number(value) or value <= 0:
        raise GerberImportError("arc_tolerance_m must be a finite positive SI value")
    tolerance = float(value)
    if not math.isfinite(tolerance * 1000.0):
        raise GerberImportError("arc_tolerance_m is too large to polygonize reliably")
    return tolerance


def _load_gerber(source: str | os.PathLike[str] | GerberText) -> tuple[Any, str]:
    try:
        from gerbonara.rs274x import GerberFile
    except ImportError as exc:
        raise GerberImportError(
            "Gerber import requires the optional 'gerber' extra "
            "(gerbonara and shapely); no packages were installed"
        ) from exc

    if isinstance(source, GerberText):
        text = source.text
        label = source.label
    else:
        path = Path(source)
        label = str(path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise GerberImportError(f"Could not read Gerber {label}: {exc}") from exc

    if re.search(r"(?:^|[%*])\s*IPNEG\s*\*(?:[%*]|$)", text, re.IGNORECASE | re.MULTILINE):
        raise GerberImportError(
            f"{label}: negative image polarity (IPNEG) is unsupported; "
            "no copper geometry was emitted"
        )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parsed = GerberFile.from_string(text, filename=label)
    except Exception as exc:
        raise GerberImportError(f"Could not parse Gerber {label}: {exc}") from exc
    if caught:
        details = "; ".join(str(item.message) for item in caught)
        raise GerberImportError(
            f"{label}: Gerbonara reported unsupported or non-canonical input "
            f"({details}); refusing to emit geometry"
        )
    return parsed, label


def _load_excellon(source: str | os.PathLike[str] | ExcellonText) -> tuple[Any, str]:
    try:
        from gerbonara.excellon import ExcellonFile
        from gerbonara.utils import Inch, MM
    except ImportError as exc:
        raise GerberImportError(
            "Excellon import requires the optional 'gerber' extra "
            "(gerbonara and shapely); no packages were installed"
        ) from exc

    if isinstance(source, ExcellonText):
        text = source.text
        label = source.label
    else:
        path = Path(source)
        label = str(path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise GerberImportError(f"Could not read Excellon {label}: {exc}") from exc

    if _has_fixed_width_values(text):
        if not _has_explicit_excellon_number_format(text):
            raise GerberImportError(
                f"{label}: fixed-width Excellon coordinates or tool values need "
                "an explicit integer/fraction format"
            )
        if not _has_explicit_excellon_zero_mode(text):
            raise GerberImportError(
                f"{label}: fixed-width Excellon coordinates or tool values need "
                "an explicit LZ/TZ zero-suppression declaration"
            )

    has_incremental_mode = bool(re.search(r"(?im)^\s*G91\s*$", text))
    if has_incremental_mode:
        raise GerberImportError(
            f"{label}: incremental Excellon coordinates are unsupported"
        )
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            # from_string deliberately avoids Gerbonara's neighboring sidecar
            # lookup. Only format declarations in this Excellon file are used.
            parsed = ExcellonFile.from_string(text, filename=label)
    except Exception as exc:
        raise GerberImportError(f"Could not parse Excellon {label}: {exc}") from exc
    # EasyEDA emits an absolute-mode G90 after the header. Gerbonara applies
    # it but warns because its parser classifies the command as header-only.
    # Accept only this warning and only if the file never selects incremental
    # mode; other warnings remain fatal.
    unsupported = [
        item for item in caught
        if not str(item.message).endswith(
            '"G90": G90 header statement found after end of header'
        )
    ]
    if unsupported:
        details = "; ".join(str(item.message) for item in unsupported)
        raise GerberImportError(
            f"{label}: Gerbonara reported unsupported or ambiguous Excellon "
            f"input ({details}); refusing to emit drill geometry"
        )
    settings = parsed.import_settings
    if settings.unit not in (MM, Inch):
        raise GerberImportError(
            f"{label}: Excellon length unit is not explicit; refusing to guess"
        )
    if not settings.is_absolute:
        raise GerberImportError(
            f"{label}: incremental Excellon coordinates are unsupported"
        )
    has_fixed_width_values = (
        settings._file_has_fixed_width_coordinates
        or _has_fixed_width_tool_parameters(text)
    )
    if has_fixed_width_values:
        number_format = settings.number_format
        valid_format = (
            isinstance(number_format, tuple)
            and len(number_format) == 2
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value > 0
                for value in number_format
            )
        )
        explicit_zero_mode = _has_explicit_excellon_zero_mode(text)
        if not valid_format or settings.zeros not in ("leading", "trailing"):
            raise GerberImportError(
                f"{label}: fixed-width Excellon coordinates or tool values "
                "need an explicit integer/fraction format"
            )
        if not explicit_zero_mode:
            raise GerberImportError(
                f"{label}: fixed-width Excellon coordinates or tool values "
                "need an explicit LZ/TZ zero-suppression declaration"
            )
    if not parsed.objects:
        raise GerberImportError(f"{label}: Excellon contains no drill hits or slots")
    return parsed, label


def _has_fixed_width_values(text: str) -> bool:
    if _has_fixed_width_tool_parameters(text):
        return True
    for line in text.splitlines():
        if line.lstrip().startswith(";"):
            continue
        if any(
            "." not in value
            for value in re.findall(r"[XYIJ]([+-]?[0-9.]+)", line, re.I)
        ):
            return True
    return False


def _has_explicit_excellon_number_format(text: str) -> bool:
    patterns = (
        r"(?im)^\s*;\s*FILE_FORMAT\s*=\s*[0-9]+:[0-9]+\s*$",
        r"(?im)^\s*;\s*FORMAT\s*=\s*\{[-0-9]+:[-0-9]+",
        r"(?im)^\s*(?:METRIC|INCH|M71|M72)(?:\s*,(?:LZ|TZ))?"
        r"\s*,\s*[0-9]+\.[0-9]+(?:\s*,[^\r\n]*)?\s*$",
        r"(?im)^\s*;\s*Format\s*:\s*[0-9]+\.[0-9]+\s*/",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _has_explicit_excellon_zero_mode(text: str) -> bool:
    patterns = (
        r"(?im)^\s*(?:METRIC|INCH|M71|M72)\s*,\s*(?:LZ|TZ)"
        r"(?:\s*,[^\r\n]*)?\s*$",
        r"(?im)^\s*;\s*Format\s*:\s*[0-9]+\.[0-9]+\s*/\s*"
        r"(?:Absolute|Incremental)\s*/\s*(?:Inch|MM)\s*/\s*"
        r"(?:Leading|Trailing)\s*$",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _has_fixed_width_tool_parameters(text: str) -> bool:
    for line in text.splitlines():
        match = re.fullmatch(r"\s*T[0-9]+((?:[A-Z][.0-9]+)+)\s*", line, re.I)
        if match:
            values = re.findall(r"[A-Z]([.0-9]+)", match[1], re.I)
            if any("." not in value for value in values):
                return True
    return False


def _import_drill_source(
    spec: DrillSourceSpec,
    *,
    affected_layers: tuple[str, ...],
    crop_bbox_m: tuple[float, float, float, float] | None,
    arc_tolerance_m: float,
) -> DrillGeometry:
    parsed, label = _load_excellon(spec.source)
    try:
        from gerbonara import graphic_objects as go
        from gerbonara import graphic_primitives as gp
        from gerbonara.apertures import ExcellonTool
        from gerbonara.utils import MM
        from shapely.affinity import scale
        from shapely.geometry import GeometryCollection, box
        from shapely.ops import unary_union
    except ImportError as exc:
        raise GerberImportError(
            "Excellon polygonization requires gerbonara and shapely 2.x"
        ) from exc

    shapes = []
    tool_diameters_mm: set[float] = set()
    plating_states: set[bool | None] = set()
    hit_count = 0
    slot_count = 0
    for obj in parsed.objects:
        if isinstance(obj, go.Flash):
            expected_primitive = gp.Circle
            hit_count += 1
        elif isinstance(obj, go.Line):
            if math.dist(obj.p1, obj.p2) == 0:
                raise GerberImportError(
                    f"{label}: zero-length Excellon slot is ambiguous"
                )
            expected_primitive = gp.Line
            slot_count += 1
        elif isinstance(obj, go.Arc):
            expected_primitive = gp.Arc
            slot_count += 1
        else:
            raise GerberImportError(
                f"{label}: unsupported Excellon object {type(obj).__name__}; "
                "only drill hits and tool-width slots are supported"
            )

        tool = getattr(obj, "tool", None)
        if not isinstance(tool, ExcellonTool):
            raise GerberImportError(
                f"{label}: {type(obj).__name__} does not use a verified circular "
                "Excellon tool"
            )
        diameter_mm = float(tool.equivalent_width(MM))
        if not math.isfinite(diameter_mm) or diameter_mm <= 0:
            raise GerberImportError(f"{label}: Excellon tool diameter is invalid")
        tool_diameters_mm.add(diameter_mm)
        plating_states.add(getattr(obj, "plated", None))
        try:
            primitives = list(obj.to_primitives(unit=MM))
        except Exception as exc:
            raise GerberImportError(
                f"{label}: cannot polygonize Excellon {type(obj).__name__}: {exc}"
            ) from exc
        if len(primitives) != 1 or not isinstance(primitives[0], expected_primitive):
            raise GerberImportError(
                f"{label}: Excellon {type(obj).__name__} did not produce its "
                "documented hit/slot primitive"
            )
        shapes.append(
            _primitive_polygon(
                primitives[0],
                tolerance_mm=arc_tolerance_m * 1000.0,
            )
        )

    drill_mm = unary_union(shapes)
    if not drill_mm.is_valid:
        raise GerberImportError(f"{label}: drill/slot union produced invalid geometry")
    if crop_bbox_m is not None:
        crop_mm = tuple(value * 1000.0 for value in crop_bbox_m)
        drill_mm = drill_mm.intersection(box(*crop_mm))
    drill_mm = _polygonal_union(drill_mm, GeometryCollection, unary_union)
    drill_m = scale(drill_mm, xfact=0.001, yfact=0.001, origin=(0, 0))
    if not drill_m.is_valid:
        raise GerberImportError(f"{label}: cropped drill geometry is invalid")

    if plating_states == {True}:
        plating_status = "plated"
    elif plating_states == {False}:
        plating_status = "nonplated"
    elif plating_states == {None}:
        plating_status = "unknown"
    else:
        plating_status = "mixed"

    return DrillGeometry(
        name=spec.name,
        source_label=Path(label).name if not isinstance(spec.source, ExcellonText) else label,
        from_layer=spec.from_layer,
        to_layer=spec.to_layer,
        affected_layers=affected_layers,
        hit_count=hit_count,
        slot_count=slot_count,
        tool_diameters_m=tuple(sorted(value * 1e-3 for value in tool_diameters_mm)),
        plating_status=plating_status,
        geometry=drill_m,
    )


def _import_layer(
    name: str,
    source: str | os.PathLike[str] | GerberText,
    spec: CopperLayerSpec,
    *,
    crop_bbox_m: tuple[float, float, float, float] | None,
    arc_tolerance_m: float,
) -> LayerGeometry:
    parsed, label = _load_gerber(source)
    if not parsed.objects:
        raise GerberImportError(f"{label}: Gerber contains no copper objects")

    try:
        from gerbonara.apertures import CircleAperture
        from gerbonara import graphic_objects as go
        from gerbonara import graphic_primitives as gp
        from gerbonara.utils import MM
        from shapely.affinity import scale
        from shapely.geometry import GeometryCollection, box
        from shapely.ops import unary_union
    except ImportError as exc:
        raise GerberImportError(
            "Gerber polygonization requires gerbonara and shapely 2.x"
        ) from exc

    supported_objects = (go.Flash, go.Line, go.Arc, go.Region)
    supported_primitives = (gp.Circle, gp.Rectangle, gp.Line, gp.Arc, gp.ArcPoly)
    copper_mm = GeometryCollection()
    tolerance_mm = arc_tolerance_m * 1000.0
    topology_changes = {
        "normalized_regions": 0,
        "removed_zero_length_edges": 0,
    }

    for obj in parsed.objects:
        if not isinstance(obj, supported_objects):
            raise GerberImportError(
                f"{label}: unsupported Gerber object {type(obj).__name__}; "
                "refusing to approximate it"
            )
        if isinstance(obj, (go.Line, go.Arc)):
            aperture = getattr(obj, "aperture", None)
            if not isinstance(aperture, CircleAperture):
                raise GerberImportError(
                    f"{label}: {type(obj).__name__} with non-circular aperture "
                    "is unsupported; Gerbonara's low-level conversion would "
                    "otherwise reduce it to an equivalent-width stroke"
                )
            hole_diameter = getattr(aperture, "hole_dia", None)
            if hole_diameter is not None and float(hole_diameter) > 0:
                raise GerberImportError(
                    f"{label}: {type(obj).__name__} using a holed aperture is "
                    "unsupported; no cutout may be silently dropped"
                )
        object_dark = getattr(obj, "polarity_dark", None)
        if not isinstance(object_dark, bool):
            raise GerberImportError(
                f"{label}: object {type(obj).__name__} has unknown polarity"
            )
        try:
            primitives = list(obj.to_primitives(unit=MM))
        except Exception as exc:
            raise GerberImportError(
                f"{label}: cannot polygonize {type(obj).__name__}: {exc}"
            ) from exc
        if not primitives:
            raise GerberImportError(
                f"{label}: {type(obj).__name__} produced no geometry"
            )

        object_mask = GeometryCollection()
        for primitive in primitives:
            if not isinstance(primitive, supported_primitives):
                raise GerberImportError(
                    f"{label}: unsupported Gerbonara primitive "
                    f"{type(primitive).__name__}; refusing to flatten it"
                )
            primitive_dark = getattr(primitive, "polarity_dark", None)
            if not isinstance(primitive_dark, bool):
                raise GerberImportError(
                    f"{label}: primitive {type(primitive).__name__} has unknown polarity"
                )
            shape = _primitive_polygon(
                primitive,
                tolerance_mm=tolerance_mm,
                allow_region_fill=isinstance(obj, go.Region),
                topology_changes=topology_changes,
            )
            # Gerbonara flips each aperture feature's polarity with its owning
            # object. Normalize those local features first, then apply the
            # object polarity once to the complete aperture/region mask.
            if primitive_dark == object_dark:
                object_mask = object_mask.union(shape)
            else:
                object_mask = object_mask.difference(shape)

        if object_dark:
            copper_mm = copper_mm.union(object_mask)
        else:
            copper_mm = copper_mm.difference(object_mask)
        if not copper_mm.is_valid:
            raise GerberImportError(
                f"{label}: polarity composition produced invalid geometry"
            )

    if any(topology_changes.values()):
        warnings.warn(
            f"{label}: normalized {topology_changes['normalized_regions']} "
            "self-touching G36/G37 region(s) with Shapely make_valid(linework) "
            f"and removed {topology_changes['removed_zero_length_edges']} "
            "zero-length outline edge(s); inspect the geometry before modeling",
            RuntimeWarning,
            stacklevel=2,
        )
    if copper_mm.is_empty:
        raise GerberImportError(f"{label}: polarity resolves to no copper")
    if crop_bbox_m is not None:
        crop_mm = tuple(value * 1000.0 for value in crop_bbox_m)
        if any(not math.isfinite(value) for value in crop_mm):
            raise GerberImportError(f"{label}: crop_bbox_m exceeds Gerber millimetre range")
        copper_mm = copper_mm.intersection(box(*crop_mm))
    polygonal_mm = _polygonal_union(copper_mm, GeometryCollection, unary_union)
    if polygonal_mm.is_empty:
        raise GerberImportError(
            f"{label}: crop contains no copper; refusing to emit empty geometry"
        )
    geometry_m = scale(polygonal_mm, xfact=0.001, yfact=0.001, origin=(0, 0))
    if not geometry_m.is_valid:
        raise GerberImportError(f"{label}: final cropped geometry is invalid")
    return LayerGeometry(
        name=name,
        z_m=spec.z_m,
        thickness_m=spec.thickness_m,
        geometry=geometry_m,
        crop_bbox_m=crop_bbox_m,
        arc_tolerance_m=arc_tolerance_m,
    )


def _primitive_polygon(
    primitive: Any,
    *,
    tolerance_mm: float,
    allow_region_fill: bool = False,
    topology_changes: dict[str, int] | None = None,
) -> Any:
    from shapely import make_valid
    from shapely.geometry import GeometryCollection, Polygon
    from shapely.ops import unary_union

    try:
        arc_poly = primitive.to_arc_poly()
        arc_poly, removed_edges = _remove_zero_length_edges(arc_poly)
        polygonized = arc_poly.approximate_arcs(max_error=tolerance_mm)
        coordinates = [
            (float(point[0]), float(point[1])) for point in polygonized.outline
        ]
    except Exception as exc:
        raise GerberImportError(
            f"cannot approximate Gerber primitive {type(primitive).__name__}: {exc}"
        ) from exc

    if topology_changes is not None:
        topology_changes["removed_zero_length_edges"] += removed_edges
    if len(coordinates) < 3 or any(
        not math.isfinite(value) for point in coordinates for value in point
    ):
        raise GerberImportError(
            f"primitive {type(primitive).__name__} has invalid polygon coordinates"
        )
    polygon = Polygon(coordinates)
    if polygon.is_empty or polygon.area <= 0:
        raise GerberImportError(
            f"primitive {type(primitive).__name__} is degenerate or self-intersecting; "
            "geometry repair is intentionally disabled"
        )
    if not polygon.is_valid and allow_region_fill:
        try:
            normalized = make_valid(polygon, method="linework")
            polygon = _polygonal_union(
                normalized,
                GeometryCollection,
                unary_union,
            )
            if topology_changes is not None:
                topology_changes["normalized_regions"] += 1
        except Exception as exc:
            raise GerberImportError(
                f"Gerber region topology normalization failed: {exc}"
            ) from exc
    if not polygon.is_valid:
        raise GerberImportError(
            f"primitive {type(primitive).__name__} is degenerate or self-intersecting; "
            "geometry repair is intentionally disabled"
        )
    if polygon.is_empty or polygon.area <= 0:
        raise GerberImportError(
            "Gerber region contains no polygonal area after topology normalization"
        )
    return polygon


def _remove_zero_length_edges(arc_poly: Any) -> tuple[Any, int]:
    outline = list(arc_poly.outline)
    centers = arc_poly.arc_centers
    if not outline or centers is None or len(centers) != len(outline):
        return arc_poly, 0

    kept_outline = []
    kept_centers = []
    removed = 0
    for index, start in enumerate(outline):
        end = outline[(index + 1) % len(outline)]
        center = centers[index]
        zero_length = start == end and (
            center is None
            or center[0] is None
            or center[1] == start
        )
        if zero_length:
            removed += 1
        else:
            kept_outline.append(start)
            kept_centers.append(center)
    if not removed:
        return arc_poly, 0
    if len(kept_outline) < 3:
        raise GerberImportError(
            "primitive collapses after removing zero-length outline edges"
        )
    return (
        type(arc_poly)(
            kept_outline,
            kept_centers,
            polarity_dark=arc_poly.polarity_dark,
        ),
        removed,
    )


def _polygon_parts(geometry: Any) -> list[Any]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry] if geometry.area > 0 else []
    if geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [
            polygon
            for item in geometry.geoms
            for polygon in _polygon_parts(item)
        ]
    return []


def _polygonal_union(geometry: Any, geometry_collection: Any, unary_union: Any) -> Any:
    polygons = _polygon_parts(geometry)
    if not polygons:
        return geometry_collection()
    result = unary_union(polygons)
    if not result.is_valid:
        raise GerberImportError("polygon union produced invalid geometry")
    return result


def _polygonal_union_from_geometry(geometry: Any) -> Any:
    try:
        from shapely.geometry import GeometryCollection
        from shapely.ops import unary_union
    except ImportError as exc:
        raise GerberImportError("polygon geometry requires shapely 2.x") from exc
    return _polygonal_union(geometry, GeometryCollection, unary_union)


def _geometry_overlay_polygons(geometry: Any) -> list[dict[str, Any]]:
    return [
        {
            "exterior": [(float(x), float(y)) for x, y in polygon.exterior.coords],
            "holes": [
                [(float(x), float(y)) for x, y in ring.coords]
                for ring in polygon.interiors
            ],
        }
        for polygon in _polygon_parts(geometry)
    ]


def _layer_overlay_data(layer: LayerGeometry) -> dict[str, Any]:
    return {
        "name": layer.name,
        "z_m": layer.z_m,
        "thickness_m": layer.thickness_m,
        "arc_tolerance_m": layer.arc_tolerance_m,
        "polygons": _geometry_overlay_polygons(layer.geometry),
    }


def _csx_polygon_arrays(geometry: Any) -> list[tuple[list[float], list[float]]]:
    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate, unary_union
    except ImportError as exc:
        raise GerberImportError("CSXCAD conversion requires shapely 2.x") from exc

    result: list[tuple[list[float], list[float]]] = []
    for polygon in _polygon_parts(geometry):
        if polygon.interiors:
            pieces = [
                triangle
                for triangle in triangulate(polygon)
                if triangle.area > 0 and polygon.covers(triangle)
            ]
            if not pieces:
                raise GerberImportError(
                    "could not decompose a copper polygon with cutouts; "
                    "refusing to fill or discard its holes"
                )
            decomposed = unary_union(pieces)
            error = decomposed.symmetric_difference(polygon).area
            allowed_error = max(polygon.area * 1e-10, 1e-30)
            if error > allowed_error:
                raise GerberImportError(
                    "CSXCAD cutout decomposition changed copper area; "
                    "refusing to emit an inaccurate polygon set"
                )
        else:
            pieces = [polygon]

        for piece in pieces:
            if not isinstance(piece, Polygon) or piece.interiors:
                raise GerberImportError(
                    "CSXCAD conversion produced a non-simple polygon"
                )
            points = list(piece.exterior.coords)[:-1]
            if len(points) < 3:
                raise GerberImportError("CSXCAD polygon has fewer than three vertices")
            result.append(
                (
                    [float(point[0]) for point in points],
                    [float(point[1]) for point in points],
                )
            )
    return result
