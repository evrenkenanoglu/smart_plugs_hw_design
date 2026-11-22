"""Revision-manifest validation and SHA-256 provenance checks."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """Raised when an input manifest is incomplete or does not verify."""


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 digest without loading the entire file at once."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a JSON revision manifest, requiring a top-level object."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read revision manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ManifestError("Revision manifest must be a JSON object")
    return manifest


def verify_manifest(
    manifest_path: Path,
    *,
    require_locked: bool = True,
    allow_candidate: bool = False,
    input_root: Path | None = None,
) -> dict[str, Any]:
    """Validate a revision manifest and verify every listed file hash.

    File paths are relative to ``input_root`` when provided, otherwise to the
    manifest's parent directory. Paths may not escape that root. A manifest
    marked as unlocked is rejected by default unless ``allow_candidate=True``.
    """
    manifest = load_manifest(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")
    revision = manifest.get("revision")
    if not isinstance(revision, str) or not revision.strip():
        raise ManifestError("revision must be a non-empty string")
    if not allow_candidate and require_locked and manifest.get("locked") is not True:
        raise ManifestError("Revision manifest is not locked")
    if not isinstance(manifest.get("locked"), bool):
        raise ManifestError("locked must be a boolean")

    placeholder_tokens = {"TODO", "TODO_VERIFY_FROM_STAGE_0", "UNCONFIRMED"}
    project_id = manifest.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ManifestError("project_id must identify the project")
    if not allow_candidate and project_id.strip().upper() in placeholder_tokens:
        raise ManifestError("project_id must identify the confirmed project")
    if not allow_candidate and revision.strip().upper() in placeholder_tokens:
        raise ManifestError("revision must identify the confirmed board revision")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ManifestError("files must contain at least one revision input")
    seen: set[str] = set()
    base = (input_root or manifest_path.parent).resolve()
    for entry in files:
        if not isinstance(entry, dict):
            raise ManifestError("Each files entry must be an object")
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not relative.strip():
            raise ManifestError("Each files entry needs a relative path")
        if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
            raise ManifestError(f"Invalid SHA-256 for input {relative!r}")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ManifestError(f"Input path must stay under input root: {relative}")
        normalized = candidate.as_posix().casefold()
        if normalized in seen:
            raise ManifestError(f"Duplicate input path: {relative}")
        seen.add(normalized)
        resolved = (base / candidate).resolve()
        if base not in resolved.parents:
            raise ManifestError(f"Input path escapes input root: {relative}")
        if not resolved.is_file():
            raise ManifestError(f"Revision input does not exist: {resolved}")
        actual = sha256_file(resolved)
        if actual != expected:
            raise ManifestError(
                f"SHA-256 mismatch for {relative}: expected {expected}, got {actual}"
            )
        if not allow_candidate and entry.get("revision", revision) != revision:
            raise ManifestError(f"Input {relative} belongs to a different revision")
    return manifest