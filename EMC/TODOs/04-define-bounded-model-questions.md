# TODO 04 — Define bounded model questions

**Status:** Candidate questions may proceed with documented assumptions  
**Depends on:** TODOs 02 and 03

## Work

- [ ] Select a small number of high-priority mechanisms from the board review;
  define a separate bounded question for each model rather than one giant
  full-board simulation.
- [ ] State the output quantity (for example, a port transfer function or a
  relative change between two controlled layout variants).
- [ ] Set a frequency/time range justified by the selected mechanism, available
  models, and solver limitations.
- [ ] Define source waveform and impedance, ports, terminations, materials,
  boundaries, and which nearby geometry must be included.
- [ ] List assumptions, excluded structures, uncertainty ranges, and the
  conditions that would stop modeling for missing evidence.
- [ ] Record the question and model scope before preparing project geometry.

## Candidate directions

Consider conducted filter/source sensitivity, local filter bypass, switching
structure coupling, or radio/antenna interaction only if those structures and
needed data exist in the selected candidate, or are explicitly assumed. Decide which solver matches each
question; do not assume one method or frequency sweep covers every mechanism.
Do not presume `$L1_3` is an EMI-filter path or that an ideal source represents
the product's operating noise.

## Done when

Each selected question has a defined output, frequency range, source/port
assumptions, controlled comparison, and stop condition. Unselected candidates
are deferred with a reason.
