# openEMS setup and model gates

openEMS is the selected open-source full-wave solver for targeted 3D EMC investigations. It uses FDTD and can calculate fields from an explicitly modeled structure; the result depends on the accuracy of the input geometry, materials, source, and boundary conditions. It is not a turnkey EasyEDA EMC checker.

## Installed tool and verification

The current Windows user has the official openEMS v0.37.0 package installed at `%LOCALAPPDATA%\openEMS\0.37.0`, with an isolated Python 3.13 environment in its `venv` subfolder. The downloaded release archive was verified against the GitHub release SHA-256: `e4f14fd6e9be7d0c1fd9c244768c21c1c2b62b8aa81f08253ebf6e06040cda5a`.

From the hardware repository root, activate the installation in the current PowerShell session:

```powershell
. .\emc\openems\activate.ps1
python -c "import CSXCAD, openEMS; print(CSXCAD.__version__, openEMS.__version__)"
```

The official upstream `openEMS/python/Tutorials/MSL_NotchFilter.py` tutorial was run successfully with openEMS 0.37.0, CSXCAD 0.7.0, and Python 3.13.11. It simulated 269,780 FDTD cells for 14,484 timesteps, reached its -60 dB termination criterion (-60.92 dB) in 24.58 seconds, and completed port post-processing. This verifies the installation and a basic FDTD run only; it is not a smart-plug PCB model or EMC result.

The installed archive is the official Windows MSVC build. Upstream describes it as a quick start and warns of possible severe performance degradation in some cases; use a Linux source build for longer production runs if this becomes a limitation. See the [official installation guide](https://docs.openems.de/en/latest/install/index.html) and [openEMS source project](https://github.com/thliebig/openEMS).

## Candidate and release evidence

Exploratory models may use a user-selected candidate export even when revision
linkage is unknown. Record the exact export, hashes, mismatched dates, material
and geometry assumptions, and limitations; stamp every report and plot
`CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`.
Single-revision SHA-256 locking is required only for final manufacturing
release sign-off. See `AGENTS.md` and `EMC/input-checklist.md`.

For each model:

1. Define one bounded question (for example, compare two documented return-path geometries), the output quantity, and the frequency/time range.
2. Start from the simplest relevant geometry; add layers, components, enclosure, and representative cables only as needed and supported by source data.
3. Use documented material properties and source waveforms. Identify any unknowns, especially the internal switching behavior of the encapsulated AC/DC module and relay/load transients.
4. Check units, mesh quality, boundary distance/absorbing conditions, excitation, and port definitions. Use actual copper; never invent a ground plane.
5. Demonstrate mesh and time convergence for the quantity being compared. Run sensitivity cases for uncertain material, component, and cable parameters.
6. Preserve the script, all input-file hashes, assumptions, solver version, logs, and plots with the run. Label the result simulated and state limitations.

Do not interpret simulated fields as CISPR/EN/FCC emissions measurements or as a prediction of certification pass/fail without a validated correlation to measurements.

## Exploratory MAIN_OMRON bypass model

`smart_power_strip/workflows/03_local_pcb_em_extract.py --allow-candidate`
models an unpopulated L1 using differential pre- and post-choke ports and
the selected candidate's local copper and drills; no ground plane is added.
It assumes 1.6 mm FR-4, 1 oz outer copper as PEC sheets, 0.10 mm copper
snapping and idealized square grid-aligned drill openings and barrel walls.
These are geometry and material approximations, not manufacturing data. The
run report records candidate identity, port fixtures, convergence gates and
any failure. The reduced differential two-port cannot capture full
four-terminal/common-mode behavior; CY1 and converter coupling are excluded
from the idealized L1/C2 co-simulation.

Energy termination at 1e-4, source quality, PEC fidelity, passivity, mesh,
duration and boundary checks remain mandatory before releasing a network.
Solver energy dB can be used to conservatively bound the true peak when
wall-clock samples omit it; solver termination alone is not convergence.
