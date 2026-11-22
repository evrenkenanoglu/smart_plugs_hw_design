# EMC model input checklist

Use this checklist to record what is verified vs. assumed for each model. Strict full-set matching is required only for final release sign-off; **exploratory candidate simulations** are explicitly permitted with unchecked items provided missing items, export-date differences, and assumed values are recorded under **Assumptions** and outputs are stamped **`CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`**.

## Assumptions: 2026-11-21 MAIN_OMRON candidate

- Candidate Gerbers/drills, netlist and placement:
  `smart_power_strip/inputs/locked_rev/MAIN_OMRON/MCP_CANDIDATE_20261121_1753/`;
  the Nov 19 BOM and stackup metadata are not linked to this candidate or the
  native archive. The revision manifest remains unlocked.
- Candidate archive SHA-256:
  `b6dddaf2be7855431e044350a63596575af5b4ee48bbcb2ec1d888b43b297e88`;
  netlist SHA-256:
  `2258d3c24cb4964cf5eed88bb7dddddda13e12d7c0c0451c622ee99166d82f9f`.
  Extracted top, bottom, PTH and via files were byte-checked against the archive.
- The Nov 19 layer metadata states two copper layers, but has no physical
  stackup. For exploration assume 1.6 mm FR-4, relative permittivity 4.2,
  loss tangent 0.02 and 1 oz (0.035 mm) outer copper. These are not
  fabricator-confirmed. Both PTH drill sets are assumed through both layers.
  The archived `candidate_20261121T190603352833Z` diagnostic XML serializes
  isotropic FR-4 epsilon and conductivity as three equal components; this
  confirms serialization only, not the physical material properties.
- Candidate netlist connects L1.3 to U1.2 and CY1 between U1.4 and GND; local
  Gerbers lack net attributes. No ground plane may be inferred or invented.
- The candidate bottom Gerber import normalizes one self-touching region and
  removes two zero-length edges with a warning; the importer subtracts
  configured drill cuts but does not model plated barrels or finite copper
  thickness. NPTH export and local net-to-polygon identity are unconfirmed.
  The attempted 3D model adds assumed ideal plated barrels of 25 µm wall
  thickness; that assumption is not evidence of actual plating.
- The candidate 3D diagnostic `smart_power_strip/runs/pcb_em/candidate_20261121T193813588877Z/`
  retains four unused bottom-copper polygon warnings after exact cutout
  partitioning and merging. Its 1,000-step excitation is truncated; neither
  the PEC midpoint screen nor this diagnostic establishes RF network validity.
- With the same revised copper geometry, the 40,000-step diagnostic
  `smart_power_strip/runs/pcb_em/candidate_20261121T194454406820Z/` no longer
  truncates excitation but retains four unused polygon warnings and ends at a
  sampled energy ratio of 0.325, above the 0.0001 stop criterion. No RF
  network or BOM co-simulation is valid from that diagnostic.
- A separate session-only mesh experiment added x anchors at 54.780, 54.855,
  54.866, 57.813 and 57.82541 mm and y anchors at -93.510, -93.500, -93.490,
  -87.640, -87.630 and -87.620 mm to the coarse diagnostic mesh. Its 1,000-step
  run reported zero unused-primitive warnings, no missing expected planar PEC
  midpoints or barrel cardinal segments, 1,327,200 cells and a 5.892 fs
  timestep. The source was truncated and no RF result is valid. These
  exploratory anchors are not a validated or practical mesh solution; the
  much smaller timestep substantially worsens the full-solve cost.
- A sparser session-only experiment used x anchors 54.780, 54.854, 54.869,
  57.811 and 57.821 mm without the added y anchors. At 1.0 and 0.75 mm
  nominal spacing it produced zero unused warnings, no missing expected
  planar PEC midpoints or barrel cardinal segments, and respectively 873,600
  and 1,111,040 cells with approximately 23.8 fs timesteps. At the existing
  0.5 mm fine spacing it still produced zero unused warnings but missed one
  expected top-copper PEC midpoint, so it fails the fidelity gate. All three
  1,000-step excitations were truncated and provide no RF network result.
- The later pre-/post-choke candidate model uses the `[16, -104, 42, -88.8]`
  mm crop, 0.10 mm copper snapping with 0.001 mm edge bias, square drill
  openings and ideal 0.020 mm PEC barrel walls, plus idealized port fixtures.
  Snapping is not a guaranteed minimum feature width. These change geometry
  and require sensitivity review; matching planar-island
  and plated-hole attachment topology does not prove sub-cell fidelity.
  Coarse diagnostic `smart_power_strip/runs/pcb_em/candidate_20261122T113700703757Z/`
  had 164,430 cells, a 770.3 fs timestep and zero unused primitives, missing
  screened copper midpoints or barrel-edge segments. It was capped at 1,000
  steps and its excitation was truncated.
- Full coarse port-1 attempt `smart_power_strip/runs/pcb_em/candidate_20261122T113735712887Z/`
  reached the solver's -40 dB stop at 20,240 steps (-40.52 dB, 15.59 ns),
  but was originally rejected because the sampled peak missed the true
  transient peak. The maximum final-to-peak ratio reconstructed from matching
  solver dB and energy samples, conservatively accounting for displayed
  rounding, is 8.873e-5. This relies on the solver's reported normalization;
  it does not establish mesh, duration, boundary, passivity or port validity.
- Repeated coarse port-1 attempt `smart_power_strip/runs/pcb_em/candidate_20261122T114404317276Z/`
  reached -40.49 dB with no unused primitives, but was stopped by an absolute
  `1e-12` incident-spectrum threshold. The openEMS pulse DFT includes a
  timestep factor, so its scale is in voltage-seconds; that absolute cutoff
  is not a voltage-amplitude criterion. Its incident magnitude varied by
  less than 8% across 30 MHz–1 GHz. The previously recorded ratio of
  0.00184 compared voltage with an electric-field source and was
  dimensionally invalid. Normalizing the source-field DFT by the 6 mm
  nominal port length gives about 0.307; this is a screening ratio, not
  calibrated source voltage. Physical port calibration remains open.
- Full healed model run `smart_power_strip/runs/pcb_em/candidate_20261122T114813606476Z/`
  reached the 1e-4 energy stop for all six coarse/medium/fine excitations.
  The grids had 164,430/484,155/617,715 solver cells and 770.3/436.1/385.2 fs
  timesteps; the latter two exceed the requested 300,000-cell target.
  Correcting both measured incident-wave columns after the run gave
  coarse/medium, medium/fine and coarse/fine complex S-entry differences
  of 12.78%, 10.00% and 19.35%, respectively, failing the 5% mesh gate.
  The unvalidated matrices also exceeded the existing strict reciprocity
  tolerance. Separate -60 dB coarse port-1/port-2 diagnostics reached
  38.22/26.52 ns; the corrected full two-port differs from the -40 dB result
  by up to 10.20%, failing the 5% time-stability screen. A -60/-80 dB coarse
  comparison changed by 0.655%, but retained a 4.02e-4 maximum absolute
  reciprocity error and did not verify other meshes. Current-probe
  integration coordinates change with mesh, and six alternative coarse
  integration contours did not resolve the reciprocity discrepancy. No
  Touchstone or BOM co-simulation was
  released. See that run's `diagnostic_findings.md`.
- An independent floating two-port resistor-loop calibration with no PCB
  and no ground plane gave S11=0.500051+j0.002948 and S21=0.499970-j0.004072
  at 30 MHz versus ideal quasistatic values of 0.5. After a -80 dB stop, its
  maximum singular value was 1.00002124 and reciprocity error 2.96e-8, both
  outside the existing 1e-9 gates. Finite structure/radiation and numerical
  approximation are omitted by the ideal reference; this is not a reason to
  relax the PCB model gates. Uniform and trapezoidal voltage-probe averages
  also failed the gates. The openEMS v0.37.0 source defines FDTD fields using
  `float`; its precision does not establish a bound on these errors.
- The BOM identifies L1 UU9.8-10mH, C2 100 nF, CY1 2.2 nF, R6 10D-7,
  RV1 14D431K with 440 pF listed, and U1 HLK-5LS05. Ratings, parasitics,
  source spectrum and exact revision linkage need independent verification.

## Design identity and geometry

- [ ] EasyEDA Pro project identity, board name, revision, export date, and source-file hash.
- [ ] Complete current Gerber set: every copper layer, board outline, solder mask, and relevant fabrication layers.
- [ ] Current PTH/NPTH drill files, with units and drill/plating information.
- [ ] Current schematic, netlist, BOM, and assembly/pick-and-place data, matched to the same revision.
- [ ] Current 3D board assembly and enclosure CAD, with known units, materials, and dimensions.
- [ ] Confirmation that the board exports and mechanical model represent the same revision.

## Stackup and materials

- [ ] Fabricator-confirmed board thickness and layer order.
- [ ] Copper thickness/weight per layer, including plating where relevant.
- [ ] Laminate material and frequency-dependent dielectric data, or explicit documented approximations.
- [ ] Component package geometry and metal structures for parts included in a full-wave model.
- [ ] Enclosure, cable, connector, and nearby-metal material/geometry assumptions.

## Electrical sources and operating cases

- [ ] Exact manufacturer part numbers and datasheets for the AC/DC module, input-filter parts, relays, protection devices, and radio module.
- [ ] Valid SPICE or equivalent models for components included in circuit simulations.
- [ ] Source impedance and switching waveform/frequency, or a documented reason they are unavailable.
- [ ] Relay switching cases and representative load types (resistive, inductive, capacitive), including simultaneous-channel cases.
- [ ] External cable types, lengths, routing, terminations, and enclosure placement relevant to the question.
- [ ] ESP32 module/antenna variant, radio mode/channel, and antenna keepout/nearby materials.
- [ ] Intended markets, product category, applicable standards, and test configurations confirmed by a qualified compliance specialist.

## Model quality and reporting

- [ ] One bounded question and output quantity defined before modeling.
- [ ] Coordinate system, units, excitation, ports, boundaries, mesh, frequency/time span, and solver version recorded.
- [ ] Tutorial/benchmark smoke test completed before project modeling.
- [ ] Mesh and simulation-duration convergence checked for the reported quantity.
- [ ] Assumptions, uncertainty, source revision, and file hashes recorded with every run.
- [ ] Result labeled as simulated, not measured, certified, or proof of compliance.