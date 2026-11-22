# Whole-board EMC and safety evidence checklist

This is a review aid, not a compliance determination. Use only files that are
matched to the revision recorded in `STAGE0_REVISION_LOCK.md`. Cite the source
file and page/section/board layer for each finding. A checklist item cannot be
closed by simulation alone when it requires applicable-standard review or
physical testing.

## Candidate export review — 2026-11-19 (not revision-locked)

The supplied Gerber archives, BOMs, PCB netlists, and pick-and-place files are
organized under `smart_power_strip\inputs\locked_rev\MAIN_OMRON\` and `UI\`.
The Gerber headers identify EasyEDA Pro v3.2.209 and millimeters; the
Excellon headers identify metric units. The supplied PDFs are PCB placement
drawings titled "Top Auto Designator Placement," not schematic PDFs. A
recheck after the reported additions found no schematic PDFs in `locked_rev`;
the staged `.eprj2` is still byte-identical to the source copy and dated
2026-11-12. The stackup values in the request are examples, not specifications,
and MAIN_OMRON's NPTH intent is unconfirmed. The link from that saved state to
the 2026-11-19 exports is not established, so findings below are preliminary
and open.

The board BOM and pick-and-place designator sets match (45 MAIN_OMRON
references and 39 UI references). The MAIN_OMRON PCB netlist contains 44
references and omits BOM/PnP reference J2; the MAIN_OMRON BOM also has no
manufacturer part number for J1/J2/J3. UI BOM/PnP/netlist references match.
Board-level connectivity does not replace a matched schematic for confirming
design intent.

A later live recheck followed the operator's **MCP Bridge > Connect Local MCP**
action. `easyeda_health_check` now reports `bridge_connected: true` for
EasyEDA Pro 3.2.209 and extension 1.16.0. The active project ID is missing
from the otherwise `complete: true` project-list entries; live sheet metadata
and PCB reads cross-check `Smart_Plugs` / `MAIN_OMRON`, but the mapping to the
saved project revision remains unresolved. A partial live bundle contains
Gerber/drill, PnP, PCB PADS netlist, and layer metadata only: BOM export
returned zero entries, schematic PDF export timed out, and physical stackup
and NPTH intent remain unknown. See `STAGE0_REVISION_LOCK.md`; no finding is
closed by this partial trial.

The Nov 21 `.epro2` archive is a readable, CRC-valid ZIP with `Smart_Plugs.epru`
and serialized schematic records, but no standalone `.esch` or schematic PDF.
Its board/document IDs and 2026-11-12 internal update time are not linked to the
Nov 19 live focus. The Nov 21 PDF/PNG are PCB drawings; differing PDF hashes
cannot establish copper or part changes. A candidate Nov 19 L1/U1 copper crop
was imported and visually reviewed, but the Gerbers have no net attributes and
the exact `$L1_3` route/GND overlap remains unverified. Keep all findings open.

## Designer inputs and current-path recheck — 2026-11-21

The designer specifies MAIN_OMRON as 1.6 mm FR-4 with 1 oz outer copper and
intentionally zero NPTH; J2 is an unconnected plated screw mounting hole.
These are designer statements, not measured/fabricator-confirmed geometry.
The designer identifies RV1 as 14D431K and `440pF` as the EasyEDA parasitic
capacitance label; the live schematic reports those same manufacturer and
value fields. The designer identifies FH1 as a 250 V/20 A PTF-77 holder, not
the fuse element. Its ratings and the fitted fuse still need datasheet and
assembly verification.

The live `PSU_Input_EMI_Protection` child sheet has FH1 then R6 on the
live-side input, followed by L1; output labels are
`AC_L_FILTERED_OUT` (L1.2) and `AC_N_FILTERED_OUT` (L1.3). The focused-sheet
net read does not show downstream hierarchical destinations. Separately, the
Nov 19 candidate PCB netlist puts L1.2/L1.3 at U1.1/U1.2 and relay contacts on
individual FT_IN/FT_OUT connector nets. This indicates distinct PCB nets, not
proof that external wiring bypasses FH1, R6, and L1; revision linkage and
complete assembly wiring remain unknown. User-stated R6 1 A and L1 0.5 A
limits are not yet independently verified. If outlet current passes through
these parts, those stated limits would be grossly exceeded.

On the later live PCB recheck, the API reports solid pours on both layers
for all eight relay-contact nets, while none of 226 native line segments
uses those net names. Consequently a line-track width is not an adequate
measurement of the outlet path; poured-copper necks, pad/thermal connections,
plating, external wiring and current sharing need separate verification.
Fresh candidate Gerbers, PCB netlist and PnP were staged in
`MAIN_OMRON/MCP_CANDIDATE_20261121_1753`; the live BOM export remained
unavailable. The two candidate copper overlays do not include drilled holes,
screws or net attribution and cannot establish creepage or clearance.

A read-only inspection of the Nov 21 candidate Excellon file locates J2 at
`X73.00984 Y-62.98999` mm with PTH tool `T08C3.20000` (3.2 mm). At that
location both copper Gerbers flash a 0.00254 mm aperture, not a conventional
annular copper pad. Verify the intended plated-hole and pad fabrication with
the board designer/fabricator; do not infer a 3.2 mm pad from the drill or a
valid clearance from the tiny flash. This is exported-artwork evidence, not a
measurement of the finished hole or screw.

## Conducted-noise paths and filter

- [ ] Trace the actual mains input, protection, filter, AC/DC module, relay,
  load, and PE connections from schematic and layout.
- [ ] Verify component values, MPNs, ratings, safety classes, and models against
  the BOM and manufacturer documents.
- [ ] Inspect input-to-output coupling paths around the actual filter,
  including adjacent copper, pours, slots, routing, and component geometry.
- [ ] Identify unknown converter/relay/load noise sources. Do not invent
  internal switching topology for a sealed module.
- [ ] Treat simulated filter response as model behavior, not conducted
  emissions or LISN receiver data.

## Switching and return paths

- [ ] Identify any switching hot loop and high-dv/dt node in verified circuit
  data; mark inaccessible sealed-module internals as unknown.
- [ ] Review loop geometry, high-frequency return paths, planes, splits, slots,
  vias, connector/board-edge transitions, and adjacent susceptible nets.
- [ ] Verify actual layer stack and copper; do not add a nominal plane where
  none is documented.
- [ ] Review relay coil suppression and switched-load transient paths against
  actual parts and datasheets.

## Radio and external structures (if present)

- [ ] Confirm exact radio module, antenna implementation, feed, operating
  modes, and vendor keep-out requirements.
- [ ] Review nearby copper, components, enclosure, and cables against the
  module/antenna guidance.
- [ ] Identify cable types, lengths, routing, terminations, enclosure, and PE
  only from evidence. Do not predict absolute radiated levels from arbitrary
  cable/source assumptions.

## Electrical safety and construction (qualified review required)

- [ ] Trace PE bonding and fault-current path from actual netlist, copper,
  hardware, terminals, and enclosure.
- [ ] Evaluate creepage/clearance using the applicable product standard and
  actual voltage, overvoltage, pollution, material, altitude, and insulation
  conditions.
- [ ] Reconcile fuse, MOV/surge protection, X/Y capacitors, discharge paths,
  module isolation, and component certification against actual BOM/data.
- [ ] Review connector, relay, copper, vias, solder joints, wiring, fuse, and
  enclosure thermal/current limits for intended operating and fault cases.
- [ ] Escalate all isolation, PE, fusing, surge, current-capacity, and thermal
  changes to a qualified reviewer.

## Record each finding

| ID | Priority (review aid) | Evidence | Why it matters | Next non-energized review / qualified action | Status |
|---|---|---|---|---|---|
| STAGE0-01 | Blocker | `STAGE0_REVISION_LOCK.md`; staged/source `.eprj2` hashes match and file timestamp is 2026-11-12; live schematic PDF export timed out | Cannot review schematic intent or attribute all artifacts conclusively to one revision | Obtain the matching schematic PDFs and saved project archive, then compare source/export identity before locking | Open |
| STAGE0-02 | Blocker | Health check now passes (`bridge_connected: true`); project listing says `complete: true` but omits its `activeProjectId`; live sheet metadata identifies `Smart_Plugs` / `MAIN_OMRON` and focused PCB UUID `e05c8329c9f84495a1131d747d50aaf9` | The live board can be read, but the project-list identity anomaly and mapping to the saved `.eprj2` revision remain unresolved | Resolve or document the active-ID/listing discrepancy; require a complete identity chain before revision locking | Open |
| STAGE0-03 | Blocker | Live MAIN_OMRON trial: Gerber/drill, PnP, and PCB PADS netlist staged; BOM export/generation returned zero entries; stackup and NPTH intent unavailable | The Stage 0 bundle is incomplete, so component sourcing, schematic cross-check, and fabrication assumptions are not revision-lockable | Obtain the live BOM, schematic PDF/netlist, fabricator stackup, and explicit NPTH intent; preserve the manifest as unlocked | Open |
| STAGE0-04 | Blocker | Nov 21 `.epro2` SHA-256 `1f57d59b3db1ab6c725c8940be11e027f7e76ec09d3c4824c9b711a509ed4246`; ZIP is valid but has no standalone `.esch`; archive board IDs/update time are not linked to the Nov 19 live focus; current active project ID remains absent from the complete project listing | The Nov 19 and Nov 21 datasets cannot be compared as one authoritative board revision; differing PCB PDF hashes do not establish copper/part changes | Open the exact Nov 21 archive in EasyEDA Pro, resolve active project/document identity, and export a complete matched Gerber/drill/BOM/PnP/netlist/stackup/schematic bundle before comparing | Open |
| IF-01 | High | Live MAIN_OMRON PCB PADS netlist: CN1.4=`$C1_1` with C1.1/R1.1/NTC1.2; candidate UI `Netlist.tel`: CN1.4=`$CN1_4` to U2.8 | Different local net names could represent a thermistor-sense connection, but the UI data is candidate-only and live schematic intent/orientation is unverified | Compare matched schematics and connector mating orientation; do not label it a wiring defect from net names alone | Open |
| IF-02 | High | Both board `Netlist.tel` files, CN1 pins 1–3 | Shared +5V, GND, +3V3 means no board-to-board galvanic isolation through CN1; module isolation does not prove system touch safety | Verify the exact module datasheet, isolation boundary, Y-capacitor connection, creepage/clearance, PE, and enclosure against the applicable product requirements with a qualified reviewer | Open |
| PSU-01 | High | Live PnP lists C1=100 nF, C4=10 uF, RV1 device `14D431K_C49069732` with value `440pF`, and FH1=`PTF-77`; designer explains 440 pF as RV1's parasitic capacitance label; candidate BOM/netlist and `docs\design_notes\POWER_SUPPLY\HLK_5LS05_AC_TO_DC_CONVERSION_AND_FILTER_DESIGN.md` | RV1 label intent is clarified but fitted part/rating need verification; the design note calls C1 a 10 uF/450 V primary-bulk part, unlike live PnP; FH1 is a holder, with no fuse element identified | Reconcile against the matched schematic, fitted BOM, and manufacturer datasheets; identify the fuse element, RV1 coordination, and CY1 class | Open |
| PSU-02 | High | MAIN_OMRON `Netlist.tel`: P1.2 to FH1 to R6 to C2_1; P1.3 to C2_2; C2/RV1 across rails; L1 feeds U1.1/U1.2 | This is candidate PCB topology only; internal HLK module switching/hot-loop details are unavailable | Verify schematic and component datasheets; treat the sealed HLK-5LS05 as a black box unless validated internal models/source data are obtained | Open |
| POWER-01 | Critical | Live focused `PSU_Input_EMI_Protection` net reads: FH1.1=`AC_L_IN`, FH1.2=R6.1, R6.2=L1.1/C2.1/RV1.2, L1.2=`AC_L_FILTERED_OUT`, L1.3=`AC_N_FILTERED_OUT`. Nov 19 candidate PCB PADS netlist connects L1.2/L1.3 to U1.1/U1.2 and each relay contact to separate FT_IN/FT_OUT connector nets. External harness and live/archive revision linkage are unknown. | Cannot establish whether the outlet feeds bypass the filter. If full outlet current passes through R6/L1, user-stated 1 A/0.5 A limits are exceeded at 16 A or 17.39 A. Holder rating does not establish fuse protection. | Reconcile matched hierarchical schematic, PCB and full external harness; verify part datasheets and fuse MPN/rating/coordination. Do not energize pending qualified review. | Open |
| POWER-02 | Critical | Designer states 1 oz outer copper and 4,000 W target; candidate Gerbers are unattributed and not matched to Nov 21 archive; actual external load routes, bottlenecks, current sharing, thermal boundaries and finished copper thickness are unverified. 4,000 W / 230 V = 17.39 A at unity power factor; 16 A x 230 V = 3,680 W. | No current-carrying or heating rating can be established from nominal copper weight alone; 17.39 A exceeds the stated 16 A Schuko limit. | Identify every actual load path including contacts, terminals, pads, vias, solder and wires; extract widths and perform qualified thermal and protection review, including laboratory tests. | Open |
| POWER-03 | High | Designer states J2 is a plated screw mounting hole without a net; candidate PnP places J2 at x=73.01 mm, y=-62.99 mm. The Nov 21 Excellon PTH file has a 3.2 mm tool at that position, while the top and bottom Gerbers each flash only 0.00254 mm there. Net-attributed matched copper, screw/head geometry, metalwork and required insulation classification are unavailable. | A plated hole or screw can be accessible conductive metal; the drill/flash discrepancy and no-net assignment do not establish finished construction, clearance, creepage, or bonding. | Resolve intended drill, plating and copper-pad construction with the designer/fabricator; measure the matched copper and full screw/head geometry on both surfaces and have a qualified reviewer determine applicable insulation and bonding. | Open |
| LAYOUT-01 | High | Live `easyeda_board_stackup` reports two copper layers; designer specifies 1.6 mm FR-4 and 1 oz outer copper for MAIN_OMRON | Fabricator confirmation, actual plated copper, dielectric properties and layer elevations are not established | Obtain fabrication stackup and drill spans; do not infer the remaining parameters from nominal thickness or raw CAD metadata | Open |
| LAYOUT-02 | High | Live PCB netlist maps `$L1_3` from L1 `e15` to U1 `e18`; `pcb_pours` reports bottom-layer GND fills, but not their polygon. The 2026-11-19 candidate Gerbers now import and have a crop at `MAIN_OMRON/Candidate_CopperCrop_2026-11-19_L1_U1.png`; net attributes are absent and these exports are not linked to the Nov 21 archive. `e1385` belongs to another historical PCB | The crop shows layer geometry/component centers only; it cannot assign GND to the local polygons or establish continuous return coverage beneath the exact route | Correlate a revision-matched route and copper geometry; do not claim GND beneath `$L1_3` or treat signal GND as PE | Open |
| RF-01 | Medium | UI `BOM.csv` and `PickAndPlace.csv`: U2=`ESP32-C6-WROOM-1-N8`, bottom side | Antenna keep-out and nearby-copper compliance have not been checked against the exact module datasheet and copper artwork | Review the official module antenna guidance against the matched Gerbers and enclosure; verify the module/antenna variant | Open |
| SAFE-01 | High | No matched enclosure, fabricator stackup, confirmed market/product category, or applicable-standard determination in this package | Creepage/clearance, accessible parts, touch current, and enclosure/PE protection cannot be determined | Establish the product configuration and have a qualified reviewer apply the relevant product requirements; energized safety/EMC tests belong in a qualified lab | Open |
| NET-01 | Medium | Live PADS netlist lists J2 under `*PART*` with no net; designer says J2 is an intentional unconnected plated screw hole | Designer intent is known; revision-matched geometry, installed hardware, spacing and bonding remain unverified | Review hole and hardware against matched PCB and assembly; see POWER-03 | Open |
| DRILL-01 | High | Live MAIN_OMRON export has two PTH drill files and no NPTH file; native inventory reports 86 plated and 0 unplated pads. Designer confirms zero NPTH is intentional. | Intent is documented, but manufacturing and mounting-hole details are not matched to the Nov 21 archive | Verify PTH hole and finished screw/hardware geometry in the matched fabrication and assembly data | Open |

Do not claim a fixed percentage of design failures will be caught by this
review. Do not perform improvised energized mains testing.
