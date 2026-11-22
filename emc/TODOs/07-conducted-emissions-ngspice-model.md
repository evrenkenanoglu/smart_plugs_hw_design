# TODO 07 — Build a bounded conducted-noise circuit model

**Status:** Candidate sensitivity simulations permitted; matched source/test-network evidence remains unavailable  
**Depends on:** TODOs 01, 02, and 04; source and product/test inputs are
required for product-specific conclusions

The generic `tests/test_spice_lisn.py` suite passes (9 tests), but it does not
simulate or validate a CISPR LISN/AMN or receiver. It tests analytic helper
math and fail-closed provenance/version behavior only.

## Work

- [ ] Build the evidence-supported candidate topology, explicitly label
  component and source assumptions, and represent unknown sealed-module
  behavior as unknown.
- [ ] If using a LISN/AMN network, identify the applicable product/test
  configuration with a qualified compliance specialist and use a
  corresponding documented network, or clearly label an explicit candidate
  LISN as an assumption. Do not assume it applies to every product.
- [ ] Use validated switching/source data where available. If absent, use
  explicitly labeled illustrative CM/DM source scenarios and sweep documented
  parameters; do not call the result an emissions prediction or use arbitrary
  capacitance values as product facts.
- [ ] Include component parasitics only when datasheets/models support them;
  record their frequency range and provenance.
- [ ] Define CM/DM quantities consistently with the modeled conductors and
  measurement network.
- [ ] If using transient FFTs, document timestep, record length, window, and
  spectral resolution. Do not treat an ordinary FFT as a standards receiver's
  bandwidth, quasi-peak, or average detector.
- [ ] Use the model for comparative filter/source sensitivity, not a
  compliance pass/fail or test-limit margin.
- [ ] Consider FastHenry/FasterCap or other quasi-static extraction only if a
  defined parasitic question requires it; validate the geometry and extraction
  assumptions before coupling it into the circuit model.

## Done when

The circuit model is reproducible and distinguishes verified inputs from
assumed scenarios; its sensitivity and missing source data are reported.
Without a validated source and correct test configuration, results remain
illustrative only.

## Safety boundary

This task is simulation/documentation only. Do not perform home LISN or
energized mains testing.
