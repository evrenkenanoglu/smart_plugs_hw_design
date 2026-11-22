# Agent guidance

This repository contains a 230 V AC, high-current smart-plug design. Treat all mains circuitry and connected loads as hazardous.

## Safety and evidence

- AI output is design assistance only. Never claim a design is safe, compliant, or certification-ready based only on documentation, calculations, or simulation.
- Do not give instructions for improvised energized mains testing. Direct physical pre-compliance and certification testing to a properly equipped, qualified lab.
- Treat project notes as claims to verify, not as evidence of compliance. Check actual schematics, PCB data, BOMs, component datasheets, and applicable standards.
- Call out conflicting values and unknowns explicitly. Do not silently choose one source of truth.
- Distinguish measured, simulated, calculated, and assumed results. Record the candidate export folder (or locked revision) and model assumptions for every result.
- Any changes affecting mains isolation, protective earth, fusing, surge protection, current capacity, or thermal performance require review against the applicable product standards by a qualified person.

## Working with design files

- Exploratory and pre-design simulations (`ngspice`, `openEMS`, Gerber geometry checks) ARE explicitly authorized and MUST NOT be blocked on `locked: false`, missing Cloud project IDs, missing schematic PDFs, unverified `.epro2` archive linkage, mixed export dates, or mounting-hole MPNs. This rule takes precedence over any older Stage-0 lock requirement in `emc/input-checklist.md`, `emc/TODOs/`, or `.agents/skills/*/SKILL.md`.
- For exploratory runs, clearly identify which candidate export folder was used, record all assumed stackup/parasitic/synthetic-source values under **Assumptions**, keep solver convergence/passivity checks and no-invented-ground-plane rules active, and stamp outputs **`CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF`**.
- Reserve strict single-revision SHA-256 locking (`locked: true`) solely for final manufacturing release sign-off.
- Do not overwrite native CAD projects, released manufacturing files, or user changes unless explicitly asked.
- For EMC work, follow `emc/README.md`, and update `emc/input-checklist.md` / `emc/risk-register.md` with findings as work proceeds without blocking exploratory simulations.
- Use specialized skills in `.agents/skills/` when relevant. MCP servers are not pre-approved; review their publisher, permissions, and commands before enabling them.
- Keep an `Error registry` in relevant skills with verified pitfalls and mitigations; label unverified concerns as assumptions, not past errors.