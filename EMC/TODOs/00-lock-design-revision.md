# TODO 00 — Lock the authoritative design revision

**Status:** Blocked — export-source revision linkage not confirmed  
**Blocks:** Final manufacturing release sign-off, not exploratory candidate modeling

## Current evidence

The candidate package now includes MAIN_OMRON and UI Gerber/BOM/PnP/PCB-netlist
exports from 2026-11-19. The only staged native `Smart_Plugs.eprj2` reports an
internal project update on 2026-11-12, and the supplied PDFs are PCB-placement
drawings rather than schematics. The board/BOM/placement references are
largely consistent, but timestamps and matching designators do not prove that
the exports came from the exact saved native-project revision. The manifest
records candidate hashes and remains unlocked.

## Work

- [ ] Confirm which EasyEDA Pro project and board revision represent the design
  to be analyzed.
- [ ] Compare the native project history with available fabrication and
  assembly records; do not infer authority from file timestamps alone.
- [ ] Record the selected project's identity, board name/revision, export date,
  and SHA-256 hash in a revision manifest.
- [ ] Identify older or differently dated Gerber, STEP, schematic, BOM, and
  native-project files as unmatched until their revision relationship is
  established.

## Current candidate evidence

- Candidate project: `Smart_Plugs`, UUID
  `b0904c5e84060c537b3dc2b63eac7793f454a84d538ff657b90ce8a3616f8a5a`;
  staged `.eprj2` SHA-256 is recorded in the manifest.
- MAIN_OMRON and UI Gerber headers identify EasyEDA Pro v3.2.209 and
  2026-11-19 export timestamps.
- BOM and pick-and-place reference sets agree for both boards; the
  MAIN_OMRON PCB netlist omits BOM/PnP reference J2.
- Matching schematic PDFs and fabricator-confirmed stackup are not staged.
- Exact board revision and the relation between the staged `.eprj2` and
  2026-11-19 exports remain unconfirmed.

## Done when

- One native project revision is explicitly identified and its hash recorded.
- Existing exports are either linked to that revision or explicitly identified
  as unmatched candidates for exploratory modeling only.

## Safety and scope

Do not overwrite native CAD or released manufacturing files. A revision lock
establishes provenance only; it does not establish safety or compliance.
