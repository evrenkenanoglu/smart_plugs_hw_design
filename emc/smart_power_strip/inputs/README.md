# Locked revision inputs

Place only exports tied to the revision recorded in
`../configs/revision_manifest.json` here. Update that manifest with relative
paths and SHA-256 values, and set `locked` to `true` only after a human has
confirmed the full input set belongs to that revision.

Required files depend on the bounded question; see
`../../docs/STAGE0_REVISION_LOCK.md` and `../../input-checklist.md`. Do not
copy historical or mismatched Gerber/STEP files here as placeholders. Do not
edit or overwrite the native CAD source during model setup.

For copper import, place each Gerber and its stackup evidence in this directory.
The layer-map `gerber_file` and stackup `source_file` values are relative to
this directory, and every configured file must also appear in the revision
manifest relative to `smart_power_strip/`. Each optional layer-map
`drill_files` entry names an Excellon file and its inclusive `from_layer` and
`to_layer` copper span; these endpoints are required and are never inferred.
The importer accepts only Excellon files with unambiguous units and coordinate
formats, subtracts hits and tool-width slots within the configured span, and
fails closed on unsupported input. It does not model via barrels or finite
copper thickness; CSXCAD output is a zero-thickness PEC sheet.
