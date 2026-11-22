"""Fail-closed helpers for executing and gating openEMS model scripts."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from numbers import Real
from pathlib import Path
from typing import Any, Sequence


class OpenEMSError(RuntimeError):
    """Raised for a failed or insufficiently validated openEMS run."""


def run_model_script(
    script: Path,
    run_directory: Path,
    *,
    arguments: Sequence[str] = (),
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a caller-supplied Python model in a new output directory.

    Geometry and all solver parameters remain the responsibility of the model
    script. The helper never invents stackup, boundaries, or reference planes.
    """
    script = script.resolve()
    run_directory = run_directory.resolve()
    if not script.is_file():
        raise OpenEMSError(f"Model script does not exist: {script}")
    if run_directory.exists():
        raise OpenEMSError(f"Refusing to overwrite run directory: {run_directory}")
    run_directory.mkdir(parents=True)
    command = [sys.executable, str(script), *arguments]
    try:
        result = subprocess.run(
            command,
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OpenEMSError(f"Could not complete openEMS model command: {exc}") from exc
    (run_directory / "model_stdout.log").write_text(result.stdout, encoding="utf-8")
    (run_directory / "model_stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise OpenEMSError(
            f"Model script exited with status {result.returncode}; see logs in "
            f"{run_directory}"
        )
    return result


def validate_run_metadata(
    metadata_path: Path,
    *,
    require_mesh_convergence: bool = True,
    require_boundary_convergence: bool = False,
) -> dict[str, Any]:
    """Load metadata and reject incomplete, unconverged, or non-finite runs."""
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenEMSError(f"Cannot read run metadata {metadata_path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise OpenEMSError("Run metadata must be a JSON object")
    if metadata.get("solver_status") != "end_criteria_reached":
        raise OpenEMSError("Solver did not reach its configured energy end criterion")
    if metadata.get("solver_end_criteria_reached") is not True:
        raise OpenEMSError("Solver end-criteria flag is missing or false")
    if require_mesh_convergence:
        convergence = metadata.get("mesh_convergence")
        if not isinstance(convergence, dict) or convergence.get("passed") is not True:
            raise OpenEMSError("Mesh convergence has not been demonstrated")
    if require_boundary_convergence:
        convergence = metadata.get("boundary_convergence")
        if not isinstance(convergence, dict) or convergence.get("passed") is not True:
            raise OpenEMSError("Boundary convergence has not been demonstrated")
    for key in ("timestep_count", "maximum_timestep_limit"):
        value = metadata.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise OpenEMSError(f"{key} must be a positive integer")
    if metadata["timestep_count"] > metadata["maximum_timestep_limit"]:
        raise OpenEMSError("Solver timestep count exceeds its configured maximum")
    for key in (
        "final_energy_to_sampled_peak_energy_ratio",
        "final_energy_to_peak_ratio",
    ):
        if key in metadata:
            value = metadata[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or value < 0
            ):
                raise OpenEMSError(f"{key} must be finite and non-negative")
    return metadata


def compare_mesh_values(
    coarse: float,
    fine: float,
    *,
    relative_tolerance: float,
) -> float:
    """Return relative change and reject a pair that exceeds caller tolerance.

    The tolerance and quantity of interest must be justified by the model
    owner; this function does not choose an engineering acceptance threshold.
    """
    values = (coarse, fine, relative_tolerance)
    if any(
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Mesh values and tolerance must be finite")
    if relative_tolerance <= 0.0:
        raise ValueError("relative_tolerance must be positive")
    scale = max(abs(coarse), abs(fine))
    if scale == 0.0:
        return 0.0
    relative_change = abs(fine - coarse) / scale
    if relative_change > relative_tolerance:
        raise OpenEMSError(
            f"Mesh result changed by {relative_change:.6g}, exceeding the "
            f"configured tolerance {relative_tolerance:.6g}"
        )
    return relative_change
