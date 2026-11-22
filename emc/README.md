# Agent guidance

This repository contains a 230 V AC, high-current smart-plug design. Treat all mains circuitry and connected loads as hazardous.

## Safety and evidence

- AI output is design assistance only. Never claim a design is safe, compliant, or certification-ready based only on documentation, calculations, or simulation.
- Do not give instructions for improvised energized mains testing. Direct physical pre-compliance and certification testing to a properly equipped, qualified lab.
- Treat project notes as claims to verify, not as evidence of compliance. Check actual schematics, PCB data, BOMs, component datasheets, and applicable standards.
- Call out conflicting values and unknowns explicitly. Do not silently choose one source of truth.
- Distinguish measured, simulated, calculated, and assumed results. Record the board revision (or candidate export set) and model assumptions for every result.
- Any changes affecting mains isolation, protective earth, fusing, surge protection, current capacity, or thermal performance require review against the applicable product standards by a qualified person.

## Working with design files

- Clearly identify which EasyEDA project, board, and candidate/locked export set was used for every analysis.
- Do not overwrite native CAD projects, released manufacturing files, or user changes unless explicitly asked.
- Exploratory and pre-design simulations (`ngspice`, `openEMS`, Gerber geometry checks) ARE explicitly permitted on user-selected candidate exports (even when manifests are unlocked or exports come from different dates), provided all date differences, assumed stackups, synthetic sources, and gaps are explicitly documented under **Assumptions** and stamped **`CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`**. Reserve strict single-revision locking (`locked: true`) for final release sign-off.
- For EMC work, follow `emc/README.md` (and update `emc/input-checklist.md` / `emc/risk-register.md` as findings emerge without blocking exploratory simulations).
- Use specialized skills in `.agents/skills/` when relevant. MCP servers are not pre-approved; review their publisher, permissions, and commands before enabling them.
- When adding a recurring project workflow, create or update its relevant skill. Keep an `Error registry` in each relevant skill with verified pitfalls and mitigations; label unverified concerns as assumptions, not past errors.