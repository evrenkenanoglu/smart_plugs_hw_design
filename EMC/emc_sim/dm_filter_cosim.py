"""Exploratory pre/post-L1 differential-mode PCB/filter co-simulation.

The supplied scikit-rf network represents the *unpopulated* L1 bypass between
two differential ports, not a series interconnect. The supplied network must
exclude the L1 and C2 component admittances to avoid double counting. Port 1
is pre-L1 and port 2 is post-L1; both voltages are line minus neutral, with
currents entering the network. The L1 differential impedance is connected in
parallel with that bypass, and C2 is across the pre-L1 differential port.

This reduced model excludes CY1: the candidate netlist connects it between
secondary U1.4 and GND, and its influence on primary DM requires justified
converter/secondary coupling. It is not a full BOM, common-mode, or
mode-conversion model. Component values are idealized assumptions, not
validated high-frequency part models; winding capacitance, core loss, C2
ESR/ESL, converter and other BOM parts are omitted. Results require the
caller's candidate export hashes, stackup and field-solver assumptions to be
preserved alongside the returned arrays. Differential reference impedance is
50 ohms per port, not 50 ohms per conductor.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Any, Mapping

import numpy as np
import skrf

from emc_sim.network_checks import (
    NetworkCheckError,
    check_passivity,
    check_reciprocity,
    require_converged_run,
    validate_finite_values,
)


STAMP = "CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF"
CY1_LIMITATION = (
    "CY1 2.2 nF connects secondary U1.4 to GND; its primary-DM effect "
    "cannot be represented without justified converter/secondary coupling."
)


@dataclass(frozen=True)
class DMFilterAssumptions:
    """Assumed symmetric coupled windings and ideal input capacitor, in SI units."""

    winding_inductance_h: float = 10e-3
    coupling: float = 0.99
    winding_resistance_ohm: float = 0.5
    c2_f: float = 100e-9
    source_resistance_ohm: float = 50.0
    load_resistance_ohm: float = 50.0


@dataclass(frozen=True)
class DMFilterResult:
    frequency_hz: np.ndarray
    s: np.ndarray
    voltage_transfer: np.ndarray
    candidate_export: str
    assumptions: DMFilterAssumptions
    stamp: str = STAMP
    limitation: str = CY1_LIMITATION


def _real(value: Real, name: str, *, minimum: float, inclusive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not isfinite(value) or (value < minimum if inclusive else value <= minimum):
        raise ValueError(f"{name} is outside its permitted range")
    return value


def cosimulate_dm_filter(
    bypass_network: skrf.Network,
    *,
    run_metadata: Mapping[str, Any],
    candidate_export: str,
    frequency_band_hz: tuple[float, float],
    pre_post_polarity_confirmed: bool,
    assumptions: DMFilterAssumptions = DMFilterAssumptions(),
) -> DMFilterResult:
    """Return full-network S and Vload/Vth for a Thevenin DM voltage source.

    The source is in series with its stated positive resistance at pre-L1;
    the positive load resistance terminates post-L1. No file is read or written.
    The caller must establish the actual unpopulated geometry, port polarity,
    candidate provenance and convergence evidence; the boolean is an explicit
    attestation, not a check of the underlying field model. The exact frequency
    grid must span the requested band; no interpolation or extrapolation occurs.
    """
    require_converged_run(run_metadata)
    for gate in ("time_convergence", "boundary_convergence", "passivity"):
        evidence = run_metadata.get(gate)
        if not isinstance(evidence, Mapping) or evidence.get("passed") is not True:
            raise NetworkCheckError(f"{gate}.passed=True is required")
    if pre_post_polarity_confirmed is not True:
        raise ValueError("Confirm pre/post differential port order and polarity")
    if not isinstance(candidate_export, str) or not candidate_export.strip():
        raise ValueError("candidate_export must identify the source export")
    if not isinstance(assumptions, DMFilterAssumptions):
        raise ValueError("assumptions must be DMFilterAssumptions")
    inductance = _real(assumptions.winding_inductance_h, "inductance", minimum=0)
    resistance = _real(assumptions.winding_resistance_ohm, "winding resistance",
                       minimum=0, inclusive=True)
    coupling = _real(assumptions.coupling, "coupling", minimum=0, inclusive=True)
    if coupling >= 1:
        raise ValueError("coupling must be less than 1")
    capacitance = _real(assumptions.c2_f, "C2", minimum=0, inclusive=True)
    source = _real(assumptions.source_resistance_ohm, "source resistance", minimum=0)
    load = _real(assumptions.load_resistance_ohm, "load resistance", minimum=0)
    if not isinstance(frequency_band_hz, (tuple, list)) or len(frequency_band_hz) != 2:
        raise ValueError("frequency_band_hz must contain two endpoints")
    low, high = (_real(v, "band endpoint", minimum=0) for v in frequency_band_hz)
    if low >= high:
        raise ValueError("frequency band must be increasing")

    if not isinstance(bypass_network, skrf.Network):
        raise ValueError("bypass_network must be a scikit-rf Network")
    validate_finite_values(bypass_network, run_metadata=run_metadata)
    s = np.asarray(bypass_network.s, dtype=complex)
    f = np.asarray(bypass_network.f, dtype=float)
    if s.shape[1:] != (2, 2) or f.ndim != 1 or len(f) != len(s) or len(f) < 2:
        raise NetworkCheckError("bypass network must be a two-port with at least two frequencies")
    if (not np.all(np.isfinite(f)) or np.any(f <= 0) or np.any(np.diff(f) <= 0)
            or not np.isclose(f[0], low, rtol=1e-12, atol=0)
            or not np.isclose(f[-1], high, rtol=1e-12, atol=0)):
        raise NetworkCheckError("network frequencies must strictly increase and span the requested band")
    z0 = np.asarray(bypass_network.z0)
    if z0.shape != (len(f), 2) or not np.all(np.isfinite(z0)) or not np.all(z0 == 50):
        raise NetworkCheckError("both ports must use consistent real 50-ohm references")
    if not check_passivity(bypass_network, run_metadata=run_metadata):
        raise NetworkCheckError("bypass network is not passive")
    if not check_reciprocity(bypass_network, run_metadata=run_metadata):
        raise NetworkCheckError("bypass network is not reciprocal")

    omega = 2 * np.pi * f
    # Opposing differential winding currents give Ldm = 2 L (1-k).
    z_choke = 2 * resistance + 1j * omega * (2 * inductance * (1 - coupling))
    y = (1 / z_choke)[:, None, None] * np.array([[1, -1], [-1, 1]])
    y[:, 0, 0] += 1j * omega * capacitance
    eye = np.eye(2, dtype=complex)
    correction = 25 * (y @ (eye + s))
    try:
        # Right division: (S - correction) @ inv(I + correction).
        combined_s = np.linalg.solve(
            np.swapaxes(eye + correction, -1, -2),
            np.swapaxes(s - correction, -1, -2),
        ).swapaxes(-1, -2)
    except np.linalg.LinAlgError as exc:
        raise NetworkCheckError("singular bypass/filter connection") from exc
    combined = skrf.Network(frequency=bypass_network.frequency.copy(),
                            s=combined_s, z0=50, s_def="power")
    validate_finite_values(combined, run_metadata=run_metadata)
    if not check_passivity(combined, run_metadata=run_metadata):
        raise NetworkCheckError("combined network is not passive")
    if not check_reciprocity(combined, run_metadata=run_metadata):
        raise NetworkCheckError("combined network is not reciprocal")

    gamma = np.array([(source - 50) / (source + 50),
                      (load - 50) / (load + 50)])
    excitation = np.array([np.sqrt(50) / (source + 50), 0])
    try:
        incident = np.linalg.solve(eye - gamma[:, None] * combined_s, excitation)
    except np.linalg.LinAlgError as exc:
        raise NetworkCheckError("singular source/load termination") from exc
    reflected = np.einsum("fij,fj->fi", combined_s, incident)
    transfer = np.sqrt(50) * (1 + gamma[1]) * reflected[:, 1]
    if not np.all(np.isfinite(transfer)):
        raise NetworkCheckError("non-finite loaded voltage transfer")
    return DMFilterResult(f.copy(), combined_s.copy(), transfer, candidate_export.strip(),
                          assumptions)
