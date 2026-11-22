# TODO 01 — Export the matched model input package

**Status:** Partial — candidate exports received; depends on TODO 00  
**Depends on:** TODO 00

The 2026-11-19 candidate Gerber/drill, BOM, PCB-netlist, and pick-and-place
files have been organized by board and hashed. The provided PDFs are PCB
placement drawings, not schematic PDFs; MAIN_OMRON J1/J2/J3 lack manufacturer
part numbers, and no fabricator-confirmed stackup is present. Do not treat
this candidate set as a matched, locked revision.

## Work

- [ ] From the locked EasyEDA Pro revision, export every copper layer, board
  outline, relevant solder-mask/fabrication layers, and PTH/NPTH drill files.
- [ ] Export the matching schematic, netlist, BOM with manufacturer part
  numbers, and assembly/pick-and-place data.
- [ ] Obtain the fabricator-confirmed layer order, finished board thickness,
  copper thickness per layer, and available dielectric properties/tolerances.
- [ ] Collect exact manufacturer part numbers and datasheets; obtain valid
  SPICE/Touchstone models only for components selected for analysis.
- [ ] Collect enclosure and cable geometry only if needed by the bounded
  question.
- [ ] Hash and inventory every file; record units, export dates, and revision
  linkage. Include enclosure/cable files when needed, explicitly identifying
  any unmatched candidate geometry.
- [ ] Mark unavailable inputs as unknown in `EMC/input-checklist.md`; any
  exploratory assumptions must be explicit, not represented as verified.

## Done when

The inputs needed for the chosen question are demonstrably tied to one design
revision, and all missing inputs are listed.

## Safety and scope

Differently dated exports may be combined for an explicitly labeled candidate
study, but filenames do not prove revision linkage. A STEP model is not a
substitute for copper geometry. Assumed stackups, component models, and
synthetic sources are not verified product data.
