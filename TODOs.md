# Follow-up improvements

These are additional tasks beyond the current folder and MCP setup.

- [ ] Reconcile the power-calculation inputs and reports with the current
  HLK-5LS05 and ESP32-C6 decisions. Review the formulas and approved circuit
  configuration first; preserve the current `peak_data.json` until its
  replacement values are engineering-reviewed.
  Audit completed 2026-11-23; reconciliation is blocked pending approved
  circuit evidence and engineering-reviewed load assumptions. See
  `DOCS/reviews/POWER_CALCULATION_RECONCILIATION_2026-11-23.md`.
- [x] Build and smoke-test the local `jlcparts-mcp` database. Record the source
  revision and data timestamp, and verify offline search/BOM checks before
  relying on the results. See
  `DOCS/reviews/JLCPARTS_MCP_SMOKE_TEST_2026-11-23.md`; the current HLK/ESP32
  BOM part numbers are absent from this mirror, so it is not yet a source for
  validating those selections.
- [x] Add catalog-data provenance and integrity checks, including explicit
  reporting of incomplete shard downloads and a non-destructive refresh path.
  `.agents/mcp/catalog_maintenance.py` stages and validates refreshes, records
  shard sequence/hash/provenance, and retains a backup. Independent upstream
  shard checksums remain unavailable.
- [ ] Validate single-bridge ownership before exposing the standalone
  `EMC/tools/export_easyeda_board.mjs` as a workspace MCP server. Package
  resolution now uses Node resolution or `EASYEDA_MCP_PRO_PACKAGE_ROOT` and
  enforces the pinned version; exposure is blocked while EasyEDA health is
  degraded (`bridge_connected=false`).
- [x] Extend `inv path-integrity` and CI with exact-case checks for tracked
  workspace paths. Existing `Path.is_file()` checks only verify existence and
  are case-insensitive on Windows; a Linux CI run would catch casing errors
  that local Windows runs miss. The checker now scans tracked paths and key
  task/config/documentation references.
- [x] Move the legacy Altium project from `ECAD/Smart_Plugs` into
  `PCB/_archive` after checking external CAD links and automation references.
  The full 1,141-file tree was preserved; 17 tracked files were moved with Git,
  and workspace task/document references were updated. The already-broken
  absolute `PCB_DESIGN/Smart_Plugs` output paths remain documented.
- [x] Evaluate a vetted openEMS/ngspice MCP adapter if model interaction needs
  MCP support; current workflows are local scripts and Invoke tasks, so no
  adapter is being added until an interactive model task requires one.
- [ ] Validate MCP component recommendations against current board data,
  manufacturer datasheets, and applicable engineering requirements; catalog
  availability is not evidence of electrical suitability or safety. No
  recommendation was accepted: the exact current BOM identifiers are absent
  from the local mirror and live board identity is unavailable.
