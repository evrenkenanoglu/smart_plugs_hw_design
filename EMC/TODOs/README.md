# EMC investigation TODOs

This is a staged, open-source-first risk-reduction plan. It broadens the
earlier single-coupon investigation into design review, circuit analysis,
targeted full-wave models, and eventual qualified-lab planning. It is not a
claim that the design is safe or compliant. The current openEMS coupon remains
an exploratory workflow demonstration; do not make PCB changes based on it.
The software-only stages do not constitute complete EMC verification; the
qualified-lab handoff is a future, non-software step.

## Tasks and dependencies

The dependencies below describe evidence for final, revision-matched
conclusions, not a gate on exploratory simulations. User-selected candidates
may be modeled with documented gaps and assumptions, strict numerical and
passivity checks, no invented ground plane, and the stamp
`CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`.
Only final manufacturing release sign-off requires a locked revision.

| File | Task | Depends on |
|---|---|---|
| [00-lock-design-revision.md](00-lock-design-revision.md) | Confirm the authoritative EasyEDA revision | None |
| [01-export-matched-input-package.md](01-export-matched-input-package.md) | Collect revision-matched evidence | 00 |
| [02-audit-whole-board-design.md](02-audit-whole-board-design.md) | Review whole-board EMC paths and safety evidence | 00, 01 |
| [03-verify-pilot-circuit-and-return-path.md](03-verify-pilot-circuit-and-return-path.md) | Verify `$L1_3` / `e1385` and its actual return path | 00, 01 |
| [04-define-bounded-model-questions.md](04-define-bounded-model-questions.md) | Prioritize and scope distinct model questions | 02, 03 |
| [05-audit-pilot-and-calculate-baseline.md](05-audit-pilot-and-calculate-baseline.md) | Check what the existing coupon can and cannot tell us | Existing pilot; reassess after 03 |
| [06-calibrate-openems-and-check-convergence.md](06-calibrate-openems-and-check-convergence.md) | Validate a benchmark and numerical stability | Official tutorial already verified; before project-specific FDTD |
| [07-conducted-emissions-ngspice-model.md](07-conducted-emissions-ngspice-model.md) | Study filter/source sensitivity in a circuit model | 01, 02, 04; valid or explicitly assumed sources |
| [08-prioritize-targeted-openems-studies.md](08-prioritize-targeted-openems-studies.md) | Select only evidence-supported local full-wave studies | 02, 04, 06 |
| [09-import-and-verify-board-copper.md](09-import-and-verify-board-copper.md) | Import and visually verify matched-revision copper | 01, 06, 08 |
| [10-filter-bypass-openems.md](10-filter-bypass-openems.md) | Model local filter-bypass coupling, if supported | 08, 09 |
| [11-smps-coupling-openems.md](11-smps-coupling-openems.md) | Model an evidenced switching-node coupling path, if supported | 08, 09; source/structure data |
| [12-radio-antenna-openems.md](12-radio-antenna-openems.md) | Model radio/antenna interaction, if present and supported | 08, 09; exact radio/antenna data |
| [13-cable-coupling-openems.md](13-cable-coupling-openems.md) | Optional relative cable-coupling study | 08, 09; credible cable/source setup |
| [14-review-tuning-options.md](14-review-tuning-options.md) | Review possible tuning options without changing the PCB | 02, 04 |
| [15-co-simulate-filter-components.md](15-co-simulate-filter-components.md) | Combine valid component and extracted-layout networks | 07 and relevant completed local models |
| [16-prepare-qualified-lab-handoff.md](16-prepare-qualified-lab-handoff.md) | Prepare future qualified-lab scope and evidence handoff | Can be drafted anytime |

## Four complementary tracks

1. **Design review:** Inspect the matched schematic, PCB, BOM, datasheets, and
   mechanical evidence across the whole board. Record evidence-backed findings
   and unresolved risks; do not infer a generic filter topology or claim a
   fixed percentage of defects will be caught.
2. **Circuit modeling:** Use ngspice for bounded conducted-noise/filter
   sensitivity questions. A standard-appropriate LISN network and real source
   behavior require evidence. Assumed sources are sensitivity cases, not
   product emissions predictions. A transient FFT is not automatically
   equivalent to a standards receiver's bandwidth and detector. This may
   proceed with an explicitly identified candidate and bounded question.
3. **Targeted full-wave modeling:** Use openEMS only for selected local
   structures and frequency ranges supported by the question and data. A
   solver stop is not mesh convergence. Do not model arbitrary cable excitation
   or claim absolute radiated levels without a validated source and setup.
4. **Physical testing:** No in-house VNA/LCR or passive measurement task is
   planned. Software-only work can prepare evidence and prioritize risks, but
   cannot establish product performance or compliance. Future energized
   EMC/safety testing belongs only in a properly equipped, qualified lab.

## Current execution status

- **TODO 00:** Blocked; MAIN_OMRON/UI candidate exports are present, but their
  link to the staged `.eprj2` revision is unconfirmed. The 2026-11-23
  EasyEDA health check returned `bridge_connected: false`; no project-scoped
  calls or new exports were attempted.
- **TODO 01:** Partial; candidate Gerbers/drills, BOMs, PCB netlists, and
  pick-and-place files are organized and hashed. Schematic PDFs and
  fabricator-confirmed stackup are missing.
- **TODO 02:** Partial; preliminary candidate findings are recorded in the EMC
  audit checklist. Full review remains blocked on TODOs 00 and 01.
- **TODOs 03–04:** Revision-matched conclusions remain open; bounded candidate
  investigations may proceed with their gaps documented.
- **TODO 05:** Partial. The historical pilot's scalar material inputs serialized
  as anisotropic `epsilon=(4.2,1,1)` and `kappa=(4.906787e-3,0,0)`; its feed and
  measurement planes are only 0.5 mm apart, and its CSV cannot reconstruct a
  power balance. These verified setup issues make the roughly 50.3% difference
  from the isotropic Hammerstad-Jensen estimate untrustworthy, but their
  individual effects have not been isolated. See TODO 05; the pilot remains
  exploratory and is not PCB evidence.
- **TODO 06:** Complete for the generic coupon only. A reproducible abrupt
  near-field mesh transition (0.2 mm substrate cells to a 2.857 mm air cell;
  0.125 mm trace-region cells to 1 mm lateral cells) was corrected with
  geometric grading. The final coarse/medium/fine maximum analytical errors
  were 8.21%/5.63%/4.30%, the maximum all-pair mesh change was 4.17%, and the
  maximum independent boundary change was 1.97%; energy-stop and power checks
  passed. See the run report and metadata linked in TODO 06. This generic
  coupon result does not validate or describe the product PCB.
- **TODOs 07–15:** Candidate simulations may proceed with explicit assumptions;
  claims still require appropriate source, geometry and numerical evidence.
  The conducted candidate study at
  `../smart_power_strip/runs/conducted_spice/20261121T191803180777Z/`
  contains assumed-source sensitivity and calculated full-network modes.
  The local field diagnostic at
  `../smart_power_strip/runs/pcb_em/candidate_20261121T191908564280Z/`
  did not pass its energy and geometry checks and produced no valid network.
- **TODO 16:** A generic handoff template exists; completing it requires the
  product configuration and qualified review. It does not authorize energized
  testing outside a qualified facility.

Record assumptions, calculations, simulated values, and measurements
separately. Keep the revision and hashes with every project-specific result,
mark missing inputs unknown, and record unresolved concerns in
`../risk-register.md`. Any proposed changes affecting mains isolation, PE,
fusing, surge protection, current capacity, or thermal performance need review
against the applicable product standards by a qualified person.
