---
name: emc-precertification
description: Review this smart-plug hardware design for EMC pre-compliance risks and missing evidence before external certification. Use when auditing schematics, PCB exports, BOMs, enclosure, or simulation results.
---

# EMC pre-certification review

This is a risk-reduction review, not a compliance determination.

Use the staged task list in `emc/TODOs/README.md` to track the broader review. Keep
whole-board document review, conducted-noise circuit modeling, local
full-wave modeling, and future laboratory testing as separate evidence tracks.
There is no software-only workflow that can establish whole-product EMC or
safety compliance.

1. Read the root `AGENTS.md`, `emc/README.md`, `emc/input-checklist.md`, and `emc/risk-register.md`.
2. Identify the source project, board, export dates, and file hashes. Unmatched
   inputs do not block candidate exploratory simulations; explicitly record
   their limitations and do not claim a verified product revision. Require
   matched, locked inputs for final manufacturing release sign-off.
3. Determine the intended markets and product category from project evidence. Do not select or claim standards applicability by assumption; list it as unresolved for a qualified compliance specialist.
4. Review conducted and radiated noise paths separately using the selected
   candidate or verified design, clearly distinguishing unverified inputs.
   Consider the AC/DC module and its input network, relay switching and
   load type, radio/clock if present, return paths, board edges, enclosure, PE,
   and external cables. Do not assume a generic filter topology or switching
   waveform.
5. Cross-check every safety-critical claim against actual design data and component datasheets. Report contradictory values, missing data, and assumptions as open items; do not call a design compliant based on a note or simulation.
6. For each finding, give severity as a prioritization aid (not a certification verdict), evidence with file and section, why it matters, and the next non-energized analysis or qualified review needed.
7. Distinguish simulation results from measured results. Stamp every candidate
   report and plot `CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`.
   State model limitations and do not infer test-lab margin from an unvalidated model.
8. Do not provide improvised instructions for testing energized mains hardware.

For circuit simulations, document the assumed LISN/AMN and its applicability
uncertainty when the product/test configuration is not established. Treat synthetic source
waveforms as sensitivity scenarios, not product emissions predictions. A
transient FFT is not automatically equivalent to a standards receiver's
bandwidth and detector. Record software-only results as calculations or
simulations, never measurements.

Do not edit CAD or manufacturing outputs unless explicitly asked. Update the
input checklist and risk register as findings emerge.

## Error registry

- **Mismatched export dates/revisions:** can make review or simulation describe the wrong board. Record unmatched candidate inputs and do not treat them as a verified release revision.
- **Treating project notes as verified design facts:** can hide contradictory component values or unsupported safety claims. Cross-check against the schematic, layout, BOM, and manufacturer data.
- **Calling a simulation a compliance test:** can create false confidence. Label results as simulated and list unmodeled sources and uncertainty.
- **Improvised energized mains testing:** creates serious shock/fire risk. Keep this workflow to document review and simulation; use qualified test facilities for physical mains tests.
