# TODO 02 — Audit whole-board EMC paths and safety evidence

**Status:** Partial — preliminary candidate-data review; depends on TODOs 00 and 01  
**Depends on:** TODOs 00 and 01

The candidate PCB BOMs, netlists, pick-and-place files, and Gerbers are
available, but the revision is not locked and matching schematic PDFs are
missing. Preliminary open findings are recorded in
`../docs/EMC_SAFETY_AUDIT_CHECKLIST.md`; this is not a completed whole-board
review.

## Work

- [ ] Review the locked schematic and layout together with the matched BOM,
  manufacturer data, and relevant fabrication/mechanical evidence.
- [ ] Review EasyEDA Pro design-rule outputs and visually inspect the complete
  board/layer set; use a Gerber viewer as an independent geometry check when
  available. DRC success is not proof of EMC or product safety.
- [ ] Trace the actual conducted-noise paths through the AC/DC supply input,
  the verified input network, relay circuits, loads, protective earth, and
  accessible cables. Do not assume a generic fuse/MOV/X-cap/choke/Y-cap order.
- [ ] Review switching hot loops and high-dv/dt structures only where the
  actual circuit and available module data expose them. Treat a sealed module
  as a black box if its internal topology/source data are unavailable.
- [ ] Check whether copper and returns allow coupling around the verified
  filter; inspect plane splits, slots, stitching, and signal-return continuity
  using the actual layer stack.
- [ ] If a radio is present, identify the exact module/antenna and check its
  vendor keep-out and nearby enclosure/cable conditions.
- [ ] Cross-check safety-critical claims against the actual design and
  manufacturer data, including fuse coordination, protective-earth path,
  isolation, component ratings, and thermal/current paths. Escalate
  standards-dependent questions for qualified review.
- [ ] Record each finding with source file/section, evidence, priority as a
  review aid, why it matters, and the next non-energized analysis or qualified
  review. Update `../risk-register.md` with unresolved concerns.

## Done when

The whole-board review is traceable to one design revision, with open
questions and model candidates documented. Do not claim a percentage of
failures caught or call a review finding a compliance verdict.

## Safety and scope

This is a documentation and layout review. Do not perform improvised energized
measurements. Any proposed changes to isolation, PE, fusing, surge protection,
current capacity, or thermal behavior require qualified review.
