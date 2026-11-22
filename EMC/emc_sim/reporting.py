"""Non-overwriting run folders and evidence-labeled report generation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def create_run_directory(root: Path, run_id: str | None = None) -> Path:
    """Create a unique run directory; never reuse or overwrite an existing one."""
    root.mkdir(parents=True, exist_ok=True)
    identifier = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not _RUN_ID_RE.fullmatch(identifier):
        raise ValueError("run_id may contain only letters, digits, dot, underscore, hyphen")
    path = root / identifier
    path.mkdir(exist_ok=False)
    return path


def write_run_metadata(run_directory: Path, metadata: dict[str, Any]) -> Path:
    """Write JSON metadata into a run folder without replacing an existing file."""
    destination = run_directory / "run_metadata.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    payload = dict(metadata)
    payload.setdefault("created_utc", datetime.now(timezone.utc).isoformat())
    destination.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    return destination


def write_report(
    run_directory: Path,
    *,
    question: str,
    evidence: dict[str, list[str]],
    result: str,
    limitations: list[str],
) -> Path:
    """Write a report with explicit evidence categories and lab-only questions."""
    required = ("assumptions", "calculations", "simulations", "measurements")
    missing = [category for category in required if category not in evidence]
    if missing:
        raise ValueError(f"Missing evidence categories: {', '.join(missing)}")
    lines = [
        "# EMC pre-design model report",
        "",
        "> Design assistance only. This report does not establish safety, "
        "compliance, certification, or test margin.",
        "",
        "## Bounded question",
        "",
        question,
        "",
        "## Evidence categories",
        "",
    ]
    for category in required:
        lines.extend([f"### {category.title()}", ""])
        items = evidence[category]
        lines.extend([f"- {item}" for item in items] if items else ["- None recorded."])
        lines.append("")
    lines.extend(["## Model result", "", result, "", "## Limitations", ""])
    lines.extend([f"- {item}" for item in limitations] if limitations else ["- None recorded."])
    lines.extend(
        [
            "",
            "## What Only a Qualified Lab Can Answer",
            "",
            "- Product emissions with representative live operation, loads, "
            "cables, enclosure, and the applicable measurement setup.",
            "- Immunity to surge, EFT/burst, ESD, RF, and voltage disturbances.",
            "- Electrical safety, dielectric withstand, touch/leakage current, "
            "thermal rise, and fault behavior.",
            "- Radio certification/coexistence, harmonics, and flicker where applicable.",
            "",
        ]
    )
    destination = run_directory / "report.md"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination
