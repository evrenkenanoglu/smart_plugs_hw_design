---
name: easyeda-pro-export
description: Inspect EasyEDA Pro projects and produce revision-matched Stage 0 exports without modifying CAD.
---

# EasyEDA Pro inspection and Stage 0 export

Use this workflow for read-only inspection, BOM/netlist verification, layer
review, or matched Gerber/drill/PDF/pick-and-place exports. These outputs are
design evidence, not proof of safety, compliance, or certification readiness.

## Pre-flight

1. Read `AGENTS.md`, `EMC/README.md`, `EMC/input-checklist.md`, and
   `EMC/risk-register.md`. Confirm the exact project, board, and revision before
   creating project-specific analysis inputs.
2. Verify the local `easyeda-mcp-pro` registration with `copilot mcp list`.
   The supported setup used here is package v1.16.0 with Node.js 24.x. The
   package `--doctor` check verifies the installed runtime and local bridge
   listener; it does not prove that EasyEDA Pro is connected.
3. Call `easyeda_health_check`. Continue only when
   `bridge_connected` is `true`. If it is false, stop without making
   project-scoped calls or exports. Enable the extension and
   **Allow interactive with external** in EasyEDA Pro, use
   **MCP Bridge > Connect Local MCP**, and repeat the health check.
4. Call `easyeda_project_list` and require a complete native listing that
   includes the `activeProjectId` as an active project entry. Record its
   name/UUID and active identity. Confirm the requested PCB board and
   schematic mapping from live project data before selecting a `projectId`;
   do not infer focus from a filename or from the project being open. If the
   active ID is absent from the returned project entries, record the
   inconsistency and do not revision-lock the exports.
5. Treat `.eprj2` and `.epro2` as different formats. Determine whether the
   selected project actually contains the required schematic and PCB documents;
   a project shell, missing companion data, or encrypted/unreadable archive is
   not a complete Stage 0 source.

## Read-only rules

- Do not edit schematic or PCB objects, update DRC rules, sync boards, move
  components, route tracks, or invoke confirmed mutation actions in an export
  workflow.
- Exports may write output files, but must not overwrite native projects,
  released manufacturing data, or existing user files. Use unique output names
  and inspect the tool's returned path.
- Check the active document identity before every export. Do not combine
  schematic, PCB, BOM, and fabrication outputs from different boards or
  revisions.
- Verify actual files on disk. A successful tool response is not enough.
- If document identity or tool connection cannot be verified, stop with the
  missing evidence; do not generate surrogate manufacturing files by parsing
  internal project data.

## Stage 0 procedure

1. Capture the exact active PCB UUID/name and project document list. Use
   `easyeda_board_layers`, `easyeda_board_stackup`, and
   `easyeda_board_dimensions`; use `easyeda_pcb_pours` and
   `easyeda_pcb_fills` to distinguish copper-pour boundaries from actual fill
   geometry. Layer configuration does not by itself establish board thickness,
   dielectric material, dielectric thickness, or copper weight.
2. Read schematic components, component pins, and nets using
   `easyeda_schematic_components`, `easyeda_schematic_component_pins`, and
   `easyeda_schematic_nets`. Verify requested pin mappings and component roles
   against the live schematic; use native PCB data for board connectivity.
3. Export the selected PCB BOM with `easyeda_bom_export` using
   `format: "csv"`. Verify designators, values, footprints, manufacturer part
   numbers, and component count against the selected board. Keep unknown MPNs
   unknown.
4. Export the netlist with `easyeda_export_netlist`. Inspect the file header
   and active document before labeling its source: the verified MAIN_OMRON
   trial returned a PADS file headed `MAIN_OMRON : PCB_MAIN_OMRON`, so it is
   PCB connectivity evidence, not a schematic netlist. Compare schematic
   connectivity with live PCB data when both are needed.
5. Export the schematic PDF with `easyeda_export_pdf` using
   `scope: "schematic"`. Open or inspect the resulting PDF and confirm that it
   contains the circuit diagram, not a PCB placement drawing.
6. Export Gerbers with `easyeda_export_gerbers`, using
   `drillFormat: "millimeter"` for the drill output. Inspect the returned
   archive and verify the actual Gerber units, copper/outline/mask layer set,
   Excellon files, drill units, and NPTH presence. Do not infer drill intent
   from a missing file.
7. Export Pick & Place with `easyeda_export_pick_place` using
   `format: "csv"`. The v1.16.0 tool schema has no unit selector; do not claim
   millimeter coordinates unless the output or export settings establish them.
8. Verify every artifact is non-empty and belongs to the same project and
   board. Check CSV headers and component counts; confirm PDF readability;
   inspect Gerber units and layer set; inspect Excellon units and drill tools;
   and confirm the Pick & Place coordinate unit. Preserve the tool response and
   export settings alongside the evidence.
9. Record layer order/configuration from the live board. Record
   fabricator-confirmed thickness, copper weight, and dielectric details
   separately; do not infer them from layer count or colors.
10. Compute SHA-256 hashes for the native source and every accepted export.
    Populate `smart_power_strip/configs/revision_manifest.json` with the exact
    project/board revision and relative paths. Set `locked: true` only after
    all required files are matched to the same board revision and the designer
    has confirmed that board as authoritative. Update
    `EMC/docs/STAGE0_REVISION_LOCK.md` with evidence and unresolved items.

## Verified MAIN_OMRON live trial — 2026-11-19

- The operator connected through **MCP Bridge > Connect Local MCP**. Health
  check returned `bridge_connected: true`, EasyEDA Pro 3.2.209, and extension
  1.16.0.
- `easyeda_project_list` reported `complete: true` and active ID
  `887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255`, but
  omitted that ID from its project entries. `easyeda_schematic_sheet_info`
  cross-checks the same active ID, names `Smart_Plugs`, and lists
  `MAIN_ONLY_CTRL_OMRON` (`MAIN_OMRON`, page UUID
  `4bacbdc86c1b4b5f8ad910dfac69425e`, parent schematic UUID
  `f13c3e10ddb04f9d9c29ca075913c7af`). The focused document is the
  MAIN_OMRON PCB (`e05c8329c9f84495a1131d747d50aaf9`). Keep the project-list
  mismatch visible and Stage 0 unlocked.
- Live files staged under
  `EMC/smart_power_strip/inputs/locked_rev/MAIN_OMRON/`:
  Gerber/Excellon ZIP, 45-reference PnP CSV with `mm` coordinates, PCB PADS
  netlist, and `MCP_LIVE_20261119_203444_LayerStackup.json`. The ZIP contains
  top/bottom copper and two PTH drill files, but no NPTH drill file.
- `easyeda_board_stackup` verified two copper layers only. Finished thickness,
  copper weight, dielectric data, and NPTH intent remain unknown. Board
  dimensions are 204.978 x 51.054 mm; the live drill inventory reports 86
  plated and zero unplated drill pads, with mounting-hole classification
  unknown.
- With the PCB focused, BOM export and BOM generation returned zero entries;
  no live BOM CSV was staged. Schematic PDF export timed out, and schematic
  component reads returned `wrong-focused-document-type`. The all-pages sheet
  metadata is not schematic connectivity evidence; do not substitute the PCB
  placement PDF or PADS PCB netlist.
- Live PCB PADS data maps `$L1_3` from L1 pad 3 (`e15`) to U1 pad 2 (`e18`).
  `CN1.4` is on `$C1_1` with C1.1, R1.1, and NTC1.2. J2 is present in the
  component list but absent from all net assignments. PnP metadata lists C1
  as 100 nF, C4 as 10 uF, FH1 as PTF-77, and RV1 device `14D431K_C49069732`
  with value/comment `440pF`; resolve the RV1 conflict. The `e1385` L1
  primitive belongs to a different historical PCB document, not this live
  MAIN_OMRON board.
- A live GND pour is reported on bottom layer 2 with 19 fill records. A canvas
  crop was captured but not visually reviewed; the tool does not expose the
  pour polygon and an exact Gerber overlap was not verified. Do not claim a
  continuous return plane beneath the route.

## Nov 21 archive and exporter preflight — 2026-11-21

- `ProPrj_Smart_Plugs_2026-11-21.epro2` is a CRC-valid, unencrypted ZIP with
  `project2.json`, `Smart_Plugs.epru`, and image assets. It has no standalone
  `.esch` or schematic PDF; the serialized `.epru` includes `SCH` and `BOARD`
  records, which are not a substitute for matched schematic exports.
- The archive contains board/document identifiers
  `d523abc1784d8ae6` and `d59928703b7503d1`, with board metadata updated
  2026-11-12. Neither has been reconciled with the Nov 19 live focus UUID
  `e05c8329c9f84495a1131d747d50aaf9`.
- Current live health is connected, but the complete project list still omits
  active ID `887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255`
  and contains no `Smart_Plugs` entry. Therefore no fresh export was run and
  the Stage 0 manifest remains unlocked.
- The new `EMC/tools/export_easyeda_board.mjs` supports
  `node EMC\tools\export_easyeda_board.mjs --board MAIN_OMRON` or `--board UI`.
  It starts a local stdio MCP server, requires a complete active-project
  listing and matching focused PCB identity/component signature, and
  rechecks project and focus immediately before each export. It writes into a
  unique, non-overwriting folder under the board's `locked_rev` directory,
  records per-file SHA-256 values in `export_manifest.json`, and never sets
  `locked: true`. It updates the shared revision manifest only when the full
  export set succeeds and the project ID and revision already match; otherwise
  candidate hashes stay in the run manifest.
- The script was checked with Node syntax/help and invalid-argument tests. It
  has not been exercised against EasyEDA because the active-ID listing gate
  currently fails. Potential competing MCP bridge ownership is unverified;
  avoid running a second local server alongside another connected
  `easyeda-mcp-pro` instance.
- A later `--allow-unlisted-active-project` option permits an explicitly
  selected candidate-only path when the complete listing omits the active ID.
  The normal default remains strict. The override requires exact native PCB
  name/type/UUID, parent project identity, and component signature, rechecks
  them for drift, never updates the shared revision manifest, and never
  authorizes a revision lock. Node unit tests use mocked responses; native
  focused-PCB field compatibility and end-to-end export remain unverified.
  Run it only when the intended PCB is focused and bridge ownership is resolved.
- A candidate-only crop,
  `EMC\smart_power_strip\inputs\locked_rev\MAIN_OMRON\Candidate_CopperCrop_2026-11-19_L1_U1.png`,
  was generated from the Nov 19 top/bottom Gerbers and PnP centers. The
  Gerbers have no net attributes, so the image does not identify the exact
  `$L1_3` route or prove GND coverage.
- `gerber_import.py` now explicitly normalizes self-touching G36/G37 fills with
  Shapely `make_valid(linework)` and removes exact zero-length outline edges,
  emitting a warning for either operation. The candidate top/bottom Gerbers
  import as valid 2D geometry; this does not establish revision linkage,
  electrical nets, or solver accuracy.
- No product-specific filter sweep or openEMS run was performed. The
  conducted workflow remains blocked by the unlocked manifest; the current
  `03_local_pcb_em_extract.py` creates a 2D overlay and is not a 3D openEMS
  extraction.
- On the subsequent 2026-11-21 recheck, the live focus was instead the
  `PSU_Input_EMI_Protection` schematic child page, not the PCB. Focused
  schematic net reads report the local FH1/R6/L1 filter connections and output
  labels, but not the downstream hierarchical destinations; the active
  project ID was still absent from the complete project listing. Do not mix
  these local schematic reads with Nov 19 PCB nets as a revision-matched
  whole-product connection or infer the external harness.
- The designer states MAIN_OMRON is 1.6 mm FR-4 with 1 oz outer copper and
  intentionally zero NPTH, with J2 an unconnected plated screw mounting hole.
  Record these as designer inputs; fabrication stackup, screw geometry and
  mains-to-metal clearance still require verification.

## Error registry

### Verified pitfalls

- **MCP registration and a passing package doctor do not prove an editor
  connection.** Require `easyeda_health_check.bridge_connected: true` and a
  complete active-project listing before project-scoped inspection or export.
  A degraded health result or `native_listing_unavailable` is a hard stop.
- **A project container can contain multiple or unlisted PCB documents.**
  Inspect live project board mappings and document UUIDs; do not equate opening
  the project with selecting its authoritative board.
- **Pick-and-place units are not selectable in the v1.16.0 tool schema.**
  Inspect the actual output or EasyEDA export settings; do not pass an invented
  `unit` argument or claim millimeters without evidence.
- **The Gerber export schema exposes drill format but not a general Gerber
  units selector.** Request millimeter drill output and independently inspect
  the exported files/settings.
- **A schematic netlist is not a PCB netlist.** `easyeda_export_netlist` is
  documented as exporting the schematic netlist, but the verified
  PCB-focused trial returned a PADS PCB netlist. Inspect the artifact header
  and label its source accurately.
- **The project listing may omit its own active ID.** In the 2026-11-19 trial,
  `complete: true` did not mean the active ID was present in `projects`.
  Cross-check document/page identities, record the discrepancy, and keep the
  revision unlocked until it is resolved.
- **Schematic page metadata does not imply schematic primitive access.** The
  all-pages sheet listing worked while the PCB was focused, but component reads
  still failed with `wrong-focused-document-type`. Do not infer circuit
  connectivity from title blocks or board netlists.
- **Full-page capture can lack sheet geometry even on a focused schematic.**
  On 2026-11-21 capture returned `captured: false` because runtime geometry
  was unavailable. Do not use the diagnostic-only inferred-A4 option to
  manufacture a claimed verified schematic capture.
- **A focused hierarchical child-sheet net read is not a complete project
  netlist.** On 2026-11-21 the focused filter child page returned only L1 pins
  for its filtered output labels. Trace parent-sheet connectivity and external
  wiring independently; absence of relay pins in that local response does not
  prove they bypass the filter.
- **A live PADS netlist may include unconnected parts only in `*PART*`.** J2
  appeared in that list but had no net assignment; inspect both sections and
  keep its design intent unresolved.
- **A GND pour record does not establish local coverage.** The API reported a
  bottom-layer GND pour with fills but no polygon geometry; a visual crop alone
  is not an exact Gerber overlap calculation.
- **Gerber exports can contain self-touching G36/G37 contours and exact
  zero-length arc-boundary edges.** The importer now explicitly normalizes the
  region linework and drops only zero-length outline edges, with runtime
  warnings; regression tests and the candidate MAIN_OMRON top/bottom import
  pass. Inspect the resulting geometry, preserve warnings, and do not infer
  electrical net coverage from un-attributed Gerbers.
- **BOM/PDF operations can fail despite a connected bridge.** In the same
  PCB-focused trial BOM export/generation returned zero entries and schematic
  PDF export timed out. Preserve these as missing evidence; do not synthesize
  a BOM or relabel a PCB placement drawing as a schematic.
- **The export service may restrict output paths to its artifact directory.**
  Export there, verify the returned file, then copy to the evidence folder
  using a unique name without overwriting existing files.
- **Layer configuration is not a fabrication stackup.** Do not infer
  laminate, copper weight, dielectric thickness, or board thickness from the
  layer list.
- **Unpoured or stale copper zones:** a zone definition is not proof of current
  filled copper. Check the fill state and verify exported copper data.
- **A path may be open in EasyEDA Pro while hashing is attempted.** If the
  platform's file-hash command cannot read it, use a streaming read-only hash
  and verify that the source remained unchanged; do not close or modify the
  user's project without permission.

### Assumptions to verify

- **Encrypted `.epro2` archives:** encryption may prevent inspection or export.
  Verify by opening the selected file in EasyEDA Pro; do not bypass encryption.
- **Windows paths:** quote paths with spaces and preserve backslashes through
  MCP arguments. Verify the actual output path returned by the tool.

## Reporting

Report the selected project and board IDs, file hashes, export settings,
verified artifacts, and unresolved fields. Separate measured, simulated,
calculated, and assumed evidence. Never claim that these exports or
simulations establish product safety, standards compliance, or certification
readiness.
