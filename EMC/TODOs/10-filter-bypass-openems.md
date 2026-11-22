# TODO 10 — Model local filter-bypass coupling

**Status:** Candidate study permitted with explicitly bounded assumptions  
**Depends on:** TODOs 08 and 09

## Work

- [ ] Document candidate evidence for an input-filter structure and select a
  bounded bypass-coupling question.
- [ ] Model the real nearby input/output copper, planes, gaps, vias, and
  component pad geometry from the selected exports; do not insert an assumed plane.
- [ ] Define ports at physically meaningful boundaries and document their
  impedances, terminations, and reference conductors.
- [ ] Compare controlled geometry variants or extract a network quantity that
  directly answers the bounded bypass question.
- [ ] Label assumed component models in co-simulation; without validated
  component models, do not call the local response actual filter attenuation.
- [ ] Check mesh/time convergence and sensitivity to justified material and
  boundary uncertainty.

## Done when

The local model is revision-traceable and stable for its stated output, with
explicit limitations. It does not predict product emissions or certification
margin.
