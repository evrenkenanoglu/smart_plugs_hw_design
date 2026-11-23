"""Portable exact-case checks for tracked files and important workspace paths."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
CASE_SENSITIVE_REFERENCES = (
    "README.md",
    "AGENTS.md",
    "TODOs.md",
    ".mcp.json",
    "pyproject.toml",
    "tasks.py",
    "check_case_paths.py",
    "HW_DESIGN.code-workspace",
    ".agents/README.md",
    ".agents/mcp/README.md",
    ".agents/mcp/CONFIGURED_SERVERS.md",
    "ANALYSIS/power_calculations",
    "ANALYSIS/power_calculations/POWER_CALCULATIONS/data/peak_data.json",
    "ANALYSIS/power_calculations/LED_CALCULATIONS/data/led_data.json",
    "ANALYSIS/power_calculations/FLYBACK_CONVERTER_CALCULATIONS/data/specs.json",
    "DOCS/design_notes",
    "DOCS/datasheets",
    "DOCS/reviews",
    "ECAD/Smart_Plugs_EasyEDA",
    "ECAD/Smart_Plugs_EasyEDA/Output/3D_PCB_MAIN_OMRON_2026-11-12.step",
    "ECAD/Smart_Plugs_EasyEDA/Output/3D_PCB_UI_2026-11-12.step",
    "EMC",
    "PCB/libraries",
    "PCB/_archive",
    "PCB/_archive/Smart_Plugs",
    "PCB/_archive/README.md",
    "PCB/_archive/Smart_Plugs/Scripts/package_gerbers.py",
    "RELEASES/main_pcb",
    "RELEASES/ui_pcb",
    "../MECHANICAL/scripts/power_strip/build_assembly.py",
    "../MECHANICAL/scripts/power_strip/build_ui_mounts.py",
)


def case_path_error(path: Path) -> str | None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        try:
            with os.scandir(current) as entries:
                names = {entry.name for entry in entries}
        except OSError:
            return f"missing parent directory: {current}"
        if part in names:
            current /= part
            continue
        actual = next((name for name in names if name.casefold() == part.casefold()), None)
        if actual is not None:
            return f"case mismatch beneath {current}: expected {part!r}, found {actual!r}"
        return f"missing path segment beneath {current}: {part!r}"
    return None


def _tracked_paths(root: Path) -> tuple[list[Path], str | None]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        return [], f"Git tracked-file scan unavailable; checking explicit references only ({error})."
    if result.returncode:
        details = result.stderr.decode(errors="replace").strip()
        return [], (
            "Git tracked-file scan unavailable; checking explicit references only"
            + (f" ({details})." if details else ".")
        )
    paths = [root / os.fsdecode(item) for item in result.stdout.split(b"\0") if item]
    return paths, None


def validate_case_paths(root: Path = ROOT) -> tuple[list[str], int, str | None]:
    root = Path(root).resolve()
    paths, warning = _tracked_paths(root)
    paths.extend(root.joinpath(*PurePosixPath(reference).parts) for reference in CASE_SENSITIVE_REFERENCES)

    seen: set[str] = set()
    errors = []
    for path in paths:
        key = os.fspath(path)
        if key in seen:
            continue
        seen.add(key)
        error = case_path_error(path)
        if error:
            errors.append(f"{path}: {error}")
    return errors, len(seen), warning


def main() -> int:
    errors, checked, warning = validate_case_paths()
    if warning:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"PATH ERROR {error}")
    if errors:
        print(f"Exact-case path check failed for {len(errors)} paths.")
        return 1
    print(f"Exact-case path check passed for {checked} tracked/reference paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
