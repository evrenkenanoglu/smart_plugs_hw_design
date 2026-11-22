# TODO 05 — Audit the pilot and calculate a baseline

**Status:** Partial — historical pilot defects identified; discrepancy not quantitatively resolved
**Depends on:** Existing exploratory pilot; use TODOs 01–02 to reassess its
physical relevance

## Work

- [x] Preserve the current pilot as an exploratory workflow demonstration;
  do not use its S-parameters to make PCB or filter decisions.
- [x] Recalculate an analytical transmission-line estimate from the modeled
  dimensions and assumptions, and compare it with the frequency-dependent
  openEMS port reference impedance. The discrepancy remains unresolved.
- [x] Investigate the pilot's roughly 133–135 ohm reported MSL port reference
  impedance against the analytical estimate; identify verified model defects
  without assuming they explain the entire difference.
- [x] Check the CSV, reference-impedance convention, port definitions, and
  available power-wave data. The saved magnitudes are insufficient to
  reconstruct a power balance; do not apply `|S11|^2 + |S21|^2` as a
  passivity test.
- [ ] Estimate expected dielectric/conductor loss and check that the model's
  materials and geometry support that comparison.
- [ ] Derive mesh limits from the highest modeled frequency and material
  properties, then refine locally for the actual trace, gaps, and other
  geometrical features.
- [x] Record the calculation inputs, method, and uncertainty separately from
  simulated values.

## Findings and limits

- The original report compares a real-part midpoint of about 134.2 ohm with
  the zero-thickness Hammerstad-Jensen estimate of 89.259 ohm for isotropic
  `epsilon_r=4.2`, a roughly 50.3% real-part difference. The saved CSV has 381
  points from 100 MHz to 2 GHz; at 1.05 GHz its input-port value is
  `134.712+j3.641 ohm`. This is a solver-extracted, frequency-dependent
  `MSLPort.Z_ref`, not a measurement.
- The archived XML records `epsilon=(4.2,1,1)` and
  `kappa=(4.906787e-3,0,0)`, although the pilot passed scalar values intending
  isotropic FR-4. The equivalent loss tangent along x is 0.02 only at 1.05
  GHz; because the serialized conductivity is fixed, it varies approximately
  from 0.21 at 100 MHz to 0.0105 at 2 GHz. The other tensor components have no
  dielectric loss. Copper and the return plane are PEC, so conductor loss is
  absent. These are verified setup defects/limitations, but their separate
  effect on `Z_ref` has not been isolated.
- The pilot uses `FeedShift=5 mm` and `MeasPlaneShift=5.5 mm` in a 6 mm port
  extension: the planes are only 0.5 mm apart, and the measurement plane is
  0.5 mm from the straight coupon end. The top MUR boundary is at z=7.9 mm,
  only 7.9 mm above the strip. This differs from the later, longer-port and
  larger-domain generic calibration. `z_min` is PEC and supplies an infinite
  ideal ground reference; the finite ground primitive in the XML is not a
  floating isolated ground.
- The pilot calls `CalcPort` without an explicit `ref_impedance`, so openEMS
  uses the extracted transmission-line reference impedance. Its CSV stores
  only S11/S21 magnitudes and the input port's complex `Z_ref`; it omits
  complex S-parameter phase and output-port `Z_ref`. Therefore a
  frequency-by-frequency power balance cannot be reconstructed from this CSV.
- At 2 GHz, a nominal isotropic `epsilon_r=4.2` gives a dielectric wavelength
  of about 73 mm, so the 0.5 mm nominal spacing is fine for wavelength
  resolution alone. The 1.6 mm substrate has only 3.2 nominal cell intervals
  (four actual z cells after surface snapping), and the mesh was explicitly
  marked unconverged. The tensor anisotropy, narrow local geometry, short
  port-to-measurement spacing, and boundary setup mean wavelength resolution
  alone is not evidence of an accurate impedance or loss result.
- These findings describe only the archived exploratory coupon. Its source
  archive is dated 2026-11-15 and has not been confirmed as the authoritative
  PCB revision. Do not use the pilot or the generic benchmark to make PCB or
  filter decisions.

## Existing run

`emc/openems/experiments/runs/l1_route_20261117_180814` reached the solver's
time-domain energy stop after 132,608 timesteps, but its metadata explicitly
marks the 0.5 mm mesh unconverged. It uses a straightened route, anisotropic
serialized material values, PEC copper, and an ideal bottom PEC boundary.
Its approximate S11 and S21 describe that artificial coupon only.
Time-domain termination does not establish mesh convergence or physical
accuracy.

## Done when

Analytical expectations and port/power normalization are independently
checked, discrepancies are explained, and no product conclusion relies on the
exploratory coupon.
