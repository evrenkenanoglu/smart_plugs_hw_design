# Stage 0 — Revision lock record

**Status:** BLOCKED — a connected live MAIN_OMRON trial produced a partial
Gerber/drill, PnP, PCB-netlist, and layer report bundle, but the matched live
BOM and schematic PDF are missing, and the live project ID is not included in
the project-list entries. The designer has since provided nominal MAIN_OMRON
stackup and NPTH intent; fabrication and archive linkage remain unverified. The
partial live exports are not matched to the saved `.eprj2` revision. Do not use
this record to authorize a project-specific simulation.

## Designer-provided MAIN_OMRON information — 2026-11-21

- The designer formally confirms the Nov 21 candidate Gerber/netlist/PnP
  exports, Nov 19 MAIN_OMRON BOM and Nov 21 `.epro2` as the intended matched
  baseline. This is recorded as a designer assertion; the native archive to
  live-PCB linkage, a complete matched schematic, and full BOM values and
  connectivity still require independent evidence. The current candidate
  folder has no stackup JSON; an earlier partial live layer report exists
  separately and does not specify finished stackup. Do not mix the files as a
  verified revision or set the manifest lock merely from reference parity.
- The designer authorizes 1 A slow-blow as a hypothetical branch-fuse model.
  The actually fitted fuse and protection coordination remain unknown.
- A fresh automated BOM/PnP comparison finds 45 distinct references in
  each and no placement-reference duplicates; BOM references J1, J2 and J3
  have no manufacturer part number. Eight BOM MPN/device-name string
  differences correspond to apparent EasyEDA catalog suffixes, but were not
  independently verified as equivalent. Reference parity alone does not
  establish that all component attributes or the archive revision match.
- The designer authorizes `MAIN_OMRON` as the intended analysis baseline.
  Authorization does not by itself establish that the Nov 21 archive and all
  design exports are the same revision; keep `locked: false` until source
  linkage, matched BOM/netlist and applicable modeling inputs are verified.
- The designer states finished board thickness/material 1.6 mm FR-4, outer
  copper 1 oz, and zero NPTH is intentional: J2 is an unconnected plated screw
  mounting hole. These are designer inputs, not a fabricator stackup, finished
  copper/plating measurement, or an isolation/clearance finding. UI stackup
  was not reconfirmed in this update.
- The designer identifies RV1 as 14D431K, with `440pF` an EasyEDA parasitic
  capacitance label; the live focused schematic reports those same manufacturer
  ID and value fields. Datasheet, fitted part, and MOV protection coordination
  remain to be verified.
- The designer describes FH1 as a PTF-77, 250 V/20 A holder. A holder is not
  the fuse element; installed fuse MPN, rating, breaking capacity and the
  circuits it protects remain unresolved.
- On the currently focused live `PSU_Input_EMI_Protection` child sheet,
  active project ID `887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255`,
  read-only schematic net inspection reports `AC_L_IN` to FH1.1, FH1.2 to
  R6.1, R6.2 to L1.1/C2.1/RV1.2, and L1.2 / L1.3 on
  `AC_L_FILTERED_OUT` / `AC_N_FILTERED_OUT` respectively. The scope is that
  child sheet only; its output net-detail reads list only those local L1 pins.
  The Nov 19 candidate PCB netlist places L1.2 / L1.3 at U1.1 / U1.2 and relay
  contact pins at separate `FT_IN` / `FT_OUT` connector nets, but cannot prove
  the external outlet wiring or correspondence to the Nov 21 archive.
- The read-only full-page schematic capture returned `captured: false` because
  runtime sheet geometry was unavailable. The tool's inferred A4 option is
  diagnostic only and was not used. No schematic capture was generated.
- The exporter now accepts `--allow-unlisted-active-project` for candidate
  exports only; it retains focused-board, parent-project, component-signature
  and context-drift checks and never updates the shared manifest when this
  override is used. Node tests pass on mocked responses. Native focused-PCB
  field compatibility and a live export remain unverified; the current focus
  is the schematic child page, not the PCB.
- At 230 V, 4,000 W / 230 V = 17.39 A for a unity-power-factor resistive load;
  16 A x 230 V = 3,680 W. Whether R6 or L1 carries outlet current, actual
  mains-path trace widths/heating, and J2 screw-to-mains copper clearances are
  not established. Do not energize or assume a 16 A/4 kW rating is supported.

## Live candidate PCB export — 2026-11-21 17:55

- The bridge was connected; the native focused PCB UUID was
  `e05c8329c9f84495a1131d747d50aaf9`, parent project
  `887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255`.
  The focus response did not supply a board name. The PCB netlist header says
  `MAIN_OMRON : PCB_MAIN_OMRON` and the component signature is consistent
  with MAIN_OMRON. Exact linkage to the Nov 21 archive is not established.
- Direct live MCP calls, rather than a second competing MCP server, produced
  a Gerber ZIP, PCB PADS netlist and PnP CSV under
  `inputs/locked_rev/MAIN_OMRON/MCP_CANDIDATE_20261121_1753/`. The focused-PCB
  BOM export returned `not_available`; no BOM or schematic capture was
  generated. SHA-256 values and plot limitations are recorded in that
  folder's `candidate_evidence.json`. The export script has not been run
  end-to-end: it requires a native focused-document name which this live
  response does not provide.
- The new and Nov 19 live candidate ZIPs pass CRC checks. Their imported top
  and bottom copper geometries have zero symmetric-difference area and compare
  equal at the importer's polygonization tolerance. Both bottom imports
  required warned normalization of one self-touching region and removal of
  two zero-length edges. The PADS netlists differ only in their export-date
  remark; their 45 PnP CSV rows are equal ignoring order. This comparison does
  not establish that the native archive is the source, nor prove all
  manufacturing layers, connectivity, or fitted parts match.
- Candidate J2 and L1/U1 copper-only PNG overlays are in that folder. They
  have no drill or net information and use display-only z/thickness values;
  they do not establish screw, mains-to-metal, or primary-to-secondary
  clearance. The PCB API reports 16 relay-net pours across both layers; none
  of the 226 native line tracks is on the eight `$K1_4`/`$K1_6` through
  `$K4_4`/`$K4_6` contact nets. Actual poured-copper necks, connectivity,
  plating, current paths and temperature rise remain unverified.

## Selected source of truth

- EasyEDA Pro project identity: `Smart_Plugs`, UUID
  `b0904c5e84060c537b3dc2b63eac7793f454a84d538ff657b90ce8a3616f8a5a`
- Selected boards: `MAIN_OMRON` and `UI`; no explicit board revision label
  found in the candidate export filenames or project metadata
- Candidate Gerber export date: 2026-11-19 (see per-board Gerber headers)
- Authoritative native project: not confirmed; the available `.eprj2` is only a
  candidate and its internal project `updated_at` is 2026-11-12
- Candidate `.eprj2` SHA-256:
  `3a8913444d4e201fae5bb706c050a8d4f8b01c31bd4b63a81cef301edf1c40f8`
- Candidate export hashes: recorded in
  `smart_power_strip\configs\revision_manifest.json`; manifest remains
  `locked: false`
- Enclosure revision and linkage: TODO — confirm if relevant
- Reviewer and lock date: TODO

## Recheck after reported additions — 2026-11-19

- The user designated the existing 2026-11-19 MAIN_OMRON and UI export sets as
  authoritative. The current `locked_rev` scan still finds only the existing
  placement PDFs (`PCB_PCB_MAIN_OMRON_2026-11-19.pdf` and
  `PCB_PCB_UI_2026-11-19.pdf`, duplicated in the board folders). Both are
  titled "Top Auto Designator Placement"; no schematic PDF is present.
- The staged `Smart_Plugs.eprj2` remains 6,787,072 bytes with SHA-256
  `3a8913444d4e201fae5bb706c050a8d4f8b01c31bd4b63a81cef301edf1c40f8`;
  it is byte-identical to the source project copy and its filesystem timestamp
  is 2026-11-12. No updated project archive was found in `locked_rev`.
- The provided stackup entries contain example placeholders rather than actual
  thickness/copper-weight values. The Gerber order notes link to generic
  ordering instructions and do not specify a fabrication stackup.
- UI includes an NPTH drill file. MAIN_OMRON has only PTH and via-PTH drill
  files; the absence of an NPTH file does not establish whether that is
  intentional or an incomplete export.
- Keep Stage 0 blocked. Do not substitute example stackup values or choose an
  NPTH intent on the designer's behalf.

## Initial live MCP recheck — 2026-11-19 (superseded by current trial below)

- Copilot CLI lists `easyeda-mcp-pro` as an enabled local server. Its v1.16.0
  doctor passes for Node.js 24.15.0, installed extension package, and local
  listener at `127.0.0.1:49620`; this does not prove that EasyEDA Pro is
  connected.
- The live `easyeda_health_check` returned `status: degraded` and
  `bridge_connected: false`. `easyeda_bridge_status` also returned
  `connected: false`; `easyeda_project_list` returned
  `native_listing_unavailable`, `complete: false`, and no projects.
- No live project inspection or export was attempted after these fail-closed
  results. The filesystem still contains no schematic PDF; the staged
  `.eprj2` remains the 2026-11-12 candidate. The existing placement PDFs are
  not schematic evidence.
- The local doctor directs the operator to reload the EasyEDA extension and
  click **MCP Bridge > Connect**, then repeat the health check. Keep this
  revision unlocked until live identity and matched exports are verified.

## Current candidate inventory (not revision linkage)

The workspace also contains older `.epro2` backups, a March 11, 2026 Gerber/BOM
release, and STEP exports from November 2026. The newly supplied `MAIN_OMRON`
and `UI` Gerbers identify EasyEDA Pro v3.2.209 exports from 2026-11-19. Their
BOM and pick-and-place designator sets agree. The MAIN_OMRON BOM/PnP include
`J2`, which is not referenced in the PCB netlist; confirm whether it is
intentionally unconnected. The available `.eprj2` was last updated
2026-11-12 and does not prove that the 2026-11-19 exports came from that exact
saved state. Do not treat matching names or dates alone as revision linkage.

## Current local inspection (candidate evidence only)

- The candidate source under inspection is
  `ECAD\Smart_Plugs_EasyEDA\Smart_Plugs.eprj2`, project name `Smart_Plugs`,
  database project UUID
  `b0904c5e84060c537b3dc2b63eac7793f454a84d538ff657b90ce8a3616f8a5a`.
- Its observed SHA-256 is
  `3a8913444d4e201fae5bb706c050a8d4f8b01c31bd4b63a81cef301edf1c40f8`.
  The copy at `smart_power_strip\inputs\locked_rev\Smart_Plugs.eprj2` was
  byte-identical when checked (6,787,072 bytes). This identifies the candidate
  file only; it does not lock a board revision.
- The project database maps four named boards: `MAIN_HF115F` to PCB UUID
  `764d0b1741e643339a50ff5138c70bca`, `UI` to
  `3c10960a1a3b4ca790d74624dc58be54`, `Combined` to
  `5b8560b388744704bd58641708760a63`, and `MAIN_OMRON` to
  `e05c8329c9f84495a1131d747d50aaf9`. A fifth PCB document,
  `pcb_combined_omron` (UUID `819591c4247e455ea945fac5ca6e11c8`), is not in
  that four-board mapping. The requested targets are `MAIN_OMRON` and `UI`;
  their project-database PCB UUIDs are recorded above, with schematic UUIDs
  `f13c3e10ddb04f9d9c29ca075913c7af` and
  `9c475721ddb74ff3aaf78e45842ae9cc`, respectively. The selected boards do not
  by themselves establish the live editor context or revision.
- A prior local check observed a listener at `127.0.0.1:8765` and a localhost
  TCP peer. That only confirmed a socket, not protocol compatibility or active
  document context; `easyeda_doctor` is not exposed to this assistant session.
- `locked_rev\MAIN_OMRON\` and `locked_rev\UI\` now contain organized copies of
  each board's BOM, pick-and-place, PCB-placement PDF, PCB netlist, and extracted
  Gerber/drill archive. The original ZIPs, root-level exports, and original
  extracted folders were retained.
- The PDFs named `PCB_PCB_MAIN_OMRON_2026-11-19.pdf` and
  `PCB_PCB_UI_2026-11-19.pdf` are titled "Top Auto Designator Placement"; they
  are PCB-placement PDFs, not schematic PDFs. Schematic PDFs are missing for
  both boards. The `.tel` files are PCB netlists, not exported schematics.
- The Gerber headers say dimensions are millimeters; the Excellon headers say
  `METRIC`. Each board has top and bottom copper Gerbers. The UI archive
  includes PTH, via-PTH, and NPTH drill files; the MAIN_OMRON archive has PTH
  and via-PTH files but no NPTH file.
- BOM and pick-and-place references match: 45 for MAIN_OMRON and 39 for UI.
  The MAIN_OMRON PCB netlist has 44 references and omits `J2`; the BOM has no
  manufacturer part number for `J1`, `J2`, or `J3`. Resolve these before
  treating the package as complete.
- The raw CAD `LAYER_PHYS` records contain values such as FR4 `59.449` and
  copper `1.379`/`1.378`, but their units and relationship to a fabricator
  stackup are unverified. Finished board thickness and copper weight therefore
  remain unknown; do not convert these values or populate a verified stackup.
- The manifest now hashes the staged candidate files but intentionally remains
  unlocked. The stackup/layer-map and conducted-filter configurations remain
  unverified.

## Historical exploratory coupon (not authoritative revision lock)

The previous exploratory coupon read
`ECAD\Smart_Plugs_EasyEDA\Smart_Plugs_backup\Smart_Plugs_2026-11-15-00-26.epro2`,
PCB document UUID `819591c4247e455ea945fac5ca6e11c8`, source SHA-256
`79a9632bd2eb1424217e0b6a11a2c2f328e8fec889fd9704b46c120066944ede`.
These identify the file used by that run only; they do not establish that it is
the current/authoritative PCB or that other exports match it.

## Pilot-region identity

- In the unlisted `pcb_combined_omron` candidate document, component record
  `e1385` is designator `L1` in reuse block
  `PSU_Input_EMI_Protection_Block`. It is not the L1 component record in the
  mapped `Combined` or `MAIN_OMRON` boards.
- In `pcb_combined_omron`, `$L1_3` connects L1 pad 3 (`e1385`) to U1 pad 2
  (`e1390`). In the mapped `Combined` board, the corresponding endpoint is
  L1 pad 3 (`e779`) to U1 pad 2 (`e784`). The circuit function is not proven by
  the net name alone. On the requested `MAIN_OMRON` PCB, `$L1_3` is L1 pad 3
  (`e15`) to U1 pad 2 (`e18`).
- Route records: `e1163`, `e1169`, `e1171` — historical archive only
- In the saved candidate `MAIN_OMRON` PCB database, `$L1_3` is on the top
  copper layer. Its raw stored coordinate bounds (units not established; x
  `797.5..1548.3`, y `-3932.3..-3759.5`) do not overlap the candidate's sole
  recorded GND pour, and no bottom-layer GND pour is recorded there. This is
  candidate-archive evidence only and conflicts with the later live API result
  below, which reports a bottom-layer GND pour. The saved candidate Gerbers
  were not correlated to either fill representation; local GND coverage
  remains unresolved. Neither result establishes a PE path.

## MAIN_OMRON supply and EMI parts (candidate BOM and PCB netlist)

The candidate MAIN_OMRON BOM for PCB document `pcb_main_omron` (UUID
`e05c8329c9f84495a1131d747d50aaf9`) lists these manufacturer parts:

| Ref. | BOM-listed part / MPN | Supplier part | Candidate role or value |
|---|---|---|---|
| U1 | HI-LINK `HLK-5LS05` | `C48935101` | BOM identifies the packaged 5 W / 5 V AC/DC module; its internal converter IC, transformer, and switching waveform are not exposed |
| L1 | FH `UU9.8-10mH` | `C148474` | 4-pin, 10 mH input choke per BOM; verify winding/common-mode details from its datasheet |
| C2 | SRD `MP2104K27C3X6LC` | `C105759` | 100 nF BOM value; safety class/rating require datasheet confirmation |
| CY1 | HEL `Y16F1D222M` | `C332369` | 2.2 nF BOM value; connected from U1 pin 4 to `GND` in the PCB netlist; class and insulation function require datasheet/schematic confirmation |
| R6 | HEL `10D-7` | `C332360` | BOM-listed input NTC; netlist places it in series between fuse holder and the input rail |
| RV1 | R+O `14D431K` | `C49069732` | BOM value says `440pF`, while the MPN is associated with a varistor; resolve this field conflict and verify ratings |
| FH1 | XFCN `PTF-77` | `C717030` | 5 x 20 mm fuse holder; no fuse element/value/MPN appears in the BOM |
| L2 | TDK `SLF7055T-100M2R5-3PF` | `C92044` | 10 uH external output inductor per BOM |
| K1-K4 | OMRON `G5RL-1A-E-HR-DC5` | `C113250` | Four relay BOM entries; confirm ratings and contact/load application from the exact datasheet |
| NTC1 | R+O `HNTC0805-103F3950FB` | `C49247662` | Thermistor connected to the CN1 pin-4 sensor-divider net |

The exported PCB netlist shows P1 pin 2 through FH1 and R6 to `C2_1`, P1 pin 3
on `C2_2`, C2 and RV1 across those rails, and L1 between those rails and U1
pins 1/2. This is PCB connectivity only; the matching schematic PDF is absent.
The BOM also lists C1 as 100 nF and C4 as 10 uF. This conflicts with
`docs\design_notes\POWER_SUPPLY\HLK_5LS05_AC_TO_DC_CONVERSION_AND_FILTER_DESIGN.md`, which calls C1 a 10 uF / 450 V primary-bulk
capacitor and describes a different L1/output-filter arrangement. Do not use
that note as a schematic or component source of truth.

The distributor product listing for HI-LINK `HLK-5LS05` reports 3000 V RMS
input/output isolation withstand voltage:
https://www.lcsc.com/product-detail/AC-DC-Converter-Modules_HI-LINK-HLK-5LS05_C48935101.html
This supports describing the module as specified to be isolated, but is not
verification of the fitted module's authenticity, board-level creepage/
clearance, leakage/touch current, or product safety. The exact manufacturer
datasheet and the board's insulation design still require qualified review.
The UI BOM/netlist identifies U1 as `AMS1117-3.3` between `+5V` and `+3V3`;
this regulator is non-isolating, so its output inherits whatever isolation the
5 V source actually provides.

## Live MAIN_OMRON trial after Connect Local MCP — 2026-11-19 (partial)

- `easyeda_health_check` now returns `status: ok`, `bridge_connected: true`,
  EasyEDA Pro 3.2.209, and extension 1.16.0. This supersedes the earlier
  disconnected check above.
- `easyeda_project_list` returns `complete: true` and
  `activeProjectId=887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255`,
  but that ID is absent from its `projects` array. The all-pages schematic
  metadata for that ID identifies `Smart_Plugs` and page
  `MAIN_ONLY_CTRL_OMRON` (`MAIN_OMRON`, page UUID
  `4bacbdc86c1b4b5f8ad910dfac69425e`, parent schematic UUID
  `f13c3e10ddb04f9d9c29ca075913c7af`). The focused document is PCB UUID
  `e05c8329c9f84495a1131d747d50aaf9`. These establish a useful live
  cross-check but do not explain why the active ID is missing from the
  project list or link this session to the saved `.eprj2` internal project ID
  `b0904c5e84060c537b3dc2b63eac7793f454a84d538ff657b90ce8a3616f8a5a`.
- Read-only exports staged under `MAIN_OMRON\`:
  - `MCP_LIVE_20261119_203444_Gerbers.zip` — Gerber/Excellon archive; top and
    bottom copper, board outline, two PTH drill files, no NPTH file. SHA-256:
    `F609426D56A38FDAFFB01FDB8BEDA3177643C3AF92D0721BA8B6AE38AA2F1274`.
  - `MCP_LIVE_20261119_203444_PnP.csv` — 45 references; coordinates explicitly
    use `mm`. SHA-256:
    `1EC9252B3C840F36DC7CB4203E4759794A0D89FA07D88A25420BC3F33476CBFE`.
  - `MCP_LIVE_20261119_203444_Netlist.pads` — PADS file header identifies
    `MAIN_OMRON : PCB_MAIN_OMRON`; it is PCB connectivity, not a schematic
    netlist. SHA-256:
    `42E8ADD9EA3A6D6C6A0003C8527DAF9A0CC83A31E23B3F6A6CAA94CE8F549E50`.
  - `MCP_LIVE_20261119_203444_LayerStackup.json` — live layer, drill, and
    stackup availability record. SHA-256:
    `8E3D2B454579EDC8A1C0FE14D70F1AB113C63086310EA1234DD9AD16A89D14B4`.
- The BOM export and generation returned zero entries; no live BOM CSV was
  produced. Schematic PDF export timed out; no schematic PDF was produced.
  Schematic component reads returned `wrong-focused-document-type` because
  the PCB was focused. The all-pages sheet list supplies metadata only, not
  schematic pin/net connectivity.
- The live board reports 27 design layers, with two signal copper layers:
  top (`layer_id=1`) and bottom (`layer_id=2`). Physical stackup is unavailable.
  Board outline is 204.978 x 51.054 mm. The drill inventory reports 86 plated
  drill pads, zero unplated drill pads, minimum 0.3048 mm, and unknown
  mounting-hole classification. No NPTH file was exported; intent is unknown.
- Live PCB PADS connectivity maps `$L1_3` from L1 pad 3 (`e15`) to U1 pad 2
  (`e18`). `CN1.4` is on `$C1_1` with C1.1, R1.1, and NTC1.2. J2 appears in
  `*PART*` but has no net assignment. PnP identifies C1 as 100 nF, C4 as
  10 uF, FH1 as `PTF-77`, and RV1 device `14D431K_C49069732` with value
  `440pF`; resolve the RV1 value/part conflict. `e1385` is not the L1 primitive
  on this live MAIN_OMRON board; it belongs to a different historical PCB.
- A GND pour is reported on bottom layer 2 with 19 fill records. The live
  canvas crop was captured, but its image content was not available for visual
  review. The pour API does not expose its polygon, so exact local GND coverage
  remains unverified. A local Gerber polygonization attempt failed closed on a
  degenerate `ArcPoly`; no geometry repair or coverage claim was made.
- The manifest was not changed and remains `locked: false`: current live
  artifacts lack BOM and schematic PDF, and their live project identity has
  not been reconciled with the saved source revision. Do not simulate from
  this partial package.

## UI control-board parts (candidate BOM)

| Ref. | BOM-listed part / MPN | Supplier part | Candidate role |
|---|---|---|---|
| U1 | AMS `AMS1117-3.3` | `C6186` | 3.3 V regulator; netlist connects its input to `+5V` and output to `+3V3` |
| U2 | Espressif `ESP32-C6-WROOM-1-N8` | `C5366877` | Wireless MCU module; exact antenna implementation and keep-out still require datasheet/layout review |

These are BOM attributes, not confirmation of the fitted parts or antenna
variant. The current evidence does not expose the HLK module's internal
switching controller/transformer or a validated switching waveform.

## MAIN_OMRON and UI interface (candidate PCB pad-net records)

Both project-listed boards use CN1 with the same EasyEDA device/footprint
metadata (`XH-12A`, supplier part `C8880`, 12 pins). The corresponding pad-net
records are:

| CN1 pin | `MAIN_OMRON` net | `UI` net |
|---:|---|---|
| 1 | `+5V` | `+5V` |
| 2 | `GND` | `GND` |
| 3 | `+3V3` | `+3V3` |
| 4 | `$C1_1` | `$CN1_4` |
| 5 | `$CN1_5` | `$CN1_5` |
| 6 | `$CN1_6` | `DRV_SIG1` |
| 7 | `$CN1_7` | `$CN1_7` |
| 8 | `$CN1_8` | `DRV_SIG2` |
| 9 | `$CN1_9` | `$CN1_9` |
| 10 | `$CN1_10` | `DRV_SIG3` |
| 11 | `$CN1_11` | `$CN1_11` |
| 12 | `$CN1_12` | `DRV_SIG4` |

The exported PCB netlists confirm the same pin-number mapping shown above.
Pin 4 is not, by itself, evidence of a wiring error: on MAIN_OMRON it is the
`NTC1`/R1/C1 sensor-divider node; on UI it connects to ESP32 module U2 pin 8.
That is a plausible thermistor-sense path, but the missing schematic and
unverified connector mating orientation prevent confirming intent. Pins 6/8/
10/12 are UI-side `DRV_SIG1..4` outputs; pins 5/7/9/11 connect to the
corresponding MAIN_OMRON relay-driver nodes.

CN1 shares `GND`, `+5V`, and `+3V3`; therefore the boards are not galvanically
isolated from each other through CN1. The netlists show the MAIN_OMRON module
providing `+5V`, while the UI board's AMS1117-3.3 provides `+3V3` back through
CN1. `GND` is not protective earth. MAIN_OMRON P1 pin 1 shares `$J1_1` with J1
and J3; its PE role is not confirmed. Do not infer touch-safety from the module
catalog isolation rating or these net names.

## Layer/stackup evidence status

The candidate Gerber archives contain `Gerber_TopLayer.GTL` and
`Gerber_BottomLayer.GBL` for both boards; Excellon headers specify metric
coordinates. These establish two exported copper layers per board, not the
finished board thickness, copper weight/plating, laminate, or dielectric
properties. The raw `LAYER_PHYS` values are not a substitute for a
fabricator-confirmed stackup. Keep stackup/layer-map configs unverified until
the exact export revision and fabrication stackup/drill spans are confirmed.

## Candidate input inventory and revision status

| Artifact | Relative path under `inputs/locked_rev/` | Candidate state | Revision match confirmed? |
|---|---|---|---|
| Native EasyEDA Pro project | `Smart_Plugs.eprj2` | SHA-256 recorded in manifest | No — project updated 2026-11-12; board revision not identified |
| MAIN_OMRON schematic PDF | Missing | PCB placement PDF is not a schematic | No |
| UI schematic PDF | Missing | PCB placement PDF is not a schematic | No |
| PCB netlists | `MAIN_OMRON\Netlist.tel`, `UI\Netlist.tel` | Candidate PCB netlists hashed | No — no matched schematic export |
| BOM with MPNs | `MAIN_OMRON\BOM.csv`, `UI\BOM.csv` | Candidate BOMs hashed; MAIN_OMRON J1/J2/J3 MPNs blank | No |
| Copper Gerbers / outline | `MAIN_OMRON\gerbers\`, `UI\gerbers\` | Candidate two-layer sets hashed | No — export date is later than candidate project update |
| PTH/NPTH drills | Board `gerbers\` folders | Candidate Excellon files hashed; MAIN_OMRON has no NPTH file | No |
| Pick-and-place | Board `PickAndPlace.csv` | Candidate CSVs hashed; mm coordinates | No |
| Fabricator stackup | Missing | No finished thickness/copper weights verified | No |
| Enclosure model (if required) | Not staged with this package | Unknown | No |

## Gate

Only mark the lock complete after all project-specific inputs required by the
selected question are traceable to one source revision, the missing schematic
PDFs and MAIN_OMRON BOM/netlist discrepancies are resolved, required stackup
evidence is obtained, and hashes are verified in
`smart_power_strip\configs\revision_manifest.json`. The current manifest
contains candidate-file hashes but remains unlocked. Missing values remain
unknown; do not silently substitute dates or assumptions.

## Nov 21 archive and MCP preflight — 2026-11-21

- `ProPrj_Smart_Plugs_2026-11-21.epro2` is a readable ZIP archive (34 members,
  CRC check passed, no ZIP-encrypted entries), SHA-256
  `1f57d59b3db1ab6c725c8940be11e027f7e76ec09d3c4824c9b711a509ed4246`.
  It contains `project2.json`, `Smart_Plugs.epru`, and image assets; it has no
  standalone `.esch` file or schematic PDF. The serialized `.epru` includes
  `SCH` and `BOARD` records, but this is not a matched schematic export and has
  not been used to infer schematic connectivity.
- The archive's board/document records contain identifiers
  `d523abc1784d8ae6` and `d59928703b7503d1`; the associated board update time
  reported in its metadata is 2026-11-12, despite the archive filename/date.
  The prior live MAIN_OMRON focus was PCB UUID
  `e05c8329c9f84495a1131d747d50aaf9`. The archive and live export identities
  have not been reconciled.
- Current `easyeda_health_check` still reports bridge connected, but the
  complete project listing omits active ID
  `887b44b44d5f8223bb08fd9db9aeef7f7255beccd56f645b2117cc3651d8d255` and
  contains no `Smart_Plugs` project entry. No new MCP export was attempted
  from this ambiguous context.
- The Nov 21 additions are a PCB drawing PDF and PNG, not a schematic. The PDF
  SHA-256 is
  `079150a1be71e5f69d09aa68bac89ac8929116bb7bf0ba3e107f40e22551913d`;
  the Nov 19 PCB drawing PDF has SHA-256
  `27a77493662992c0e1eda5360a3fb54bad8a188dacb1efffe7f2238e2e16fde5`.
  Their differing hashes establish that the PDFs are not byte-identical; they
  do not prove a copper or component change. No matched Nov 21 Gerbers/drill,
  BOM, PnP, netlist, stackup, or schematic PDF are present.
- Those Nov 21 files and a candidate-only Nov 19 L1/U1 copper crop plus
  provenance JSON are now hashed in `revision_manifest.json`. The manifest's
  project ID and revision remain unconfirmed, and `locked` remains `false`.
- The Nov 19 top/bottom Gerbers now import as valid 2D geometry after explicit
  self-touching-region normalization and removal of exact zero-length outline
  edges. The crop is saved as
  `inputs/locked_rev/MAIN_OMRON/Candidate_CopperCrop_2026-11-19_L1_U1.png`.
  It marks component centers only. These Gerbers have no net attributes, so
  the crop does not identify the `$L1_3` route or prove GND coverage beneath
  it; it is not linked to the Nov 21 archive and is not an EM simulation.
- The automated exporter is implemented at
  `EMC/tools/export_easyeda_board.mjs`. Syntax/help and invalid-argument paths
  were checked; no live export was run because the active-project listing gate
  currently fails. It refuses to overwrite an existing output folder and
  never sets `locked: true`.
- No product-specific conducted or 3D simulation was run. The conducted sweep
  remains gated by the unlocked manifest and placeholder configuration;
  `03_local_pcb_em_extract.py` currently produces a 2D geometry overlay, not
  an openEMS 3D extraction, so mesh convergence, passivity, and component
  co-simulation have no results.

## Current answer to the Nov 19 vs. Nov 21 change question

**Not verifiable from the available files; re-export fresh from the exact Nov
21 project through MCP.** The current evidence cannot establish whether PCB
copper or parts changed. Do not treat different PCB drawing PDFs as a
revision-matched Gerber/BOM/PnP comparison.
