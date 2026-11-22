# L1-route transmission-line pilot

This tests whether native layout data can drive an openEMS workflow. It uses
three `L1_3` route segments near L1 from the 2026-11-15 native EasyEDA archive,
then builds a **straightened transmission-line coupon** with the same aggregate
route length and 1 mm trace width. The native route's bends and surroundings
are not modeled. It is **not** a smart-plug EMC result or a prediction of
emissions.

The coupon uses an assumed 1.6 mm FR-4 substrate, assumed dielectric
properties, a continuous bottom reference plane that is not imported from the
PCB, and openEMS microstrip ports with a 1.05 GHz center / 1.9 GHz bandwidth
Gaussian excitation over a 100 MHz–2 GHz sweep. Port impedance is extracted by
openEMS rather than assumed to be 50 ohms. The
choke, capacitor, remaining PCB copper, components, enclosure, cables, and
actual noise source are excluded. Therefore, its S-parameters cannot be
interpreted as actual filter attenuation or emissions. No mesh-convergence or
material-sensitivity study has yet been performed.

Run from the hardware repository root after activating the installed openEMS
environment:

```powershell
. .\emc\openems\activate.ps1
python .\emc\openems\experiments\l1_route_pilot.py
```

Append `--setup-only` to validate the geometry and ports without time-stepping.
The maximum number of FDTD steps defaults to 250,000 and can be changed with
`--max-timesteps`.
Each run gets a new directory under `emc\openems\experiments\runs\` containing
the source hash and model assumptions, solver geometry, S-parameter CSV, and
plot. The CSV includes the frequency-dependent port reference impedance. The
native EasyEDA source is read-only.

The 2026-11-17 run in `runs\l1_route_20261117_180814` reached the solver's
−40 dB energy end criterion after 132,608 steps. This verifies that the
exploratory geometry ran through its time-domain termination criterion and
post-processing; it does not establish model accuracy or S-parameter
convergence. Its results remain unsuitable for product EMC or filter-
performance conclusions without mesh refinement, sensitivity analysis, and
the omitted physical inputs. An earlier 70,000-step run hit its step cap and
is unconverged; do not interpret its S-parameters.

The first lumped-port draft did not produce a valid run and its output is
discarded. The current coupon uses openEMS microstrip ports, following the
installed official tutorial API; the generated plot and data remain
exploratory and must not be used as evidence of product performance.
