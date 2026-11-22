"""Fail-closed helpers for user-configured ngspice circuit models.

This module intentionally does not generate a universal LISN, filter, or
switching-noise source. Circuit and test networks must be supplied with
revision/model provenance by the application configuration.
"""

from __future__ import annotations

import math
import re
from numbers import Real
import shutil
import subprocess
from pathlib import Path
from typing import Any


class SpiceModelError(RuntimeError):
    """Raised when an ngspice model is unavailable or invalid."""


def _find_ngspice(executable: str) -> str | None:
    binary = shutil.which(executable)
    if binary and Path(binary).name.lower() == "ngspice.exe":
        console = Path(binary).with_name("ngspice_con.exe")
        if console.is_file():
            return str(console)
    return binary


def load_conducted_config(path: Path) -> dict[str, Any]:
    """Load YAML config and reject placeholders or missing provenance."""
    try:
        import yaml
    except ImportError as exc:
        raise SpiceModelError(
            "PyYAML is required for YAML configs; install the 'spice' extra"
        ) from exc
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SpiceModelError(f"Cannot read conducted model config {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise SpiceModelError("Conducted model config must be a YAML object")
    candidate = config.get("mode") == "candidate"
    required = ("source", "measurement_network", "frequency_band_hz") + (
        ("candidate_dir", "stackup_metadata") if candidate else ("netlist",)
    )
    missing = [key for key in required if key not in config]
    if missing:
        raise SpiceModelError(f"Missing conducted config fields: {', '.join(missing)}")
    for key in ("source", "measurement_network"):
        value = config[key]
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("provenance"), str)
            or not value["provenance"].strip()
        ):
            raise SpiceModelError(f"{key}.provenance is required; assumptions must be explicit")
        if value.get("status") in ("TODO_VERIFY_FROM_STAGE_0", "TODO"):
            raise SpiceModelError(f"{key} is still a placeholder")
    band = config["frequency_band_hz"]
    if (
        not isinstance(band, list)
        or len(band) != 2
        or any(isinstance(v, bool) or not isinstance(v, Real) for v in band)
        or not all(math.isfinite(v) and v > 0 for v in band)
        or band[0] >= band[1]
    ):
        raise SpiceModelError("frequency_band_hz must be [positive_min, larger_max]")
    if candidate:
        for field in ("candidate_dir", "stackup_metadata"):
            value = config[field]
            if not isinstance(value, str) or not value.strip():
                raise SpiceModelError(f"{field} must name an existing candidate input")
            resolved = (path.parent / value).resolve()
            if not (resolved.is_dir() if field == "candidate_dir" else resolved.is_file()):
                raise SpiceModelError(f"Candidate input does not exist: {resolved}")
            config[f"_resolved_{field}"] = str(resolved)
        return config
    if not isinstance(config["netlist"], str) or not config["netlist"].strip():
        raise SpiceModelError("netlist must name an existing SPICE file")
    netlist = (path.parent / config["netlist"]).resolve()
    if not netlist.is_file():
        raise SpiceModelError(f"Configured SPICE netlist does not exist: {netlist}")
    config["_resolved_netlist"] = str(netlist)
    return config


CANDIDATE_STAMP = "CANDIDATE / EXPLORATORY SIMULATION — NOT COMPLIANCE OR SAFETY PROOF"


def validate_candidate_scenario(config: dict[str, Any]) -> None:
    """Reject edits to the documented fixed scenario that the netlist ignores."""
    expected = {
        "source_revision": "MAIN_OMRON_MCP_CANDIDATE_20261121_1753",
        "source": {
            "status": "assumed",
            "provenance": "Bounded synthetic HLK-5LS05 scenarios, not measured converter data",
            "description": "1 uA DM or 1 uA per conductor CM with 100 kohm primary shunt",
        },
        "measurement_network": {
            "status": "assumed",
            "provenance": "Candidate CISPR 16/32-style 50 uH and 50 ohm two-line network; applicability and impedance tolerance not verified",
            "description": "Each branch has 50 uH with 5 ohm series resistance, 8 uF supply-side capacitance and a 250 nF coupled 50 ohm receiver",
        },
        "components": {
            "L1": "UU9.8-10mH, assumed 10 mH per winding and 0.5 ohm each",
            "C2": "100 nF X2",
            "CY1": "2.2 nF Y1, secondary-rail connection per candidate netlist",
            "R6": "10D-7, assumed 2 ohm hot resistance",
            "RV1": "14D431K, assumed 440 pF linear capacitance",
            "coupling": "Assumed k values 0.95, 0.99 and 0.999",
            "parasitics": "Assumed 100 pF primary-secondary and 100 pF secondary-reference, with 1 Mohm secondary leakage",
        },
        "sweep": ["DM k 0.95", "DM k 0.99", "DM k 0.999", "CM k 0.99"],
    }
    for field, value in expected.items():
        if config.get(field) != value:
            raise SpiceModelError(
                f"Candidate {field} differs from the fixed simulated scenario; "
                "config edits are not model parameter overrides"
            )
    allowed = set(expected) | {
        "mode", "candidate_dir", "stackup_metadata", "frequency_band_hz",
        "_resolved_candidate_dir", "_resolved_stackup_metadata",
    }
    extra = set(config) - allowed
    if extra:
        raise SpiceModelError(f"Unsupported candidate config fields: {', '.join(sorted(extra))}")
    candidate = Path(config["_resolved_candidate_dir"])
    stackup = Path(config["_resolved_stackup_metadata"])
    if (candidate.name != "MCP_CANDIDATE_20261121_1753" or
            candidate.parent.name != "MAIN_OMRON" or
            stackup.name != "MCP_LIVE_20261119_203444_LayerStackup.json" or
            stackup.parent != candidate.parent):
        raise SpiceModelError("Fixed scenario requires the selected MAIN_OMRON candidate and stackup")


def attenuation_db(filtered: list[list[float]], bypass: list[list[float]],
                   column: int) -> list[float]:
    """Same-conductor bypass/filtered voltage magnitude ratio in dB."""
    if column not in (1, 3) or len(filtered) != len(bypass) or not filtered:
        raise SpiceModelError("Attenuation requires matching non-empty AC traces")
    values = []
    for row, reference in zip(filtered, bypass):
        if (len(row) != 5 or len(reference) != 5 or
                not all(math.isfinite(x) for x in (*row, *reference)) or
                not math.isclose(row[0], reference[0], rel_tol=1e-9)):
            raise SpiceModelError("Attenuation frequency grids or samples do not match")
        measured = abs(complex(row[column], row[column + 1]))
        baseline = abs(complex(reference[column], reference[column + 1]))
        if measured == 0 or baseline == 0:
            raise SpiceModelError("Attenuation ratio is undefined at zero voltage")
        values.append(20 * (math.log10(baseline) - math.log10(measured)))
    return values


def candidate_netlist(mode: str, coupling: float, points_per_decade: int,
                      band: list[float], *, bypass: bool = False) -> str:
    """Build the documented passive, assumed filter plus synthetic current source."""
    if mode not in ("dm", "cm"):
        raise SpiceModelError("Synthetic source mode must be dm or cm")
    if not 0 < coupling < 1:
        raise SpiceModelError("Choke coupling must be between zero and one")
    if points_per_decade < 1 or len(band) != 2 or not (0 < band[0] < band[1]):
        raise SpiceModelError("Invalid AC sweep")
    sources = (
        "Idm outl outn DC 0 AC 1u\n" if mode == "dm"
        else "Icm1 outl 0 DC 0 AC 1u\nIcm2 outn 0 DC 0 AC 1u\n"
    )
    filter_section = """* Reference: L1, C2 and RV1 removed; 1mOhm ideal-through links.
Rthroughl ntc outl 1m
Rthroughn isn outn 1m
""" if bypass else f"""* Nominal C2 100nF, RV1 440pF.
C2 ntc isn 100n
Crv ntc isn 440p
* L1 10mH per winding, assumed winding resistance and coupling.
Rwl ntc il 0.5
Lwl il outl 10m
Lwn isn in 10m
Rwn in outn 0.5
Kchoke Lwl Lwn {coupling:.8g}
"""
    return f"""Candidate filter AC sensitivity; all parameters assumed unless stated
* CISPR-style hypothetical network, not an asserted standard implementation.
* 50uH series 5ohm, supply-side 8uF, receiver coupling 250nF and 50ohm.
Llisl lin ls 50u
Rlisl ls supplyl 5
Clisl supplyl 0 8u
Llisn isn nins 50u
Rlisn nins supplyn 5
Clisn supplyn 0 8u
Rdc_l supplyl 0 1g
Rdc_n supplyn 0 1g
Clrecv lin lmeas 250n
Rlrecv lmeas 0 50
Cnrecv isn nmeas 250n
Rnrecv nmeas 0 50
* Hot R6 assumed 2ohm.
Rntc lin ntc 2
{filter_section}
* CY1 bridges isolated secondary rails, not PE; unknown module internals.
Ccy secondary1 secondary2 2.2n
Rsecondary secondary1 secondary2 1meg
Csecondary secondary2 0 100p
Rdc_secondary secondary2 0 1g
* Unknown primary/secondary coupling used only as illustrative assumption.
Ciso outn secondary1 100p
{sources}Rsource outl outn 100k
.control
set noaskquit
set wr_singlescale
set wr_vecnames
ac dec {points_per_decade} {band[0]:.12g} {band[1]:.12g}
wrdata response.dat v(lmeas) v(nmeas)
quit
.endc
.end
"""


def assumed_lisn_branch_impedance(frequency_hz: float) -> complex:
    """Input impedance of the exact modeled passive branch, not a standard limit."""
    if not math.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError("frequency must be finite and positive")
    s = 2j * math.pi * frequency_hz
    supply_branch = 5 + s * 50e-6 + 1 / (s * 8e-6 + 1e-9)
    receiver_branch = 50 + 1 / (s * 250e-9)
    return 1 / (1 / supply_branch + 1 / receiver_branch)


def assumed_lisn_branch_poles() -> list[complex]:
    """Finite poles of the modeled branch driving-point impedance."""
    try:
        import numpy as np
    except ImportError as exc:
        raise SpiceModelError("LISN pole analysis requires NumPy") from exc
    inductance, supply_cap, receiver_cap = 50e-6, 8e-6, 250e-9
    resistance, conductance = 55.0, 1e-9
    coefficients = [
        inductance * supply_cap * receiver_cap,
        (resistance * supply_cap + inductance * conductance) * receiver_cap,
        resistance * conductance * receiver_cap + receiver_cap + supply_cap,
        conductance,
    ]
    poles = [complex(root) for root in np.roots(coefficients)]
    for pole in poles:
        denominator = sum(abs(coefficient) * abs(pole) ** (3 - i)
                          for i, coefficient in enumerate(coefficients))
        if (pole.real > 1e-8 or not math.isfinite(pole.real) or
                not math.isfinite(pole.imag) or
                abs(np.polyval(coefficients, pole)) / denominator > 1e-10):
            raise SpiceModelError("Assumed LISN branch pole validation failed")
    return sorted(poles, key=lambda x: (x.real, x.imag))


def passive_circuit_analysis(netlist: str, frequencies_hz: list[float], *,
                             reference_ohm: float = 50.0,
                             reference_hz: float = 1e6) -> dict[str, Any]:
    """Solve the generated RLC circuit independently using descriptor MNA.

    The finite eigenvalues are natural modes with independent currents zeroed,
    not necessarily observable transfer-function poles or physical component poles.
    """
    try:
        import numpy as np
        import scipy
        import scipy.linalg as la
    except ImportError as exc:
        raise SpiceModelError("Candidate pole analysis requires NumPy and SciPy") from exc

    factors = {"": 1.0, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3,
               "u": 1e-6, "n": 1e-9, "p": 1e-12}

    def value(text: str) -> float:
        match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(meg|g|k|m|u|n|p)?",
                             text.casefold())
        if not match:
            raise SpiceModelError(f"Unsupported SPICE value in pole analysis: {text}")
        return float(match.group(1)) * factors[match.group(2) or ""]

    elements = []
    for line in netlist.splitlines()[1:]:
        line = line.strip()
        if line.casefold().startswith(".control"):
            break
        if not line or line.startswith("*"):
            continue
        fields = line.casefold().split()
        if fields[0][0] not in "rclki":
            raise SpiceModelError(f"Unsupported element in pole analysis: {line}")
        if len(fields) not in (4, 7) or (fields[0][0] == "i" and
                                           (len(fields) != 7 or fields[3:6] != ["dc", "0", "ac"])):
            raise SpiceModelError(f"Unsupported element syntax in pole analysis: {line}")
        elements.append(fields)
    if len({fields[0] for fields in elements}) != len(elements):
        raise SpiceModelError("Duplicate circuit element in pole analysis")
    nodes = sorted({node for fields in elements if fields[0][0] in "rcli"
                    for node in fields[1:3] if node != "0"})
    inductors = [fields for fields in elements if fields[0][0] == "l"]
    node_index = {node: i for i, node in enumerate(nodes)}
    inductor_index = {fields[0]: i for i, fields in enumerate(inductors)}
    n, m = len(nodes), len(inductors)
    g = np.zeros((n, n))
    c = np.zeros((n, n))
    l = np.zeros((m, m))
    b = np.zeros((n, m))
    source = np.zeros(n)

    def stamp(matrix: Any, first: str, second: str, number: float) -> None:
        for node1, sign1 in ((first, 1), (second, -1)):
            for node2, sign2 in ((first, 1), (second, -1)):
                if node1 != "0" and node2 != "0":
                    matrix[node_index[node1], node_index[node2]] += sign1 * sign2 * number

    for fields in elements:
        kind = fields[0][0]
        if kind in "rcl":
            number = value(fields[3])
            if not math.isfinite(number) or number <= 0:
                raise SpiceModelError("R, C and L must be finite and positive")
            if kind in "rc":
                stamp(g if kind == "r" else c, fields[1], fields[2],
                      1 / number if kind == "r" else number)
            else:
                index = inductor_index[fields[0]]
                l[index, index] = number
                for node, sign in ((fields[1], 1), (fields[2], -1)):
                    if node != "0":
                        b[node_index[node], index] += sign
        elif kind == "i":
            number = value(fields[6])
            for node, sign in ((fields[1], -1), (fields[2], 1)):
                if node != "0":
                    source[node_index[node]] += sign * number
    for fields in elements:
        if fields[0][0] == "k":
            try:
                i, j = inductor_index[fields[1]], inductor_index[fields[2]]
                coupling = value(fields[3])
            except KeyError as exc:
                raise SpiceModelError("Coupled inductor does not exist") from exc
            if i == j or not -1 < coupling < 1 or l[i, j] != 0:
                raise SpiceModelError("Invalid or duplicate mutual coupling")
            l[i, j] = l[j, i] = coupling * math.sqrt(l[i, i] * l[j, j])
    if m == 0 or np.min(la.eigvalsh(l)) <= 0:
        raise SpiceModelError("Inductance matrix must be positive definite")
    if not all(name in node_index for name in ("lmeas", "nmeas")):
        raise SpiceModelError("Receiver nodes are required")
    if any(not math.isfinite(f) or f <= 0 for f in frequencies_hz):
        raise SpiceModelError("Pole validation frequencies must be positive and finite")

    if not (math.isfinite(reference_ohm) and reference_ohm > 0 and
            math.isfinite(reference_hz) and reference_hz > 0):
        raise SpiceModelError("Descriptor reference scales must be finite and positive")
    # Dimensionless scaling: V=1 V, I=V/reference_ohm, s=2*pi*reference_hz.
    omega0 = 2 * math.pi * reference_hz
    a = np.block([[reference_ohm * g, b], [b.T, np.zeros((m, m))]])
    e = np.block([[reference_ohm * omega0 * c, np.zeros((n, m))],
                  [np.zeros((m, n)), -omega0 * l / reference_ohm]])
    # Eliminate algebraic coordinates before QZ: near-zero beta values in the
    # unreduced descriptor pencil can otherwise masquerade as enormous poles.
    u, singular, vh = la.svd(e)
    tolerance = max(e.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    if rank == 0:
        raise SpiceModelError("Descriptor circuit has no dynamic states")
    transformed = u.T @ a @ vh.T
    a11, a12 = transformed[:rank, :rank], transformed[:rank, rank:]
    a21, a22 = transformed[rank:, :rank], transformed[rank:, rank:]
    try:
        reduced = a11 - a12 @ la.solve(a22, a21) if a22.size else a11
        ered = np.diag(singular[:rank])
        values, vectors = la.eig(-reduced, ered)
    except la.LinAlgError as exc:
        raise SpiceModelError(f"Descriptor reduction or eigenvalue solve failed: {exc}") from exc
    finite = np.isfinite(values)
    if not np.all(finite):
        raise SpiceModelError("Reduced descriptor produced non-finite natural modes")
    poles = []
    max_residual = 0.0
    for index in np.flatnonzero(finite):
        pole = values[index]
        vector = vectors[:, index]
        residual = la.norm((reduced + pole * ered) @ vector) / (
            (la.norm(reduced) + abs(pole) * la.norm(ered)) * la.norm(vector)
        )
        max_residual = max(max_residual, float(residual))
        actual = pole * omega0
        if actual.real > 1e-5:
            raise SpiceModelError(f"Passive circuit has an unstable calculated mode: {actual}")
        poles.append({"real_rad_s": float(actual.real),
                      "imag_rad_s": float(actual.imag),
                      "oscillation_hz": float(abs(actual.imag) / (2 * math.pi)),
                      "eigen_residual": float(residual)})
    if max_residual > 1e-8:
        raise SpiceModelError(f"Descriptor pole residual too large: {max_residual}")
    responses = []
    max_ac_residual = 0.0
    for frequency in frequencies_hz:
        mat = np.block([[g + 2j * math.pi * frequency * c, b],
                        [b.T, -2j * math.pi * frequency * l]])
        try:
            rhs = np.r_[source, np.zeros(m)]
            answer = la.solve(mat, rhs)
        except la.LinAlgError as exc:
            raise SpiceModelError(f"Independent AC solution failed: {exc}") from exc
        residual = la.norm(mat @ answer - rhs) / (
            la.norm(mat) * la.norm(answer) + la.norm(rhs)
        )
        max_ac_residual = max(max_ac_residual, float(residual))
        responses.append([complex(answer[node_index[name]]) for name in ("lmeas", "nmeas")])
    if max_ac_residual > 1e-8:
        raise SpiceModelError(f"Independent AC residual too large: {max_ac_residual}")
    return {"poles": sorted(poles, key=lambda x: (x["oscillation_hz"], x["real_rad_s"])),
            "algebraic_coordinates_eliminated": len(singular) - rank,
            "max_eigen_residual": max_residual, "max_ac_residual": max_ac_residual,
            "responses": responses,
            "reference_ohm": reference_ohm, "reference_hz": reference_hz,
            "numpy_version": np.__version__, "scipy_version": scipy.__version__}


def run_ngspice(
    netlist_path: Path,
    run_directory: Path,
    *,
    executable: str = "ngspice",
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a supplied batch netlist in a new run directory; never fabricate data."""
    netlist_path = netlist_path.resolve()
    run_directory = run_directory.resolve()
    binary = _find_ngspice(executable)
    if binary is None:
        raise SpiceModelError(
            f"ngspice executable {executable!r} was not found; no simulation was run"
        )
    if not netlist_path.is_file():
        raise SpiceModelError(f"Netlist does not exist: {netlist_path}")
    if run_directory.exists():
        raise SpiceModelError(f"Refusing to overwrite run directory: {run_directory}")
    run_directory.mkdir(parents=True)
    log_path = run_directory / "ngspice.log"
    command = [binary, "-b", "-o", str(log_path), str(netlist_path)]
    try:
        result = subprocess.run(
            command,
            cwd=run_directory,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpiceModelError(f"Could not run ngspice: {exc}") from exc
    (run_directory / "ngspice_stdout.log").write_text(result.stdout, encoding="utf-8")
    (run_directory / "ngspice_stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise SpiceModelError(
            f"ngspice exited with status {result.returncode}; see {run_directory}"
        )
    return result


def ngspice_version(
    *,
    executable: str = "ngspice",
    timeout_seconds: float = 10.0,
) -> str:
    """Return the external ngspice version string or raise an explicit error."""
    binary = _find_ngspice(executable)
    if binary is None:
        raise SpiceModelError(
            f"ngspice executable {executable!r} was not found; no simulation was run"
        )
    try:
        result = subprocess.run(
            [binary, "-v"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SpiceModelError(f"Could not query ngspice version: {exc}") from exc
    if result.returncode:
        raise SpiceModelError(
            f"ngspice version query exited with status {result.returncode}"
        )
    version_text = result.stdout.strip() or result.stderr.strip()
    if not version_text:
        raise SpiceModelError("ngspice version query returned no version text")
    return next(
        (line.strip(" *") for line in version_text.splitlines()
         if re.search(r"\bngspice[- ]\d", line, re.IGNORECASE)),
        version_text.splitlines()[0],
    )


def parallel_rl_impedance(
    frequency_hz: float,
    inductance_h: float,
    resistance_ohm: float,
) -> complex:
    """Calculate Z of a user-specified ideal parallel R-L branch.

    This is only an elementary circuit calculation, not a standardized LISN
    model. The user must provide and justify all values and surrounding
    topology for an applicable test network.
    """
    values = (frequency_hz, inductance_h, resistance_ohm)
    if any(
        isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or value <= 0
        for value in values
    ):
        raise ValueError("frequency, inductance, and resistance must be finite and positive")
    omega_l = 2.0 * math.pi * frequency_hz * inductance_h
    if not math.isfinite(omega_l):
        raise ValueError("parallel R-L reactance is outside the representable range")
    impedance = 1.0 / (1.0 / resistance_ohm + 1.0 / complex(0.0, omega_l))
    if not (math.isfinite(impedance.real) and math.isfinite(impedance.imag)):
        raise ValueError("parallel R-L impedance is outside the representable range")
    return impedance
