"""Validation helpers for Touchstone S-parameter networks.

These checks are numerical design aids only. They do not establish EMC
compliance or validate the solver model that produced a network.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib import import_module
from numbers import Real
from os import PathLike, fspath
from typing import Any


class NetworkCheckError(ValueError):
    """Raised when a network or its supporting run evidence is invalid."""


def _load_numpy() -> Any:
    try:
        return import_module("numpy")
    except ImportError as exc:
        raise RuntimeError(
            "Network checks require the optional NumPy dependency; "
            "install numpy to process S-parameter data."
        ) from exc


def _load_skrf() -> Any:
    try:
        return import_module("skrf")
    except ImportError as exc:
        raise RuntimeError(
            "Touchstone loading requires the optional scikit-rf dependency "
            "(and NumPy); install scikit-rf to load Touchstone files."
        ) from exc


def load_touchstone(path: str | PathLike[str]) -> Any:
    """Load a Touchstone file with scikit-rf, importing it only when needed."""
    skrf = _load_skrf()
    return skrf.Network(fspath(path))


def require_converged_run(run_metadata: Mapping[str, Any]) -> None:
    """Require explicit solver end-criteria and mesh-convergence evidence."""
    if not isinstance(run_metadata, Mapping):
        raise NetworkCheckError("run_metadata must be a mapping")
    if run_metadata.get("solver_end_criteria_reached") is not True:
        raise NetworkCheckError(
            "Network processing requires solver_end_criteria_reached=True"
        )
    if (
        "solver_status" in run_metadata
        and run_metadata["solver_status"] != "end_criteria_reached"
    ):
        raise NetworkCheckError(
            "solver_status conflicts with solver end-criteria evidence"
        )
    mesh_convergence = run_metadata.get("mesh_convergence")
    if (
        not isinstance(mesh_convergence, Mapping)
        or mesh_convergence.get("passed") is not True
    ):
        raise NetworkCheckError(
            "Network processing requires mesh_convergence.passed=True"
        )


def _validate_tolerance(tolerance: Real) -> float:
    if isinstance(tolerance, bool) or not isinstance(tolerance, Real):
        raise ValueError("tolerance must be a finite non-negative real number")
    try:
        value = float(tolerance)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            "tolerance must be a finite non-negative real number"
        ) from exc
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("tolerance must be a finite non-negative real number")
    return value


def _scattering_matrix(network: Any, run_metadata: Mapping[str, Any]) -> tuple[Any, Any]:
    require_converged_run(run_metadata)
    numpy = _load_numpy()

    if not hasattr(network, "s"):
        raise NetworkCheckError("network must expose an S-parameter matrix as .s")
    if getattr(network, "s_def", None) != "power":
        raise NetworkCheckError(
            "Network checks require power-wave S parameters "
            "(network.s_def must be 'power')"
        )

    try:
        scattering = numpy.asarray(network.s)
    except (TypeError, ValueError) as exc:
        raise NetworkCheckError("network.s must be a numeric S-parameter array") from exc

    if scattering.ndim != 3 or scattering.shape[1] != scattering.shape[2]:
        raise NetworkCheckError(
            "network.s must have shape (frequency, port, port)"
        )
    if scattering.shape[0] == 0 or scattering.shape[1] == 0:
        raise NetworkCheckError("network.s must contain frequencies and ports")
    if not numpy.issubdtype(scattering.dtype, numpy.number):
        raise NetworkCheckError("network.s must contain numeric values")
    if not numpy.all(numpy.isfinite(scattering)):
        raise NetworkCheckError("network.s contains non-finite values")
    return numpy, scattering


def validate_finite_values(
    network: Any,
    *,
    run_metadata: Mapping[str, Any],
) -> None:
    """Reject malformed or non-finite S parameters after checking run evidence."""
    _scattering_matrix(network, run_metadata)


def maximum_singular_values(
    network: Any,
    *,
    run_metadata: Mapping[str, Any],
) -> tuple[float, ...]:
    """Return each frequency's largest singular value for power-wave S."""
    numpy, scattering = _scattering_matrix(network, run_metadata)
    try:
        singular_values = numpy.linalg.svd(scattering, compute_uv=False)
    except numpy.linalg.LinAlgError as exc:
        raise NetworkCheckError("Could not compute S-matrix singular values") from exc
    return tuple(float(value) for value in singular_values[:, 0])


def check_passivity(
    network: Any,
    *,
    run_metadata: Mapping[str, Any],
    tolerance: Real = 1e-9,
) -> bool:
    """Return whether max singular value of power-wave S is <= 1 + tolerance."""
    allowed_excess = _validate_tolerance(tolerance)
    maxima = maximum_singular_values(network, run_metadata=run_metadata)
    return all(value <= 1.0 + allowed_excess for value in maxima)


def check_reciprocity(
    network: Any,
    *,
    run_metadata: Mapping[str, Any],
    tolerance: Real = 1e-9,
) -> bool:
    """Return whether S approximately equals its transpose at every frequency.

    ``tolerance`` is an absolute per-element tolerance; no relative tolerance
    is applied.
    """
    absolute_tolerance = _validate_tolerance(tolerance)
    numpy, scattering = _scattering_matrix(network, run_metadata)
    difference = scattering - numpy.swapaxes(scattering, 1, 2)
    return bool(numpy.all(numpy.abs(difference) <= absolute_tolerance))
