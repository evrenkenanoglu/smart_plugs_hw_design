# Follow-up improvements

These are additional tasks beyond the current folder and MCP setup.

- [ ] Reconcile the power-calculation inputs and reports with the current
  HLK-5LS05 and ESP32-C6 decisions. Review the formulas and approved circuit
  configuration first; preserve the current `peak_data.json` until its
  replacement values are engineering-reviewed.
- [ ] Build and smoke-test the local `jlcparts-mcp` database. Record the source
  revision and data timestamp, and verify offline search/BOM checks before
  relying on the results.
- [ ] Add catalog-data provenance and integrity checks, including explicit
  reporting of incomplete shard downloads and a non-destructive refresh path.
- [ ] Make `EMC/tools/export_easyeda_board.mjs` resolve the EasyEDA package
  portably, then validate single-bridge ownership before exposing it as a
  workspace MCP server.
- [ ] Add case-sensitive path checks for workspace tasks, configuration, and
  documentation, and run them in CI on a case-sensitive filesystem.
- [ ] Move the legacy Altium project from `ECAD/Smart_Plugs` into
  `PCB/_archive` only after external CAD links and automation references are
  verified.
- [ ] Evaluate a vetted openEMS/ngspice MCP adapter if model interaction needs
  MCP support; these workflows currently use local scripts and Invoke tasks.
- [ ] Validate MCP component recommendations against current board data,
  manufacturer datasheets, and applicable engineering requirements; catalog
  availability is not evidence of electrical suitability or safety.
