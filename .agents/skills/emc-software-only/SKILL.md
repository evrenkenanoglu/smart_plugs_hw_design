---
name: emc-software-only
description: Run a software-only EMC risk-reduction workflow for the smart-plug design; use when planning audits, circuit simulations, or targeted openEMS models without lab equipment.
---

# Software-only EMC risk-reduction workflow

This workflow is intended for an independent designer without in-house EMC
equipment. It can expose design questions, compare documented model variants,
and prepare for a qualified lab. It cannot verify real-product emissions,
immunity, electrical safety, or certification. Do not describe it as a complete
software substitute for physical testing.

Use `emc/TODOs/README.md` to track the staged work. Keep this workflow separate
from physical prototype testing and formal compliance evaluation.

## Workflow

1. **Read project gates.** Read `AGENTS.md`, `emc/README.md`,
   `emc/input-checklist.md`, `emc/risk-register.md`, and
   `emc/TODOs/README.md`.
   Treat project notes as claims to verify.
2. **Identify revision or candidate baseline.** Record the EasyEDA Pro
   project/board identity and hashes of staged exports. For **final release sign-off**,
   require a single matched locked revision. For **exploratory candidate simulations**,
   proceed on user-selected candidate exports (`allow_candidate=True`) even when
   manifests are unlocked or dates differ, while recording all gaps and assumptions.
3. **Audit the whole design from evidence.** Review actual conducted and
   radiated paths, filter topology, switching structures, relay/load circuits,
   return paths, board geometry, radio if present, enclosure, PE, and cables.
   Cross-check safety-critical claims with component data and qualified
   product-standard review. Record evidence, priority, uncertainty, and next
   action in `emc/risk-register.md`; a review priority is not a compliance
   finding.
4. **Select bounded questions.** Choose mechanisms supported by the design or
   explicit candidate assumptions. Give each model its own quantity of interest,
   frequency range, geometry, source, ports, terminations, assumptions, and stop gate.
   Do not start with one whole-board, all-frequency simulation.
5. **Use circuit simulation for circuit questions.** Use ngspice/Qucs-S with
   verified or explicitly assumed candidate filter/component models and a
   documented CISPR LISN/AMN network. When the converter source is unknown,
   model explicit bounded synthetic source scenarios as sensitivity cases—not
   measured or predicted product emissions. A transient FFT is not automatically
   equivalent to a standards receiver's bandwidth or detector.
6. **Use openEMS for selected full-wave questions.** Reproduce the official
   tutorial/benchmark, verify geometry and ports, then model a local structure
   using real Gerber copper (never inventing an absent ground plane). Check mesh
   and simulation-time convergence of the reported quantity, passivity, plus
   justified boundary/material/source sensitivities. Solver termination alone is
   not mesh convergence.
7. **Review design options without silently editing CAD.** Alternative/DNP
   footprints may be documented as future variants only after their purpose,
   voltage domain, parasitics, isolation/creepage, thermal/current impact, and
   qualified review needs are clear. Do not generically add snubbers, gate
   resistors, X/Y capacitors, or choke bypasses. Do not modify native EasyEDA
   or released manufacturing files unless explicitly asked.
8. **Report limits and hand off.** Label every result as assumption,
   calculation, or simulation, and stamp exploratory candidate runs
   `CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`; do not
   call any simulation measurement, margin, pass/fail, or proof of safety/compliance.
   Preserve input hashes, tool versions, scripts, inputs, logs, and plots. List
   unresolved risks and future qualified-lab questions. Do not provide
   improvised energized-mains test instructions.

## Software-only deliverables

- Revision manifest and candidate/matched-input inventory.
- Whole-board review findings with traceable evidence and unresolved risks.
- Reproducible circuit and/or local full-wave models for bounded questions.
- Sensitivity results with assumptions and numerical convergence checks.
- A future qualified-lab handoff that does not imply the software work has
  established compliance.

## Error registry

- **Mismatched design artifacts:** The repository records Gerbers and STEP
  files from different dates without confirmed revision linkage
  (`emc/README.md`). Mitigation: log exact dates/hashes and separate
  exploratory candidate runs from locked release sign-off.
- **Treating the L1 coupon as the actual filter or board:** The pilot
  straightens the route and assumes the substrate/return plane while omitting
  the filter components and surrounding layout
  (`emc/openems/experiments/README.md`). Mitigation: keep it as a solver
  workflow demonstration; use real local Gerber geometry for board models.
- **Treating the solver energy stop as mesh convergence:** The pilot reached
  its time-domain termination, while the mesh-convergence flag remains false
  (`emc/openems/experiments/runs/l1_route_20261117_180814/run_metadata.json`).
  Mitigation: refine the mesh and show stability of the output quantity.
- **Treating `MSLPort.Z_ref` as a scalar:** A direct scalar conversion raised a
  `TypeError`; openEMS returns frequency-dependent values matching the sweep
  (`.agents/skills/openems-modeling/SKILL.md`). Mitigation: validate the array
  against the frequency vector and preserve its frequency dependence.
- **Treating the coupon excitation as a product noise source:** The pilot uses
  a Gaussian microstrip-port excitation and does not model the smart-plug
  converter or relay/load noise (`emc/openems/experiments/l1_route_pilot.py`).
  Mitigation: do not infer product emissions; use source data or explicitly
  bounded illustrative scenarios.
- **Treating the pilot's MSL port reference impedance as a measured line
  impedance:** the archived value is a solver-derived, frequency-dependent
  port-reference quantity and differs materially from the simple analytical
  estimate (`emc/TODOs/05-audit-pilot-and-calculate-baseline.md`). Mitigation:
  label the quantities precisely and rely on the calibrated benchmark rules.
- **Treating a 2D copper/drill import as complete 3D PCB geometry:** the
  importer subtracts explicitly configured Excellon hits and slots from named
  copper layers, but does not model via barrels or finite copper thickness
  (`emc/emc_sim/gerber_import.py`). Mitigation: retain those limitations in
  every model scope and do not treat the overlay as a complete EM model.
- **Guessing Excellon coordinate or layer-span semantics:** the importer
  requires explicit coordinate settings and inclusive copper-layer spans and
  rejects ambiguous drill data rather than inferring blind/buried via spans
  (`emc/emc_sim/gerber_import.py`). Mitigation: verify the export settings and
  span against the stackup config before importing.
- **Treating a successful openEMS energy stop as benchmark validation:** the
  earlier generic coarse/fine coupon reached its energy stop but failed its
  analytical agreement and refinement gates
  (`emc/TODOs/06-calibrate-openems-and-check-convergence.md`). Mitigation:
  apply the verified geometric mesh grading from the passing 45 mm benchmark.
- **Approximating unsupported Gerber features:** non-circular trace apertures
  and negative-image polarity are rejected by the importer rather than
  converted to guessed shapes (`emc/emc_sim/gerber_import.py`). Mitigation:
  use supported exports or extend and test the parser before modeling.
- **Rejecting EasyEDA's body `G90` as ambiguous:** the Nov 21 candidate drill
  files use absolute-mode `G90` after the header, which Gerbonara applies but
  warns about. The importer accepts only that specific warning and still
  rejects incremental mode and all other parser warnings
  (`emc/emc_sim/gerber_import.py`, `emc/tests/test_gerber_import.py`).