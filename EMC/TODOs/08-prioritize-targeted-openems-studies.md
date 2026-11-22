# TODO 08 — Prioritize targeted openEMS studies

**Status:** Candidate studies permitted with explicit assumptions and numerical checks  
**Depends on:** TODOs 02, 04, and 06

## Work

- [ ] From the actual board review, select at most two or three initial local
  structures whose geometry and boundary conditions can be supported by
  evidence.
- [ ] For each candidate, state its own bounded question, output quantity,
  frequency range, source/ports, terminations, included geometry, and
  exclusions.
- [ ] Consider filter input-to-output coupling, a documented switching-node
  coupling path, or radio/antenna interaction only when those structures
  actually exist and their inputs are available.
- [ ] Use circuit/quasi-static methods for questions outside full-wave FDTD's
  practical frequency/geometry range rather than forcing one simulation from
  150 kHz to multi-GHz.
- [ ] Defer candidates whose sources, geometry, or physical return paths cannot
  be justified. Record why they were not modeled.

## Done when

The selected studies are explicitly bounded and ordered by evidence and risk;
no full-board, all-frequency simulation is implied.
