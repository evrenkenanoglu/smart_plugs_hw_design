# TODO 03 — Verify the pilot circuit and return path

**Status:** Revision-matched verification open; candidate investigations permitted  
**Depends on:** TODOs 00 and 01

## Work

- [ ] In the locked schematic and PCB, identify the electrical role of
  component record `e1385` and net `$L1_3`.
- [ ] Verify the actual route segments, connected components, and topology;
  confirm whether the route is part of an input filter, switching path, or
  another circuit.
- [ ] Inspect all copper layers beneath and around the pilot route, including
  planes, pours, slots, vias, and isolation clearances.
- [ ] Record relevant line-to-neutral, protective-earth, and isolated-domain
  boundaries from the actual design; do not infer them from net names.
- [ ] If claims conflict with the schematic, layout, BOM, or datasheets, record
  the conflict and update `../risk-register.md`.

## Done when

The pilot region's function, connected network, and physical return path are
supported by revision-matched artifacts, or the unknowns are explicitly
documented. Candidate models may proceed with those unknowns stated.

## Safety and scope

Do not add an assumed ground plane to a mains-connected region. This is a
documentation/layout review task, not an instruction to energize or probe the
board.
