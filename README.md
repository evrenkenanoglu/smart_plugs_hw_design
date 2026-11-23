# Smart Plugs Hardware

This repository contains the smart-plug ECAD inputs, manufacturing handoffs, engineering notes, calculation tools, and EMC design-assistance workflows. The mains design is hazardous; calculations and simulations do not establish safety, compliance, or certification.

## Structure

| Path | Contents |
| --- | --- |
| `PCB/libraries/` | Altium component libraries |
| `PCB/_archive/` | Legacy Altium boards |
| `ECAD/Smart_Plugs_EasyEDA/` | Current EasyEDA project and its coupled outputs |
| `RELEASES/main_pcb/`, `RELEASES/ui_pcb/` | Revision-tagged, board-specific release packages |
| `DOCS/design_notes/` | PSU, ESP32, UI, and general design notes |
| `DOCS/datasheets/` | Datasheets |
| `DOCS/reviews/` | Review records and generated calculation index |
| `ANALYSIS/power_calculations/` | Calculation scripts, inputs, and reports organized by module |
| `EMC/` | EMC simulation package, tests, inputs, and evidence |
| `_SCRATCH/` | Unclassified or temporary material retained for review |

### Migration hold

The EasyEDA project and coupled outputs remain together under `ECAD/Smart_Plugs_EasyEDA/`; backup archives are excluded from Git. Mechanical references point to this source tree. The legacy Altium project is archived under `PCB/_archive/Smart_Plugs`.

The existing `Releases/v0.3.0` content is a combined package dated 2026-03-11. It is not treated as separate main/UI releases or as revision-linked to the November 2026 STEP files and EasyEDA archives. Do not infer a production revision from filenames alone.

## Python environment and tasks

Use Python 3.10 or later. From this directory in PowerShell:

```powershell
python -m venv .venv
uv pip compile requirements.in -o requirements.txt --annotation-style line
.\.venv\Scripts\inv.exe install
.\.venv\Scripts\inv.exe --list
.\.venv\Scripts\inv.exe info
.\.venv\Scripts\python.exe -m invoke case-paths
```

`requirements.in` declares Invoke, pytest, and the EMC package editable with its `all` extras. `inv compile` updates the pinned `requirements.txt`; `inv install` synchronizes the HW virtual environment from that file. `uv` must be available on PATH. openEMS is an external solver, not a Python dependency; the openEMS executable was not found during this audit. ngspice is available on the current system PATH.

Copilot CLI workspace MCP servers are registered in root `.mcp.json`; AI-specific policy and setup notes are under `.agents/mcp/`.

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

## Current design decisions and legacy references

- The latest design decision is **HLK-5LS05** for AC/DC and **ESP32-C6**. Older references in `DOCS/design_notes/GENERAL_DESIGN_NOTES/HLK_10M05_5V_LOGIC_POWER_DESIGN_RATIONALE.md`, `DOCS/design_notes/GENERAL_DESIGN_NOTES/FOUR_CHANNEL_20A_SMART_PLUG_CONTROLLER_TECHNICAL_SPECIFICATION.md`, and `ANALYSIS/power_calculations/POWER_CALCULATIONS/data/peak_data.json` identify HLK-10M05; treat those as superseded.
- The power calculation inputs/reports also retain ESP32-WROOM-32UE. Treat that as a legacy reference, not the current decision.
- The older design notes and calculation inputs remain unchanged pending an explicitly requested technical update; do not use them to override the current design decisions.

## Scratch items retained for review

- `_SCRATCH/DESIGN_AI/` — AI-generated design notes and image.
- `_SCRATCH/TEMP_PLUG_RELATED/` — teardown notes and images.
- `_SCRATCH/UTILITY_Additional_Components/` and `_SCRATCH/UTILITY_JLCPCB_useful_component_list.md` — utility notes not identified as reusable CAD library assets.
