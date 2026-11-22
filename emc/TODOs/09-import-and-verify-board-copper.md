# TODO 09 — Import and verify a local PCB copper model

**Status:** Candidate import permitted; matched revision and confirmed physical stackup remain open  
**Depends on:** TODOs 01, 06, and 08

## Work

- [ ] Select a local crop large enough to include the conductors, return paths,
  nearby copper, vias, and discontinuities relevant to the bounded question.
- [ ] Convert the selected candidate fabrication geometry into a documented
  CSXCAD/openEMS representation using an appropriate importer.
- [ ] Configure each Excellon file's affected copper span explicitly and
  compare its hits and slots against the selected fabrication export.
- [ ] Use the selected candidate stackup, copper, and dielectric data; label
  assumptions and sweep justified uncertainty ranges.
- [ ] Define ports between physically meaningful conductors and use actual
  nearby return structures; do not invent a continuous reference plane.
- [ ] Inspect the generated geometry and mesh visually and compare them against
  the source Gerbers, drills, and schematic.
- [ ] Refine the mesh and test material/boundary sensitivity before reporting
  the selected output quantity.
- [ ] Save the import script, source hashes, geometry, run logs, and plots.

## Done when

The modeled crop is traceable to its identified candidate or locked revision,
visually agrees with the source Gerbers and Excellon files, and the target
quantity passes its stated convergence checks.

## Stop condition

Document missing revision linkage and physical return-path evidence. Do not
create an assumed bottom plane to make the solver setup easier.

The generic importer handles a limited set of copper Gerber objects and
unambiguous Excellon drill hits/tool-width slots. Drill files must explicitly
name their inclusive copper-layer spans. It does not model via barrels or
finite-thickness copper; its CSXCAD output is a zero-thickness sheet. Those
exclusions must be resolved or explicitly bounded before using it for an
openEMS board model.
