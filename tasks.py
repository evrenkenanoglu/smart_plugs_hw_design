"""Windows-safe automation for the hardware workspace."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from invoke import Exit, task


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "ANALYSIS" / "power_calculations"
NEW_PCB_SOURCE = ROOT / "PCB" / "smart_plug_v3_easyeda"
LEGACY_PCB_SOURCE = ROOT / "ECAD" / "Smart_Plugs_EasyEDA"
MECHANICAL_DIR = ROOT.parent / "MECHANICAL"
GERBER_SUFFIXES = {".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo", ".gtp", ".gbp", ".gm1", ".gm2"}
DRILL_SUFFIXES = {".drl", ".xln"}
RELEASE_GROUPS = ("gerbers", "drill", "bom", "cpl", "schematic", "3d")
BOARD_INFO = {
    "main": {
        "release_dir": "main_pcb",
        "aliases": ("main", "omron"),
        "step_prefix": "3d_pcb_main",
    },
    "ui": {
        "release_dir": "ui_pcb",
        "aliases": ("ui", "control"),
        "step_prefix": "3d_pcb_ui",
    },
}
CASE_SENSITIVE_REFERENCES = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "TODOs.md",
    ROOT / ".mcp.json",
    ROOT / "pyproject.toml",
    ROOT / "tasks.py",
    ROOT / "HW_DESIGN.code-workspace",
    ROOT / ".agents" / "README.md",
    ROOT / ".agents" / "mcp" / "README.md",
    ROOT / ".agents" / "mcp" / "CONFIGURED_SERVERS.md",
    ROOT / "ANALYSIS" / "power_calculations",
    ROOT / "DOCS" / "design_notes",
    ROOT / "DOCS" / "datasheets",
    ROOT / "DOCS" / "reviews",
    ROOT / "ECAD" / "Smart_Plugs_EasyEDA",
    ROOT / "EMC",
    ROOT / "PCB" / "libraries",
    ROOT / "PCB" / "_archive",
    ROOT / "PCB" / "_archive" / "Smart_Plugs",
    ROOT / "PCB" / "_archive" / "README.md",
    ROOT / "PCB" / "_archive" / "Smart_Plugs" / "Scripts" / "package_gerbers.py",
    ROOT / "RELEASES" / "main_pcb",
    ROOT / "RELEASES" / "ui_pcb",
)


def _case_path_error(path: Path) -> str | None:
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


def _tracked_case_path_errors(extra_paths: tuple[Path, ...] = ()) -> tuple[list[str], int]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise Exit(f"Unable to list tracked paths: {error}", code=1) from error
    if result.returncode:
        details = result.stderr.decode(errors="replace").strip()
        raise Exit(f"Unable to list tracked paths: {details}", code=result.returncode)

    paths = [ROOT / os.fsdecode(item) for item in result.stdout.split(b"\0") if item]
    paths.extend(CASE_SENSITIVE_REFERENCES)
    paths.extend(extra_paths)
    seen: set[str] = set()
    errors = []
    for path in paths:
        key = os.fspath(path)
        if key in seen:
            continue
        seen.add(key)
        error = _case_path_error(path)
        if error:
            errors.append(f"{path}: {error}")
    return errors, len(seen)


def _pcb_source(source_dir: str | None = None) -> Path:
    if source_dir:
        source = Path(source_dir).expanduser().resolve()
        if not source.is_dir():
            raise Exit(f"PCB source directory does not exist: {source}", code=2)
        return source
    if NEW_PCB_SOURCE.is_dir() and any(NEW_PCB_SOURCE.iterdir()):
        return NEW_PCB_SOURCE
    if LEGACY_PCB_SOURCE.is_dir():
        return LEGACY_PCB_SOURCE
    raise Exit("No EasyEDA PCB source folder is available.", code=2)


def _board_matches(path: Path, source: Path, board: str) -> bool:
    relative = path.relative_to(source).as_posix().lower()
    if "combined" in relative:
        return False
    return any(alias in relative for alias in BOARD_INFO[board]["aliases"])


def _archive_members(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return []


def _find_artifacts(source: Path, board: str) -> dict[str, list[Path]]:
    groups = {name: [] for name in RELEASE_GROUPS}
    for path in source.rglob("*"):
        if not path.is_file() or not _board_matches(path, source, board):
            continue
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix in GERBER_SUFFIXES:
            groups["gerbers"].append(path)
        elif suffix in DRILL_SUFFIXES:
            groups["drill"].append(path)
        elif suffix == ".zip":
            members = _archive_members(path)
            member_suffixes = {PurePosixPath(member).suffix.lower() for member in members}
            if member_suffixes & GERBER_SUFFIXES:
                groups["gerbers"].append(path)
            if member_suffixes & DRILL_SUFFIXES:
                groups["drill"].append(path)
        elif suffix in {".csv", ".xlsx", ".xls"}:
            if "bom" in name or "bill_of_material" in name:
                groups["bom"].append(path)
            if any(token in name for token in ("pickandplace", "pick_and_place", "pnp", "centroid", "cpl")):
                groups["cpl"].append(path)
        elif suffix == ".pdf" and ("schematic" in name or "sch" in name):
            groups["schematic"].append(path)
        elif suffix in {".step", ".stp"} and name.startswith(BOARD_INFO[board]["step_prefix"]):
            groups["3d"].append(path)
    return groups


def _report_artifacts(source: Path, board: str, groups: dict[str, list[Path]]) -> bool:
    print(f"{board.upper()} source: {source}")
    complete = True
    for group in RELEASE_GROUPS:
        paths = groups[group]
        if paths:
            for path in sorted(paths):
                print(f"  FOUND {group}: {path.relative_to(source)}")
        else:
            print(f"  MISSING {group}")
            complete = False
    return complete


def _run_script(script: Path) -> str:
    if not script.is_file():
        raise RuntimeError(f"Calculation script is missing: {script}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        raise RuntimeError(f"{script.name} failed with exit code {result.returncode}")
    return result.stdout


def _run_uv(*arguments: str) -> None:
    executable = shutil.which("uv")
    if not executable:
        raise Exit("uv was not found on PATH; install uv before managing requirements.", code=2)
    result = subprocess.run([executable, *arguments], cwd=ROOT, check=False)
    if result.returncode:
        raise Exit(f"uv {' '.join(arguments)} failed with exit code {result.returncode}.", code=result.returncode)


def _calc_scripts() -> list[tuple[str, Path, str | None]]:
    return [
        ("Power calculations", ANALYSIS_DIR / "POWER_CALCULATIONS" / "scripts" / "main.py", None),
        ("LED calculations", ANALYSIS_DIR / "LED_CALCULATIONS" / "scripts" / "led_calc.py", None),
        (
            "Relay transistor calculations",
            ANALYSIS_DIR / "RELAY_TRANSISTOR_CALCULATION" / "scripts" / "relay_transistor_report.py",
            None,
        ),
        (
            "Omron relay transistor calculations",
            ANALYSIS_DIR / "RELAY_TRANSISTOR_CALCULATION" / "scripts" / "relay_transistor_report_omron.py",
            None,
        ),
        (
            "Flyback calculations",
            ANALYSIS_DIR / "FLYBACK_CONVERTER_CALCULATIONS" / "scripts" / "flyback_designer.py",
            "flyback_calculation.txt",
        ),
    ]


@task(name="compile")
def compile_requirements(_):
    """Compile requirements.in to a pinned requirements.txt using uv."""
    _run_uv(
        "pip",
        "compile",
        "requirements.in",
        "-o",
        "requirements.txt",
        "--annotation-style",
        "line",
    )


@task
def install(_):
    """Synchronize the active HW Python environment from requirements.txt using uv."""
    requirements = ROOT / "requirements.txt"
    if not requirements.is_file():
        raise Exit("requirements.txt is missing; run 'inv compile' first.", code=2)
    _run_uv("pip", "sync", "--python", sys.executable, str(requirements))


@task
def info(_):
    """Print Python environment, folder health, board exports, and known design-data conflicts."""
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    print(f"Virtual environment: {sys.prefix}")
    print(f"HW root: {ROOT}")
    for path in (
        ROOT / ".venv",
        ROOT / "PCB",
        ROOT / "DOCS",
        ROOT / "ANALYSIS",
        ROOT / "EMC",
        ROOT / "RELEASES",
    ):
        print(f"{'OK' if path.exists() else 'MISSING'} {path.relative_to(ROOT)}")
    try:
        source = _pcb_source()
    except Exit as error:
        print(f"PCB source: {error}")
        return
    print(f"PCB source: {source.relative_to(ROOT) if source.is_relative_to(ROOT) else source}")
    releases = source / "Releases"
    if releases.is_dir():
        for path in sorted(releases.iterdir()):
            if path.is_dir():
                print(f"Observed source release folder: {path.name} (revision linkage unverified)")
    for board, details in BOARD_INFO.items():
        steps = _find_artifacts(source, board)["3d"]
        print(f"{board.upper()} STEP candidates: {', '.join(path.name for path in steps) or 'none'}")
    print("Current design decisions: HLK-5LS05 and ESP32-C6.")
    print("Legacy HLK-10M05 and ESP32-WROOM-32UE references remain in older notes/calculation inputs.")
    print("No electrical input or calculation was changed by the folder rename.")


@task
def calc(_):
    """Run all calculation modules and write generated reports beneath each module's reports folder."""
    for title, script, report_name in _calc_scripts():
        print(f"== {title} ==")
        output = _run_script(script)
        if report_name:
            report_path = script.parents[1] / "reports" / "generated" / report_name
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(output, encoding="utf-8")
            print(f"Saved console report: {report_path.relative_to(ROOT)}")


@task
def reports(c):
    """Run calculations and update the generated-report index in DOCS/reviews."""
    calc(c)
    report_files = sorted(
        path
        for module in ANALYSIS_DIR.iterdir()
        if module.is_dir()
        for path in (module / "reports" / "generated").glob("*")
        if path.is_file()
    )
    summary = [
        "# Power Calculation Reports",
        "",
        "Generated calculation outputs are design assistance, not proof of safety or compliance.",
        "",
        "| Module | Generated report |",
        "| --- | --- |",
    ]
    for path in report_files:
        summary.append(f"| {path.parents[2].name} | `{path.relative_to(ROOT).as_posix()}` |")
    summary.extend(["", "Inputs are preserved separately under each module's `data/` directory."])
    target = ROOT / "DOCS" / "reviews" / "POWER_SUMMARY.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"Updated {target.relative_to(ROOT)} ({len(report_files)} reports)")


@task
def export_check(_, board="all", source_dir=None):
    """Check board-specific Gerber, drill, BOM, CPL, schematic PDF, and STEP artifacts."""
    if board not in {"all", "main", "ui"}:
        raise Exit("board must be all, main, or ui", code=2)
    source = _pcb_source(source_dir)
    boards = ("main", "ui") if board == "all" else (board,)
    complete = True
    for selected in boards:
        groups = _find_artifacts(source, selected)
        complete = _report_artifacts(source, selected, groups) and complete
    if not complete:
        raise Exit("Export check incomplete: required board-specific artifacts are missing.", code=1)
    print("All required per-board export artifact types are present; revision identity still requires review.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_zip_members(archive: zipfile.ZipFile, suffixes: set[str]) -> list[zipfile.ZipInfo]:
    safe = []
    for member in archive.infolist():
        normalized = member.filename.replace("\\", "/")
        member_path = PurePosixPath(normalized)
        if (
            member.is_dir()
            or member_path.is_absolute()
            or ".." in member_path.parts
            or any(":" in part for part in member_path.parts)
        ):
            continue
        if member_path.suffix.lower() in suffixes:
            safe.append(member)
    return safe


def _copy_group(paths: list[Path], destination: Path, group: str) -> list[Path]:
    copied = []
    destination.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.suffix.lower() == ".zip" and group in {"gerbers", "drill"}:
            allowed = GERBER_SUFFIXES if group == "gerbers" else DRILL_SUFFIXES
            with zipfile.ZipFile(path) as archive:
                for member in _safe_zip_members(archive, allowed):
                    target = destination / Path(*PurePosixPath(member.filename).parts)
                    if target.exists():
                        raise FileExistsError(f"Duplicate release artifact path: {target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    copied.append(target)
        else:
            target = destination / path.name
            if target.exists():
                raise FileExistsError(f"Duplicate release artifact path: {target}")
            shutil.copy2(path, target)
            copied.append(target)
    return copied


@task
def release(_, board="all", version=None, dry_run=False, source_dir=None):
    """Validate and package revision-tagged exports; dry-run validates without creating files."""
    if board not in {"all", "main", "ui"}:
        raise Exit("board must be all, main, or ui", code=2)
    if not version or not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise Exit("version is required and must contain only letters, digits, dot, underscore, or hyphen", code=2)
    source = _pcb_source(source_dir)
    boards = ("main", "ui") if board == "all" else (board,)
    plans = []
    complete = True
    for selected in boards:
        groups = _find_artifacts(source, selected)
        complete = _report_artifacts(source, selected, groups) and complete
        destination = ROOT / "RELEASES" / BOARD_INFO[selected]["release_dir"] / version
        if destination.exists():
            print(f"  BLOCKED: destination already exists: {destination.relative_to(ROOT)}")
            complete = False
        plans.append((selected, groups, destination))
    if not complete:
        raise Exit("Release blocked: required board-specific artifacts are missing or output already exists.", code=1)
    for selected, groups, destination in plans:
        print(f"{'DRY-RUN' if dry_run else 'PACKAGE'} {selected.upper()} -> {destination.relative_to(ROOT)}")
    if dry_run:
        print("Dry run complete; no release files or manifests were written.")
        return
    for selected, groups, destination in plans:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise Exit(f"Release destination appeared during packaging: {destination}", code=1)
        with tempfile.TemporaryDirectory(prefix=f".{version}.", dir=destination.parent) as temp_dir:
            staged = Path(temp_dir) / version
            manifest = {
                "manifest_version": 1,
                "board": selected,
                "version": version,
                "source_directory": str(source),
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "notice": "Packaging metadata does not establish revision identity, compliance, or safety.",
                "artifacts": {},
            }
            for group in RELEASE_GROUPS:
                copied = _copy_group(groups[group], staged / group, group)
                manifest["artifacts"][group] = [
                    {
                        "path": path.relative_to(staged).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                    for path in sorted(copied)
                ]
            (staged / "RELEASE_MANIFEST.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            staged.rename(destination)
        print(f"Created {destination.relative_to(ROOT)}")


@task
def emc_test(_):
    """Run the EMC simulation/support test suite with the active HW Python."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "EMC" / "tests")],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise Exit("EMC tests failed.", code=result.returncode)


@task
def path_integrity(_):
    """Verify calculation paths and the unchanged Mechanical PCB STEP inputs."""
    expected = [
        ANALYSIS_DIR / "POWER_CALCULATIONS" / "data" / "peak_data.json",
        ANALYSIS_DIR / "LED_CALCULATIONS" / "data" / "led_data.json",
        ANALYSIS_DIR / "FLYBACK_CONVERTER_CALCULATIONS" / "data" / "specs.json",
        LEGACY_PCB_SOURCE / "Output" / "3D_PCB_MAIN_OMRON_2026-11-12.step",
        LEGACY_PCB_SOURCE / "Output" / "3D_PCB_UI_2026-11-12.step",
        MECHANICAL_DIR / "scripts" / "power_strip" / "build_assembly.py",
        MECHANICAL_DIR / "scripts" / "power_strip" / "build_ui_mounts.py",
    ]
    errors, checked = _tracked_case_path_errors(tuple(expected))
    for error in errors:
        print(f"PATH ERROR {error}")
    if errors:
        raise Exit(f"Exact-case path integrity failed for {len(errors)} paths.", code=1)
    print(f"Exact-case check passed for {checked} tracked/reference paths.")
    missing = [path for path in expected if not path.is_file()]
    for path in expected:
        print(f"{'MISSING' if path in missing else 'OK'} {path}")
    if missing:
        raise Exit(f"Path integrity failed for {len(missing)} required paths.", code=1)
    print("Mechanical source inputs resolve under ECAD; Mechanical CAD logic remains unchanged.")


@task
def case_paths(_):
    """Verify exact casing of tracked workspace, configuration, and documentation paths."""
    errors, checked = _tracked_case_path_errors()
    for error in errors:
        print(f"PATH ERROR {error}")
    if errors:
        raise Exit(f"Exact-case path check failed for {len(errors)} paths.", code=1)
    print(f"Exact-case path check passed for {checked} tracked/reference paths.")


@task
def check(c):
    """Run calculations, EMC tests, export checks, and path-integrity checks."""
    checks = (
        ("calc", calc),
        ("emc_test", emc_test),
        ("export_check", export_check),
        ("path_integrity", path_integrity),
    )
    failures = []
    for name, check_task in checks:
        print(f"== {name} ==")
        try:
            check_task(c)
        except (Exit, RuntimeError) as error:
            failures.append((name, error))
            print(f"FAILED {name}: {error}", file=sys.stderr)
    if failures:
        names = ", ".join(name for name, _ in failures)
        raise Exit(f"Check completed with failures: {names}", code=1)
    print("All checks passed.")


@task
def clean(_):
    """Remove Python/test caches and build temp folders without touching PCB, releases, docs, or .venv."""
    protected = {
        ".git",
        ".venv",
        ".agents",
        "_SCRATCH",
        "ANALYSIS",
        "DOCS",
        "ECAD",
        "EMC",
        "PCB",
        "PCB_DESIGN",
        "RELEASES",
    }
    removable = {"__pycache__", ".pytest_cache", "build", "dist"}
    removed = []
    for current, dirs, _files in os.walk(ROOT, topdown=True):
        dirs[:] = [name for name in dirs if name not in protected]
        current_path = Path(current)
        for name in list(dirs):
            path = current_path / name
            if name in removable or name.endswith(".egg-info"):
                shutil.rmtree(path)
                dirs.remove(name)
                removed.append(path.relative_to(ROOT).as_posix())
    print("Removed:" if removed else "No generated caches found.")
    for path in removed:
        print(f"  {path}")
