---
name: openems-modeling
description: Plan or build a reproducible openEMS model for a PCB or EMC question. Use when board geometry (locked or user-selected candidate), stackup, materials, source assumptions, and an explicit simulation objective are available.
---

# openEMS modeling workflow

openEMS is a 3D FDTD field solver, not an automatic EMC certification tool. A detailed-looking result is not meaningful unless the geometry, excitation, material data, boundary conditions, and numerical convergence are justified.

1. Read `AGENTS.md`, `EMC/README.md`, `EMC/input-checklist.md`, and the openEMS notes in `EMC/openems/README.md`.
2. Record which PCB export set was used. Strict single-revision locking (`locked: true`) is reserved for release sign-off; **exploratory candidate runs** may use user-selected candidate exports (`allow_candidate=True`) when any missing linkage or assumed stackup parameters are explicitly logged under **Assumptions**.
3. State one bounded question for each model, such as relative field change or passive coupling from a filter-layout region. Do not begin with the entire assembled product.
4. Record geometry units, copper and dielectric properties, loss assumptions, excitation waveform and source impedance, ports, enclosure/cable geometry, boundary conditions, mesh rules, and frequency/time range. Never invent a ground plane under a trace or filter if the real Gerber layers do not contain one.
5. Reproduce an official openEMS tutorial or benchmark first. On this Windows setup, use the repo activation script and verified benchmark grading rules; check that the solver and Python bindings work before creating project geometry.
6. Refine the mesh and simulation duration until the quantity of interest is stable. Report the mesh, timestep, termination criteria, passivity, and convergence checks.
7. Run controlled comparisons and sensitivity cases; identify which unknown source or material parameters dominate the result.
8. Save the input script, tool versions, source-file hashes, assumptions, and output plots for every run. Do not edit the source PCB as part of model setup.
9. Label findings as model results (and stamp exploratory candidate runs `CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`). Do not describe them as emissions-test results, certification margin, or proof of compliance.

## Error registry

- **Using Gerbers and STEP files from unconfirmed revisions:** can model the wrong assembly if unlabeled. Record exact candidate export folder/hashes and keep exploratory disclaimers explicit.
- **Importing Python bindings from inside the openEMS/CSXCAD source tree:** can import source stubs instead of compiled modules. Run the smoke test from a neutral directory with the intended environment activated.
- **Reporting results before mesh/time convergence:** can make numerical artifacts look like design behavior. Refine the mesh and simulation duration and show stability of the reported quantity.
- **Inventing a source waveform or internal model for a sealed AC/DC module:** produces unsupported emissions predictions. Use validated data or explicitly mark synthetic source sweeps as bounded assumptions.
- **Treat near-field solver output as certification margin:** overstates what the model validates. Report only the modeled fields/quantities and their assumptions.
- **Passing an N-by-2 array to `CSPropMetal.AddPolygon`:** CSXCAD 0.7.0 expects `[x_coordinates, y_coordinates]`; the wrong orientation raises `AssertionError: points must be a list of length 2`. Follow the installed binding's docstring.
- **Creating an `MSLPort` before defining propagation-axis mesh lines, or with a zero-length propagation extent:** the port cannot create valid probes/excitation. Add the mesh first and give the port finite propagation and excitation spans.
- **Using a lumped port without discretizing its edges:** can leave the FDTD setup with no registered excitation. Inspect the solver's excitation count during setup; an unsourced or unstable run is not a result.
- **Using an unstable exploratory geometry after solver energy diverges:** an `inf`/`nan` field-energy trace invalidates post-processing. Discard its S-parameters and correct the source, port, and mesh setup before rerunning.
- **Giving an MSL port a width different from the modeled strip, or stopping at the timestep cap:** can create port discontinuities and non-decaying fields. Match the port to the strip cross-section, then confirm the energy criterion is reached before interpreting S-parameters.
- **Treating extracted `MSLPort.Z_ref` as a scalar:** openEMS returns frequency-dependent impedance values matching the requested sweep. Validate the array shape against the frequency vector and store the per-frequency real and imaginary values with the S-parameter data rather than coercing it to a scalar.
- **Treating an energy stop as benchmark validation:** termination only shows that the solver met its energy criterion; it does not establish analytical agreement or mesh/boundary stability. Require each declared gate. The generic coupon later passed these gates after its mesh transitions were corrected, but that result does not validate a product PCB.
- **Treating mesh stability as boundary stability:** on the earlier generic coupon, expanding the transverse domain/PML placement changed fine-mesh `MSLPort.Z_ref` by about 14% at representative frequencies even though each three-mesh run passed its 5% refinement gate. After correcting the near-field grid, independent x/y/z extent cases changed the medium-mesh result by at most 1.97%. Record actual PML interfaces and run separate boundary-sensitivity cases; within-run refinement is not a substitute.
- **Leaving abrupt mesh transitions beside a microstrip:** the generic coupon's fixed grid jumped from 0.2 mm substrate cells to a 2.857 mm first air cell, and from 0.125 mm trace-region cells to 1 mm lateral cells. The resulting stable but biased `MSLPort.Z_ref` failed analytical agreement. Explicitly grade upper-air and lateral cells (maximum 1.4 growth, 3 mm upper-air and 1 mm lateral cell caps), then inspect the serialized mesh and rerun analytical, refinement, and boundary gates. This correction was reproduced on the generic coupon; it does not establish product-model accuracy.
- **Passing scalar material values when isotropy is intended:** in the preserved CSXCAD 0.7.0 pilot, scalar `epsilon=4.2` and scalar conductivity serialized as `epsilon=(4.2,1,1)` and `kappa=(kappa,0,0)`. Use explicit three-component vectors for isotropic materials and inspect the generated XML before trusting material assumptions.
- **Treating a capped candidate run or midpoint screen as a valid network:** the
  MAIN_OMRON diagnostic at `EMC/smart_power_strip/runs/pcb_em/candidate_20261121T191908564280Z/`
  reached its 40,000-step cap without the energy stop and logged 6,365
  unused-polygon warnings. Its midpoint screen did not establish sub-cell
  copper fidelity or connectivity. Resolve those warnings and demonstrate
  energy, mesh, boundary, and passivity gates before releasing S-parameters.
- **Interpreting fewer unused-polygon warnings as a validated mesh:** exact
  copper cutout partitioning and merging reduced the MAIN_OMRON warning count
  from 6,365 to four in `candidate_20261121T193813588877Z`, but the remaining
  warnings and copper connectivity are unresolved and the excitation was
  truncated. The later 40,000-step diagnostic `candidate_20261121T194454406820Z`
  did not truncate excitation but also failed the energy gate. Keep the
  geometry and convergence gates active.
- **Resolving unused primitives solely by extreme global grid refinement:**
  targeting MAIN_OMRON's small copper fragments removed their warnings in a
  short session-only diagnostic but reduced the timestep from 64.25 fs to
  5.892 fs and increased the mesh from 720,720 to 1,327,200 cells. The source
  was truncated and no network was validated. See `EMC/input-checklist.md`;
  evaluate accuracy and computational cost rather than treating warning
  removal as solver convergence.
- **Assuming a mesh adjustment that passes one grid works at every refinement:**
  sparse candidate anchors removed the unused warnings and passed the midpoint
  screens on the coarse and medium diagnostic meshes, but the 0.5 mm fine
  mesh missed one expected top-copper PEC midpoint. All diagnostic excitations
  were truncated. Check geometry fidelity independently on every mesh.
- **Using two downstream ports to infer choke bypass:** the candidate L1-to-U1
  differential ports both lie after L1. Even a converged downstream network
  would not establish pre-/post-choke coupling; define and validate suitable
  ports and terminations for that separate question.
- **Treating a wall-clock sampled energy peak as the true solver peak:** on
  `candidate_20261122T113735712887Z` the first sample missed the transient
  maximum, so its sampled final/peak ratio was 0.00295 despite the solver
  reaching -40.52 dB. Bound the true peak using matching sampled energies
  and solver-reported normalized dB, including printed rounding, and require
  a consistent final sample and exact stop marker. The 1e-4 energy threshold
  remains unchanged; solver normalization is not independent validation.
- **Treating pulse DFT magnitude as a frequency-domain voltage amplitude:**
  openEMS `DFT_time2freq` multiplies pulse transforms by the timestep.
  An absolute `1e-12` cutoff rejected the broadband incident spectrum in
  `candidate_20261122T114404317276Z`. Check dimensional scaling against
  a dimensionally consistent nominal source, relative bandwidth and numerical
  conditioning instead; do not treat this screen as port calibration.
- **Comparing a port-voltage spectrum directly to the electric excitation:**
  openEMS applies a soft electric-field excitation on Yee edges, so a raw
  source-to-voltage ratio has incompatible dimensions. For a nominal
  screening comparison multiply the source-field spectrum by the modeled
  excitation length; this is not a measured or calibrated terminal source.
- **Interpreting healed candidate fields after energy stop alone:** in
  `candidate_20261122T114813606476Z`, all six excitations reached the energy
  stop and the PEC screens passed, but the three-mesh comparison failed and
  the unvalidated matrices exceeded the existing strict reciprocity
  tolerance. Preserve the unreleased probes and investigate port calibration,
  geometry, mesh and duration together; do not export a Touchstone or infer
  filter bypass from the failed model.
- **Ignoring measured incident waves at the unexcited port:** the saved
  `candidate_20261122T114813606476Z` probes show nonzero incident waves at
  both ports. Dividing each reflected column only by the driven port's
  incident wave is not generally equivalent to the two-excitation
  scattering relation. Assemble both measured incident-wave columns and
  solve `B = S A`, reject ill-conditioned matrices, then retain all independent
  convergence, passivity and reciprocity gates.
- **Assuming the same current-probe box produces the same FDTD contour on
  refined meshes:** the saved candidate coarse/medium current-probe outputs
  span z=0.8–2.120 mm, while fine spans 1.0–1.867 mm. Compare the output
  probe coordinates and establish calibrated, comparable measurement surfaces;
  neither the differing contours nor the source of the network discrepancy is
  resolved by a successful energy stop.
- **Assuming a successful energy stop establishes exact discrete passivity or
  reciprocity:** the independent floating resistor-loop calibration recorded
  in `candidate_20261122T114813606476Z/diagnostic_findings.md` reached -80 dB
  but still exceeded both existing 1e-9 numerical gates. Compare against a
  bounded reference and preserve the original gates; a near-ideal circuit
  does not validate the PCB model.
- **Assuming the FDTD engine uses double precision because postprocessing
  uses NumPy doubles:** openEMS v0.37.0 defines `FDTD_FLOAT` as `float`
  in `tools/constants.h`. Use the solver precision when screening numerical
  cancellation; a double-precision Fourier transform cannot recover lost
  field precision. This is not a justification for relaxing release gates.
- **Assuming changing `FDTD_FLOAT` alone creates a validated double-precision
  solver:** the upstream v0.37.0 SSE engine uses separate four-float vector
  field arrays (`FDTD/engine_sse.h`). Any alternative build needs a compatible
  engine, dependent libraries and independent benchmark validation before
  PCB results can be interpreted.