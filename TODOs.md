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
- [ ] Add catalog-data provenance and integrity checks, including explicit
  reporting of incomplete shard downloads and a non-destructive refresh path.
- [ ] Make `EMC/tools/export_easyeda_board.mjs` resolve the EasyEDA package
  portably, then validate single-bridge ownership before exposing it as a
  workspace MCP server.
- [ ] Extend `inv path-integrity` or CI with exact-case checks for tracked
  workspace paths. Existing `Path.is_file()` checks only verify existence and
  are case-insensitive on Windows; a Linux CI run would catch casing errors
  that local Windows runs miss.
- [ ] Move the legacy Altium project from `ECAD/Smart_Plugs` into
  `PCB/_archive` only after external CAD links and automation references are
  verified.
- [ ] Evaluate a vetted openEMS/ngspice MCP adapter if model interaction needs
  MCP support; these workflows currently use local scripts and Invoke tasks.
- [ ] Validate MCP component recommendations against current board data,
  manufacturer datasheets, and applicable engineering requirements; catalog
  availability is not evidence of electrical suitability or safety.
