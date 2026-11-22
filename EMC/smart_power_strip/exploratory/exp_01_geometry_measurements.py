"""Reproduce limited, non-simulation measurements of the Nov 21 candidate."""

import csv
import hashlib
import json
import math
import re
import sys
import warnings
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import gerbonara
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "EMC"))
import emc_sim.gerber_import as gi

STAMP = "EXPLORATORY PRE-DESIGN SIMULATION ON CANDIDATE FILES — NOT SAFETY OR COMPLIANCE PROOF"
SOURCE = ROOT / "EMC" / "smart_power_strip" / "inputs" / "locked_rev" / "MAIN_OMRON" / "MCP_CANDIDATE_20261121_1753"
PREFIX = "MCP_CANDIDATE_20261121_1753_MAIN_OMRON_"
EXPECTED = {
    PREFIX + "Gerbers.zip": "b6dddaf2be7855431e044350a63596575af5b4ee48bbcb2ec1d888b43b297e88",
    PREFIX + "Netlist.pads": "2258d3c24cb4964cf5eed88bb7dddddda13e12d7c0c0451c622ee99166d82f9f",
    PREFIX + "PnP.csv": "b57e4de54f7c271e63a6741f8a26a4b491838c3462c17e8d8a88e09e5d5ffa6a",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    files = {name: (SOURCE / name).read_bytes() for name in EXPECTED}
    for name, expected in EXPECTED.items():
        if digest(files[name]) != expected:
            raise ValueError(f"Candidate hash changed: {name}")
    with zipfile.ZipFile(SOURCE / (PREFIX + "Gerbers.zip")) as archive:
        names = {
            "top": "Gerber_TopLayer.GTL",
            "bottom": "Gerber_BottomLayer.GBL",
            "outline_graphics": "Gerber_BoardOutlineLayer.GKO",
        }
        entries = {name: archive.read(name) for name in [*names.values(), "Drill_PTH_Through.DRL", "Drill_PTH_Through_Via.DRL", "FlyingProbeTesting.json"]}
    probe = json.loads(entries["FlyingProbeTesting.json"])
    if probe["lengthUnit"] != "mil":
        raise ValueError("Unexpected probe units")
    rows = [dict(zip(probe["pins"]["fields"], row)) for row in probe["pins"]["rows"]]
    pin_rows = {}
    for row in rows:
        name = row["PIN_NAME"]
        if name in pin_rows:
            old = pin_rows[name]
            if any(row[k] != old[k] for k in ("PIN_X", "PIN_Y", "NET_NAME", "PIN_TYPE", "LAYER")):
                raise ValueError(f"Conflicting duplicate probe pin {name}")
        pin_rows[name] = row

    pad_nets = {}
    net = None
    for line in files[PREFIX + "Netlist.pads"].decode("utf-8-sig").splitlines():
        if line.startswith("*SIGNAL* "):
            net = line.split(maxsplit=1)[1]
        elif line.startswith("*"):
            net = None
        elif net:
            for pin in line.split():
                pad_nets[pin.replace(".", "_")] = net
    relevant_pins = (
        ["L1_3", *(f"U1_{i}" for i in range(1, 7)), "CY1_1", "CY1_2"]
        + [f"FT_{side}{i}_{pin}" for i in range(1, 5) for side in ("IN", "OUT") for pin in (1, 2)]
        + [f"K{i}_{pin}" for i in range(1, 5) for pin in (3, 4, 5, 6)]
    )
    for pin in relevant_pins:
        if pin_rows[pin]["NET_NAME"] != pad_nets[pin]:
            raise ValueError(f"Netlist/probe disagreement at {pin}")

    # Importer requires z and thickness metadata even for 2D analysis. These
    # placeholders do not represent the stackup and are not used in calculations.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        board = gi.import_gerbers(
            {key: gi.GerberText(entries[name].decode("ascii"), name) for key, name in names.items()},
            [gi.CopperLayerSpec(key, 0, 1e-6) for key in names],
            arc_tolerance_m=1e-7,
        )

    def point(row):
        return Point(row["PIN_X"] * 0.0000254, row["PIN_Y"] * 0.0000254)

    def island(layer, pin):
        matches = [shape for shape in board.layer(layer).polygons if shape.covers(point(pin_rows[pin]))]
        if len(matches) != 1:
            raise ValueError(f"{pin} has {len(matches)} containing {layer} islands")
        shape = matches[0]
        net_names = {
            row["NET_NAME"] for row in rows
            if (row["PIN_TYPE"] == "DIP" or (layer == "top" and row["LAYER"] == "T")
                or (layer == "bottom" and row["LAYER"] == "B"))
            and shape.covers(point(row))
        }
        if net_names != {pin_rows[pin]["NET_NAME"]}:
            raise ValueError(f"Conflicting probe nets in {layer} island of {pin}: {sorted(net_names)}")
        return shape

    def mm_points(a, b):
        return [[p.x * 1000, p.y * 1000] for p in nearest_points(a, b)]

    def drill_shapes(text):
        """Parse only this candidate's explicit decimal-mm hits and G85 slots."""
        lines = text.splitlines()
        if ";TYPE=PLATED" not in lines or "METRIC,LZ,0000.00000" not in lines or "G90" not in lines:
            raise ValueError("Unexpected drill units, coordinates or plating")
        tools, selected, shapes = {}, None, []
        number = r"-?\d+\.\d+"
        xy = rf"X({number})Y({number})"
        for line in lines:
            if not line or line.startswith(";") or line in ("M48", "METRIC,LZ,0000.00000", "%", "G05", "G90", "M30"):
                continue
            definition = re.fullmatch(r"T(\d+)C(\d+\.\d+)", line)
            select = re.fullmatch(r"T(\d+)", line)
            hit = re.fullmatch(xy, line)
            slot = re.fullmatch(xy + "G85" + xy, line)
            if definition:
                tools[definition.group(1)] = float(definition.group(2))
            elif select:
                selected = select.group(1)
                if selected not in tools:
                    raise ValueError(f"Unknown drill tool {selected}")
            elif (hit or slot) and selected:
                values = [float(v) / 1000 for v in (hit or slot).groups()]
                centerline = Point(*values) if hit else LineString([(values[0], values[1]), (values[2], values[3])])
                shapes.append(centerline.buffer(tools[selected] / 2000, quad_segs=128))
            else:
                raise ValueError(f"Unsupported drill command: {line}")
        return shapes

    holes = shapely.union_all([
        shape for name in ("Drill_PTH_Through.DRL", "Drill_PTH_Through_Via.DRL")
        for shape in drill_shapes(entries[name].decode("ascii"))
    ])
    sections = []
    for i in range(1, 5):
        for side, relay_pins in (("IN", (5, 6)), ("OUT", (3, 4))):
            connector_pins = [f"FT_{side}{i}_{p}" for p in (1, 2)]
            contact_pins = [f"K{i}_{p}" for p in relay_pins]
            all_pins = connector_pins + contact_pins
            nets = {pad_nets[p] for p in all_pins}
            if len(nets) != 1:
                raise ValueError(f"Connector/contact pin nets differ: {all_pins}")
            a, b = point(pin_rows[connector_pins[1]]), point(pin_rows[contact_pins[1 if side == "IN" else 0]])
            x = (a.x + b.x) / 2
            midpoint = Point(x, (a.y + b.y) / 2)
            for layer in ("top", "bottom"):
                shape = island(layer, connector_pins[1])
                if not all(shape.covers(point(pin_rows[pin])) for pin in all_pins):
                    raise ValueError(f"Pins do not share {layer} island: {all_pins}")
                section_line = LineString([(x, shape.bounds[1] - .001), (x, shape.bounds[3] + .001)])
                section = section_line.intersection(shape.difference(holes))
                parts = list(section.geoms) if hasattr(section, "geoms") else [section]
                parts = [part for part in parts if part.geom_type == "LineString" and part.length > 0]
                selected = [part for part in parts if part.distance(midpoint) < 1e-10]
                if len(selected) != 1:
                    raise ValueError(f"Midpoint not in one drill-subtracted section: {layer} {all_pins}")
                segment = selected[0]
                sections.append({
                    "channel": i,
                    "side": side,
                    "layer": layer,
                    "candidate_net": next(iter(nets)),
                    "connector_pins": connector_pins,
                    "relay_pins": contact_pins,
                    "reference_centers_mm": [[a.x * 1000, a.y * 1000], [b.x * 1000, b.y * 1000]],
                    "section_x_mm": x * 1000,
                    "segment_y_min_mm": segment.bounds[1] * 1000,
                    "segment_y_max_mm": segment.bounds[3] * 1000,
                    "width_mm": segment.length * 1000,
                    "other_section_segments": len(parts) - 1,
                })

    gap = {}
    for layer in ("top", "bottom"):
        for a, b in (("CY1_1", "CY1_2"), ("U1_5", "U1_4"), ("U1_5", "U1_2")):
            one, two = island(layer, a), island(layer, b)
            gap[f"{layer}:{a}:{b}"] = {
                "pin_nets": [pin_rows[a]["NET_NAME"], pin_rows[b]["NET_NAME"]],
                "distance_mm": one.distance(two) * 1000,
                "nearest_points_mm": mm_points(one, two),
            }

    boundary_pins = [*(f"U1_{i}" for i in range(1, 7)), "CY1_1", "CY1_2"]
    u1_cy1_island_pairs = []
    for layer in ("top", "bottom"):
        for index, a in enumerate(boundary_pins):
            for b in boundary_pins[index + 1:]:
                if pad_nets[a] == pad_nets[b]:
                    continue
                one, two = island(layer, a), island(layer, b)
                u1_cy1_island_pairs.append({
                    "layer": layer, "pins": [a, b], "candidate_nets": [pad_nets[a], pad_nets[b]],
                    "distance_mm": one.distance(two) * 1000,
                    "nearest_points_mm": mm_points(one, two),
                })

    top_route = island("top", "L1_3")
    if not top_route.covers(point(pin_rows["U1_2"])):
        raise ValueError("Top L1_3 and U1_2 do not share an island")
    bottom_ground = island("bottom", "U1_5")
    overlap = top_route.intersection(bottom_ground).area

    # J2 center is taken from the probe file and independently checked against
    # the candidate PnP and the explicitly selected 3.2 mm plated drill hit.
    j2 = point(pin_rows["J2_1"])
    pnp = list(csv.DictReader(files[PREFIX + "PnP.csv"].decode("utf-8-sig").splitlines()))
    j2_row = next(row for row in pnp if row["Designator"] == "J2")
    for attr, value in (("Pad X", j2.x * 1000), ("Pad Y", j2.y * 1000)):
        if abs(float(j2_row[attr].removesuffix("mm")) - value) > 0.001:
            raise ValueError("J2 probe/PnP coordinate mismatch")
    drill = entries["Drill_PTH_Through.DRL"].decode("ascii")
    tools = {tool: float(dia) for tool, dia in re.findall(r"^T(\d+)C([\d.]+)\s*$", drill, re.M)}
    active = None
    hits = []
    for line in drill.splitlines():
        select = re.fullmatch(r"T(\d+)", line)
        hit = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if select:
            active = select.group(1)
        elif hit and active in tools:
            hits.append((float(hit.group(1)), float(hit.group(2)), tools[active]))
    matches = [h for h in hits if math.hypot(h[0] - j2.x * 1000, h[1] - j2.y * 1000) < 0.001]
    if len(matches) != 1 or matches[0][2] != 3.2:
        raise ValueError(f"J2 drill hit ambiguous: {matches}")
    drill_center = Point(matches[0][0] / 1000, matches[0][1] / 1000)
    hole = drill_center.buffer(matches[0][2] / 2000, quad_segs=512)
    j2_distances = {}
    for layer in ("top", "bottom"):
        copper = board.layer(layer).geometry.difference(hole)
        j2_distances[layer + "_drill_edge_to_copper"] = {
            "distance_mm": hole.distance(copper) * 1000,
            "nearest_points_mm": mm_points(hole, copper),
        }
    outline = board.layer("outline_graphics").geometry
    j2_distances["drill_edge_to_any_gko_graphic"] = {
        "distance_mm": hole.distance(outline) * 1000,
        "nearest_points_mm": mm_points(hole, outline),
    }

    report = {
        "warning": STAMP,
        "scope": "Static 2D candidate-file geometry only; no circuit or field simulation; no verified board revision.",
        "source": "MAIN_OMRON MCP_CANDIDATE_20261121_1753; archive-to-native revision link not established; candidate BOM export unavailable.",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "hashes_sha256": {
            **{name: digest(content) for name, content in files.items()},
            **{"zip:" + name: digest(content) for name, content in entries.items()},
            "script": digest(Path(__file__).read_bytes()),
            "emc_sim/gerber_import.py": digest(Path(gi.__file__).read_bytes()),
        },
        "software": {"python": sys.version, "gerbonara": gerbonara.__version__, "shapely": shapely.__version__},
        "method": [
            "Gerber positive/negative copper images and GKO rendered in memory by repository Gerber importer, 0.0001 mm maximum arc chord error.",
            "The importer requires dummy z=0 and thickness=0.001 mm; neither is physical nor used. No copper thickness or stackup is inferred.",
            "Probe pin centers identify continuous 2D copper islands; candidate PADS cross-checks six relevant net labels. SMD projections on the opposite layer are excluded from island-net consistency checks.",
            "Gaps are shortest Shapely Euclidean distances between complete undrilled 2D copper islands, not 3D clearance or creepage. No plating, assembly or manufacturing tolerances included.",
            "J2 drill circle uses the PTH file's 3.2 mm nominal diameter; copper inside it is excluded. GKO graphic distance is to the rendered stroke, not an identified board edge.",
            "Area projection is intersection of the entire top L1_3-seeded copper island and bottom U1_5/GND-seeded copper island, without drill subtraction or copper thickness.",
            "Each relay-path section is the vertical line at the mean X of FT pin 2 and its nearest corresponding relay contact on the same candidate net. Report the single continuous drill-subtracted copper segment containing the midpoint of those centers.",
            "Decimal-mm absolute G85 slot centerlines and hits from both explicitly plated through drill files are buffered by nominal tool radius and subtracted from the sections. Only the exact syntax in these candidate drill files is supported; other commands fail closed. No plating or barrel is modeled.",
            "U1/CY1 pair table includes all different-net pin pairs; pins identify whole planar copper islands, not necessarily local pad-to-pad gaps. Same-net pairs are omitted and no primary/secondary classification is inferred.",
        ],
        "import_warnings": [str(w.message) for w in caught],
        "candidate_copper_island_pair_distances": gap,
        "u1_cy1_candidate_pin_net_mapping": {pin: pad_nets[pin] for pin in boundary_pins},
        "u1_cy1_different_net_island_pair_distances": u1_cy1_island_pairs,
        "ft_relay_midpoint_cross_sections": sections,
        "j2": {"drill_center_mm": [matches[0][0], matches[0][1]], "nominal_drill_diameter_mm": matches[0][2], **j2_distances},
        "l1_3_top_vs_bottom_gnd_seeded_island": {
            "top_island_area_mm2": top_route.area * 1e6,
            "overlap_area_mm2": overlap * 1e6,
            "overlap_fraction": overlap / top_route.area,
        },
        "blockers_and_limits": [
            "FT_IN/FT_OUT midpoint sections are local widths, not global path bottlenecks or complete current paths; multiple routes, pad necks, plated slots, top/bottom current sharing, contacts and wiring remain unassessed.",
            "Heating cannot be determined from static geometry: actual currents, finished copper and plating, contacts, solder, wiring, enclosure, thermal conditions and measured validation are not established. Stated 1 oz is not fabricator-confirmed here.",
            "The candidate probe and PADS net labels are not a verified source revision and do not establish primary/secondary classification or identify every conductor. Reported seeded-island gaps do not establish the minimum isolation-boundary gap.",
            "GKO contains multiple graphics; nearest graphic is not established as board edge or slot. Screw/head, plated wall, metalwork and required insulation are unknown.",
            "A zero intersection concerns only one top island and one seeded bottom island. It is not proof of no GND anywhere beneath the route or of high-frequency return behavior.",
            "Importer normalized a self-touching bottom region; visual/fabricator validation and tolerance sensitivity are necessary.",
            "Physical safety and compliance require qualified review and appropriate laboratory work.",
        ],
    }
    output_parent = ROOT / "EMC" / "smart_power_strip" / "runs" / "exploratory" / "geometry"
    output_parent.mkdir(parents=True, exist_ok=True)
    run = output_parent / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    run.mkdir(exist_ok=False)
    output = run / "geometry_measurements.json"
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(STAMP)
    print("Candidate-file geometry only; full methods, numbers and limitations:", output)


if __name__ == "__main__":
    main()
