# Qualified EMC and safety lab handoff

This is a preparation template, not a test plan or compliance claim. Complete
the product-specific fields with a qualified compliance specialist and the
selected laboratory. Energized mains testing belongs only in a properly
equipped, qualified facility.

## Product and configuration

- Product name / model: **TBD**
- Intended markets: **TBD**
- Product category: **TBD**
- Applicable standards and editions: **TBD with qualified specialist**
- Authoritative EasyEDA project and PCB revision: **UNCONFIRMED**
- Revision manifest and input hashes:
  `../smart_power_strip/configs/revision_manifest.json`
  (**currently unlocked**)
- Prototype / assembly revision and quantity: **TBD**
- Enclosure, cable, and accessory revisions: **TBD**
- Operating modes and worst-case configurations: **TBD**
- Load types, ratings, and channel combinations: **TBD**
- Radio module, antenna, bands, and modes (if applicable): **TBD**

## Evidence available

- **Measured:** None. No product EMC or electrical-safety laboratory data is
  available in this workspace.
- **Calculated:** A Hammerstad-Jensen microstrip estimate of approximately
  89.3 ohm was made for a historical, assumed 1 mm trace over 1.6 mm FR-4 with
  relative permittivity 4.2. It is a simplified analytical estimate, not a
  measurement or product result.
- **Simulated:** An archived openEMS coupon reported an MSL port-reference
  real-part midpoint of approximately 134.2 ohm. Its roughly 50.3% difference
  from the simplified estimate is unresolved. The coupon assumes a continuous
  return plane, uses a straightened route and coarse mesh, and omits the actual
  filter, other PCB copper, components, enclosure, cables, and validated noise
  sources. It is not a calibrated benchmark or an emissions prediction.
- **Installation check:** The official openEMS notch-filter tutorial ran
  successfully. It verifies a basic solver installation only; it is not a
  smart-plug simulation.

The revision candidates and model limitations are recorded in
`STAGE0_REVISION_LOCK.md`, `../README.md`, and `../TODOs/README.md`. Do not
combine files from different candidate revisions as one design.

## Questions for the laboratory

Ask the laboratory and qualified compliance specialist to determine:

- The applicable emissions, immunity, harmonics/flicker, radio, and electrical
  safety evaluations for the confirmed product category and target markets.
- Required operating modes, representative loads, cable and enclosure
  configurations, sample count, and any destructive or safety evaluations.
- Applicable acceptance criteria, detector/receiver settings, and test
  configurations. Do not assume a universal engineering margin.
- Whether a construction/document review should precede physical testing.
- The appropriate pre-compliance and formal certification sequence, sample
  preparation, and records to provide.

## Open evidence needed before booking

- Confirm the authoritative EasyEDA project and PCB revision.
- Export and hash the matched schematic, netlist, Gerbers, drills, BOM,
  assembly data, stackup, and relevant enclosure files.
- Reconcile the open items in `../risk-register.md` against the actual design
  and manufacturer data.
- Identify actual product operating modes, loads, cables, radio modes, and
  intended markets.
- Resolve the openEMS benchmark discrepancy before relying on any
  project-specific full-wave result.
- Add future measured results only with the sample revision, configuration,
  laboratory, method, and report reference recorded.

## Safety and interpretation

Simulation, calculations, design review, and this handoff template do not
establish that hardware is safe or compliant. Do not perform improvised
energized mains tests. No result from this software workflow should be
presented as laboratory measurement, certification margin, or proof of
compliance.
