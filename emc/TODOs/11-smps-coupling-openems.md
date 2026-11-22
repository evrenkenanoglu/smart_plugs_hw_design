# TODO 11 — Model switching-structure coupling, if supportable

**Status:** Conditional — candidate assumptions must be explicit  
**Depends on:** TODOs 08 and 09; requires actual switching-structure data

## Work

- [ ] Investigate from the candidate evidence and component documentation whether
  the switching structure is on the PCB and accessible to a defensible model.
- [ ] Model only a specific coupling path, such as a documented high-dv/dt
  node to a nearby conductor, with known geometry and a stated excitation.
- [ ] Use measured, vendor-provided, or otherwise justified excitation data.
  If the supply is sealed and internal switching data are unavailable, do not
  invent its switch node or waveform; defer this model.
- [ ] Separate electrical source uncertainty from geometry and run bounded
  sensitivities only when ranges have a stated basis.
- [ ] Keep any modeled fields/coupling as simulated relative quantities, not
  emissions measurements.

## Done when

The selected physical coupling mechanism and source are traceable to evidence,
and results are stable under mesh/time refinement. If source evidence is
missing, record the blocker instead of producing a success-shaped model.
