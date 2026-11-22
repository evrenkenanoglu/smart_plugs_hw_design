# TODO 06 — Calibrate openEMS and check convergence

**Status:** Complete for the generic coupon benchmark; this does not authorize project-specific FDTD
**Can proceed:** In parallel with revision lock and board review, using a
generic benchmark; must pass before project-specific FDTD

The official notch-filter tutorial verifies the installation. The historical
coupon diagnostic found an approximately 50.3% difference between the simple
analytical estimate and the pilot's frequency-dependent MSL port reference
impedance; this is not an independent benchmark or a mesh-convergence result.
Do not treat the coupon as calibrated.

## Generic coupon diagnosis and runs

The opt-in generic microstrip coupon ran on 2026-11-17 at
`smart_power_strip/runs/benchmark/generic_msl_20261117T223745.078238Z_34240038/`.
The original two-mesh setup reached the configured energy stop, but failed the
10% analytical agreement and 5% refinement gates. After explicitly snapping
trace edges and port planes, checking 1/3-2/3 trace-edge grading, using
`AddMSLPort`, increasing the substrate resolution, and adding a medium mesh, the
three-mesh run at
`smart_power_strip/runs/benchmark/generic_msl_20261118T115911.948110Z_9bd8c666/`
passed the energy, power-excess, and all-pair refinement gates. The analytical
errors were still 14.61%, 13.50%, and 12.99% for coarse/medium/fine, against
10%. The maximum all-pair mesh change fell to 2.37%, against 5%.

The saved geometry for that run verified that the trace edges and substrate
surfaces are exactly on mesh lines, and the port is an `AddMSLPort`, not a
`LumpedPort`. The 1/3-2/3 edge grading and 4/6/8 substrate cells were
recorded. `FeedShift` is 2 mm and `MeasPlaneShift` is 8 mm; the feed and
measurement plane are 6 mm apart, and the measurement plane is 2 mm from the
straight coupon end. All
planes are outside the PML cells. The initial transverse object-to-PML
clearance was only about 4.0-4.8 mm, well below a quarter of the 150 mm
free-space wavelength at 2 GHz. The domain-expansion rerun below tested
boundary sensitivity, but did not by itself explain the analytical mismatch.

The corrected frequency-by-frequency power balance is normalized using each
port's real characteristic admittance, `Re(1/Z_ref)`, because `|S11|^2 +
|S21|^2` alone is not the power sum when the two voltage-wave reference
impedances differ. The reported deficit is not attributed solely to dielectric
loss; it can also include radiation/PML absorption and numerical error. `Z_ref`
is a solver-derived modal quantity, not a measured impedance. The coupon is
generic and is not the user's PCB.

### Transverse-domain sensitivity rerun

The rerun at
`smart_power_strip/runs/benchmark/generic_msl_20261118T122518.268588Z_1bbe54d1/`
expanded the y/z domain to ±80 mm. The actual `PML_8` interfaces were
y=±56.727 mm and z=-56.770/+56.296 mm. This left 40.727 mm from the 32 mm
return-plane edges to either y interface and 55.170/56.296 mm from the
substrate boundaries to the z interfaces, exceeding the configured 37.474 mm
quarter-free-space-wavelength minimum at 2 GHz. The x interfaces remained
7.273 mm outside each port start; the uniform line continues through those
x-directed PMLs.

All three meshes reached the energy stop, passed power-excess checking (power
sum 0.9891-0.9928), and passed all-pair mesh stability (maximum 1.30%, versus
5%). They still failed the 10% analytical gate: coarse/medium/fine maximum
complex errors were 23.58%, 22.91%, and 22.58%. More importantly, changing the
transverse domain/PML placement from the prior narrow setup changed the fine
input/output `Z_ref` by about 14% at representative frequencies, despite each
run being internally mesh-stable. For example, at 1.05 GHz the input changed
from 81.75+j0.62 ohm to 71.69+j0.61 ohm, and the output from 80.79+j0.93 ohm
to 70.75+j0.82 ohm. This is observed domain sensitivity; it does not identify
the cause or establish that either result is accurate. The larger padding did
not fix the benchmark, and no gate was relaxed.

### Corrected mesh-grading rerun

The serialized fine mesh from the failed run above showed the remaining defect:
the 0.2 mm substrate cells were followed immediately by 2.857 mm air cells
above the strip, while lateral spacing jumped from 0.125 mm in the trace region
to 1 mm outside ±3 mm. These fixed abrupt transitions persisted across mesh
levels, despite the prior local trace-edge and substrate refinement.

The rerun at
`smart_power_strip/runs/benchmark/generic_msl_20261118T175255.072265Z_13b75fa3/`
changed the lateral and upper-air mesh to geometric grading (maximum 1.4
spacing growth, 1 mm lateral-cell cap, and 3 mm upper-air-cell cap). It
retained `AddMSLPort` at both ends, with 30 mm port extensions,
`FeedShift=2 mm`, `MeasPlaneShift=15 mm`, and `Feed_R` at its default infinity.
The feed and measurement planes are mesh-snapped, 13 mm apart, and inside the
port extensions; the measurement plane is 15 mm from the coupon end. Because
`Feed_R` is infinite, the line continues through the x-directed `PML_8` rather
than ending in a resistor. The setup also retained the ideal ground reference
at PEC `z_min` (not a finite floating sheet), y/z MUR boundaries, analytical
equation, and boundary cases. The new first air cells were 0.4/0.267/0.2 mm
for coarse/medium/fine, with 4/6/8 cells through the 1.6 mm substrate. The
controlled change moved medium-mesh `Z_ref` from about 71 ohm to 84.6 ohm at
1.05 GHz, reducing the maximum complex analytical error from about 20% to
5.63%. This identifies abrupt near-field mesh grading as the failure's root
cause in this generic benchmark; it does not validate a product model.

All nine solver runs reached the energy stop before their timestep caps and
passed the configured power-excess check. The canonical 45 mm coupon's
coarse/medium/fine maximum analytical errors were 8.21%, 5.63%, and 4.30%;
the maximum all-pair mesh change was 4.17%. The largest independent x/y/z
boundary change was 1.97%, and the original 15.4598 mm coupon differed from
the 45 mm diagnostic by at most 1.91%. The 10% analytical, 5% mesh, and 5%
boundary gates all pass without relaxation. `report.md` and `run_metadata.json`
in the run folder record assumptions, power balance, solver versions, and
per-case results.

The compared quantity is the frequency-dependent openEMS `MSLPort.Z_ref`
modal reference impedance, compared as a complex quantity against the
lossless Hammerstad-Jensen `Z0` estimate at 100 MHz-2 GHz; it is not measured
impedance or a 50-ohm S-parameter normalization. The 15.4598 mm coupon changed
by at most 1.91% versus the 45 mm coupon at fine mesh, so the short length was
not the remaining source of the earlier large error. The pass is only for the
lossless, idealized generic coupon. Candidate PCB-specific FDTD may proceed
with explicit input and model assumptions, subject to its own numerical checks.

## Work

- [x] Retain the successful official openEMS tutorial run as installation
  evidence; reproduce it again only if the environment changes.
- [x] Define and run an opt-in generic coupon with documented assumptions,
  ports, and an analytical reference. Reuse the official tutorial result only
  as installation evidence.
- [x] Verify mesh placement, trace edge grading, port excitation/measurement
  planes, excitation registration, and finite solver output for the recorded
  three-mesh run.
- [x] Run coarse/medium/fine meshes and compare the frequency-dependent
  port-reference quantity; the final run passes both the 10% analytical and
  5% mesh-stability gates.
- [x] Refine local geometry sufficiently; use gradual outer-cell grading in
  addition to trace-edge and substrate refinement, rather than relying on
  wavelength resolution alone.
- [x] Check simulation-duration/end-criterion and independent x/y/z
  boundary-domain sensitivity; all nine final runs reached the energy stop and
  the maximum boundary change was 1.97%.
- [x] Use a power-normalized network check and report its unaccounted-power
  range without attributing it to a single loss mechanism.
- [x] Record solver version, timestep, cell count, stop status, mesh settings,
  actual PML coordinates, and result changes for each run.

## Done when

The benchmark agrees with its analytical or trusted reference within a
predeclared, justified tolerance, and the reported quantity is stable under
mesh and time/boundary refinement.

This completion applies only to the generic coupon. It does not satisfy the
separate source-data, geometry, or numerical requirements for a
project-specific smart-plug model; revision locking is for final release.

## Stop condition

If the benchmark diverges, is unstable, or does not converge, do not move on to
project-specific full-wave conclusions. Update the openEMS skill's Error
registry only with reproduced pitfalls and verified mitigations.
