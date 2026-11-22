# Smart Plugs Hardware

This repository contains the smart-plug ECAD inputs, manufacturing handoffs, engineering notes, calculation tools, and EMC design-assistance workflows. The mains design is hazardous; calculations and simulations do not establish safety, compliance, or certification.

## Structure

| Path | Contents |
| --- | --- |
| `pcb/libraries/` | Altium component libraries |
| `pcb/smart_plug_v3_easyeda/` | Target location for the intact EasyEDA project and its coupled outputs |
| `pcb/_archive/` | Target location for legacy Altium boards |
| `releases/main_pcb/`, `releases/ui_pcb/` | Revision-tagged, board-specific release packages |
| `docs/design_notes/` | PSU, ESP32, UI, and general design notes |
| `docs/datasheets/` | Datasheets |
| `docs/reviews/` | Review records and generated calculation index |
| `analysis/power_calculations/` | Calculation scripts, inputs, and reports organized by module |
| `emc/` | EMC simulation package, tests, inputs, and evidence |
| `_scratch/` | Unclassified or temporary material retained for review |

### Migration hold

At the time of this reorganization, EasyEDA Pro had the `Smart_Plugs` project open. Its native `Smart_Plugs.eprj2` remained under `PCB_DESIGN/Smart_Plugs_EasyEDA`, so that source tree and its associated outputs/backups were left together and its Mechanical references were not changed. Close the project before moving the complete tree to `pcb/smart_plug_v3_easyeda` and updating the path-only references in `MECHANICAL`. The legacy Altium folder move to `pcb/_archive/Smart_Plugs` was also refused by Windows and remains at `PCB_DESIGN/Smart_Plugs`; it has not been deleted or force-moved.

The existing `Releases/v0.3.0` content is a combined package dated 2026-03-11. It is not treated as separate main/UI releases or as revision-linked to the November 2026 STEP files and EasyEDA archives. Do not infer a production revision from filenames alone.

## Python environment and tasks

Use Python 3.10 or later. From this directory in PowerShell:

```powershell
python -m venv .venv
uv pip compile requirements.in -o requirements.txt --annotation-style line
.\.venv\Scripts\inv.exe install
.\.venv\Scripts\inv.exe --list
.\.venv\Scripts\inv.exe info
```

`requirements.in` declares Invoke, pytest, and the EMC package editable with its `all` extras. `inv compile` updates the pinned `requirements.txt`; `inv install` synchronizes the HW virtual environment from that file. `uv` must be available on PATH. openEMS is an external solver, not a Python dependency; the openEMS executable was not found during this audit. ngspice is available on the current system PATH.

Common tasks:

```powershell
.\.venv\Scripts\inv.exe calc
.\.venv\Scripts\inv.exe reports
.\.venv\Scripts\inv.exe compile
.\.venv\Scripts\inv.exe install
.\.venv\Scripts\inv.exe export-check --board all
.\.venv\Scripts\inv.exe emc-test
.\.venv\Scripts\inv.exe check
.\.venv\Scripts\inv.exe release --board all --version v0.3.x_check --dry-run
.\.venv\Scripts\inv.exe clean
```

`release` fails closed when any board-specific Gerber, drill, BOM, CPL, schematic PDF, or 3D STEP category is missing. A dry run never writes packages or manifests. Historical or combined exports are not reclassified as current releases.

## Known source conflicts

- `docs/design_notes/GENERAL_DESIGN_NOTES/HLK_10M05_5V_LOGIC_POWER_DESIGN_RATIONALE.md`, `docs/design_notes/GENERAL_DESIGN_NOTES/FOUR_CHANNEL_20A_SMART_PLUG_CONTROLLER_TECHNICAL_SPECIFICATION.md`, and `peak_data.json` identify HLK-10M05; `docs/design_notes/POWER_SUPPLY/HLK_5LS05_AC_TO_DC_CONVERSION_AND_FILTER_DESIGN.md` and design-chat notes identify HLK-5LS05.
- The calculation input/report identifies ESP32-WROOM-32UE, while design notes identify ESP32-C6. The current fitted/active board configuration has not been resolved.
- These values are preserved as found. No electrical design inputs or calculations were silently changed by the folder migration.

## Scratch items retained for review

- `_scratch/DESIGN_AI/` — AI-generated design notes and image.
- `_scratch/TEMP_PLUG_RELATED/` — teardown notes and images.
- `_scratch/UTILITY_Additional_Components/` and `_scratch/UTILITY_JLCPCB_useful_component_list.md` — utility notes not identified as reusable CAD library assets.
