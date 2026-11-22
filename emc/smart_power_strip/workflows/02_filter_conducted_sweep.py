"""Run a configured ngspice sensitivity case only after provenance gates pass."""

from __future__ import annotations

import argparse
from bisect import bisect_left
import math
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

EMC_ROOT = Path(__file__).resolve().parents[2]
if str(EMC_ROOT) not in sys.path:
    sys.path.insert(0, str(EMC_ROOT))

from emc_sim.manifest import ManifestError, sha256_file, verify_manifest
from emc_sim.reporting import write_report, write_run_metadata
from emc_sim.spice_conducted import (
    CANDIDATE_STAMP,
    SpiceModelError,
    attenuation_db,
    assumed_lisn_branch_impedance,
    assumed_lisn_branch_poles,
    candidate_netlist,
    load_conducted_config,
    ngspice_version,
    passive_circuit_analysis,
    run_ngspice,
    validate_candidate_scenario,
)


def run_candidate(config: dict, config_path: Path, app_root: Path, manifest: dict) -> Path:
    """Run bounded synthetic-source cases without asserting revision linkage."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    input_root = (app_root / "inputs" / "locked_rev").resolve()
    candidate = Path(config["_resolved_candidate_dir"])
    stackup = Path(config["_resolved_stackup_metadata"])
    for path in (candidate, stackup):
        if input_root not in path.parents:
            raise SpiceModelError(f"Candidate input outside locked_rev: {path}")
    files = sorted(path for path in candidate.rglob("*") if path.is_file())
    if not files:
        raise SpiceModelError("Candidate directory contains no files")
    bom = input_root / "BOM_MAIN_OMRON_PCB_MAIN_OMRON_2026-11-19.csv"
    if not bom.is_file():
        raise SpiceModelError(f"Candidate comparison BOM unavailable: {bom}")

    spice_version = ngspice_version()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = app_root / "runs" / "conducted_spice" / run_id
    output.mkdir(parents=True, exist_ok=False)
    band = config["frequency_band_hz"]
    cases = (("dm_k095", "dm", 0.95, False), ("dm_k099", "dm", 0.99, False),
             ("dm_k0999", "dm", 0.999, False), ("cm_k099", "cm", 0.99, False),
             ("dm_bypass", "dm", 0.99, True), ("cm_bypass", "cm", 0.99, True))
    results = {}
    convergence = {}
    for name, mode, coupling, bypass in cases:
        grids = []
        for density in (10240, 40960):
            netlist = output / f"{name}_{density}.cir"
            netlist.write_text(candidate_netlist(mode, coupling, density, band, bypass=bypass), encoding="ascii")
            directory = output / f"{name}_{density}"
            run_ngspice(netlist, directory)
            log = (directory / "ngspice.log").read_text(encoding="utf-8", errors="replace")
            if any(word in log.casefold() for word in
                   ("error:", "fatal", "convergence failed", "singular matrix",
                    "stepping failed", "timestep too small")):
                raise SpiceModelError(f"ngspice reported an error in {directory}")
            try:
                rows = [
                    [float(value) for value in line.split()]
                    for line in (directory / "response.dat").read_text().splitlines()[1:]
                    if line.strip()
                ]
            except (OSError, ValueError) as exc:
                raise SpiceModelError(f"Invalid AC data in {directory}: {exc}") from exc
            if len(rows) < 2 or any(len(row) != 5 or not all(math.isfinite(x) for x in row) for row in rows):
                raise SpiceModelError(f"Malformed or non-finite AC data in {directory}")
            if any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
                raise SpiceModelError(f"Non-monotonic frequency data in {directory}")
            expected_count = math.floor(math.log10(band[1] / band[0]) * density) + 1
            if (len(rows) < expected_count or not math.isclose(rows[0][0], band[0], rel_tol=1e-6)
                    or rows[-1][0] < band[1] * (1 - 3 / density)
                    or rows[-1][0] > band[1] * 1.01):
                raise SpiceModelError(f"Incomplete AC sweep in {directory}")
            rows = [row for row in rows if row[0] <= band[1]]
            grids.append(rows)
        coarse, fine = grids
        if len(fine) < 4 * len(coarse) - 8:
            raise SpiceModelError(f"Incomplete fine grid for {name}")
        differences = []
        frequencies = [row[0] for row in fine]
        for row in coarse:
            index = bisect_left(frequencies, row[0])
            if index == 0 or index == len(fine):
                continue
            lower, upper = fine[index - 1], fine[index]
            fraction = (row[0] - lower[0]) / (upper[0] - lower[0])
            for column in (1, 3):
                a = complex(row[column], row[column + 1])
                lo = complex(lower[column], lower[column + 1])
                hi = complex(upper[column], upper[column + 1])
                b = lo + fraction * (hi - lo)
                differences.append(abs(a - b) / max(abs(a), abs(b), 1e-18))
        if not differences:
            raise SpiceModelError(f"AC grids do not overlap for {name}")
        max_change = max(differences)
        if max_change > 0.05:
            raise SpiceModelError(f"AC grid consistency failed for {name}: {max_change}")
        peak_changes = {}
        for column, conductor in ((1, "L"), (3, "N")):
            maxima = [max(abs(complex(r[column], r[column + 1])) for r in grid) for grid in grids]
            peak_changes[conductor] = abs(20 * math.log10(max(maxima[1], 1e-18) / max(maxima[0], 1e-18)))
        convergence[name] = {"max_relative_complex_change": max_change,
                             "sampled_peak_change_db": peak_changes,
                             "sampled_peak_stable_0_2db": max(peak_changes.values()) <= 0.2,
                             "note": "Grid sampling check only, not component-model validation."}
        results[name] = fine

    pole_analysis = {}
    low_band = [1000, 100000]
    for name, mode, coupling, bypass in cases:
        if bypass:
            continue
        low_netlist = output / f"{name}_low_frequency.cir"
        low_text = candidate_netlist(mode, coupling, 160, low_band)
        low_netlist.write_text(low_text, encoding="ascii")
        low_directory = output / f"{name}_low_frequency"
        run_ngspice(low_netlist, low_directory)
        log = (low_directory / "ngspice.log").read_text(encoding="utf-8", errors="replace")
        if any(word in log.casefold() for word in
               ("error:", "fatal", "convergence failed", "singular matrix",
                "stepping failed", "timestep too small")):
            raise SpiceModelError(f"ngspice reported an error in {low_directory}")
        try:
            low_rows = [[float(v) for v in line.split()] for line in
                        (low_directory / "response.dat").read_text().splitlines()[1:] if line.strip()]
        except (OSError, ValueError) as exc:
            raise SpiceModelError(f"Invalid low-frequency AC data: {exc}") from exc
        if (len(low_rows) < 321 or
                any(len(row) != 5 or not all(math.isfinite(x) for x in row) for row in low_rows) or
                any(a[0] >= b[0] for a, b in zip(low_rows, low_rows[1:])) or
                not math.isclose(low_rows[0][0], low_band[0], rel_tol=1e-6) or
                low_rows[-1][0] < low_band[1] * 0.99 or
                low_rows[-1][0] > low_band[1] * 1.01):
            raise SpiceModelError(f"Incomplete or invalid low-frequency AC data: {low_directory}")
        high_rows = results[name]
        high_frequencies = [row[0] for row in high_rows]
        low_frequencies = [row[0] for row in low_rows]
        high_peak_l = max(high_rows, key=lambda row: abs(complex(row[1], row[2])))
        high_peak_n = max(high_rows, key=lambda row: abs(complex(row[3], row[4])))
        sample_rows = [
            low_rows[0], low_rows[bisect_left(low_frequencies, 47844)],
            low_rows[-1], high_rows[0], high_peak_l, high_peak_n,
            high_rows[min(bisect_left(high_frequencies, 1e6), len(high_rows) - 1)],
            high_rows[-1],
        ]
        analysis = passive_circuit_analysis(low_text, [row[0] for row in sample_rows])
        responses = analysis.pop("responses")
        rescaled = passive_circuit_analysis(low_text, [], reference_ohm=100,
                                            reference_hz=100000)
        primary_modes = [complex(p["real_rad_s"], p["imag_rad_s"])
                         for p in analysis["poles"] if p["imag_rad_s"] > 0]
        rescaled_modes = [complex(p["real_rad_s"], p["imag_rad_s"])
                          for p in rescaled["poles"] if p["imag_rad_s"] > 0]
        if len(primary_modes) != len(rescaled_modes):
            raise SpiceModelError(f"Oscillatory mode count changes under scaling for {name}")
        scale_error = max((abs(a - b) / max(abs(a), abs(b), 1e-18)
                           for a, b in zip(primary_modes, rescaled_modes)), default=0.0)
        if scale_error > 1e-5:
            raise SpiceModelError(f"Oscillatory poles are scale-sensitive for {name}: {scale_error}")
        comparisons = []
        for row, expected in zip(sample_rows, responses):
            for col, conductor, model_value in zip((1, 3), ("L", "N"), expected):
                spice_value = complex(row[col], row[col + 1])
                error = abs(model_value - spice_value) / max(abs(model_value), abs(spice_value), 1e-18)
                comparisons.append({"frequency_hz": row[0], "conductor": conductor,
                                    "relative_complex_error": error})
        max_error = max(item["relative_complex_error"] for item in comparisons)
        if max_error > 1e-4:
            raise SpiceModelError(f"Independent MNA/ngspice AC comparison failed for {name}: {max_error}")
        analysis["ngspice_ac_comparisons"] = comparisons
        analysis["max_ngspice_relative_complex_error"] = max_error
        analysis["alternate_scaling"] = {
            "reference_ohm": 100, "reference_hz": 100000,
            "max_oscillatory_pole_relative_difference": scale_error,
            "max_eigen_residual": rescaled["max_eigen_residual"],
        }
        analysis["method"] = (
            "RLC netlist parsed into scaled modified nodal descriptor matrices; "
            "SVD removes algebraic coordinates, Schur reduction and generalized "
            "eigenanalysis yield finite natural modes. Sources are zeroed for poles."
        )
        pole_analysis[name] = analysis

    lisn_poles = [{"real_rad_s": p.real, "imag_rad_s": p.imag,
                   "oscillation_hz": abs(p.imag) / (2 * math.pi)}
                  for p in assumed_lisn_branch_poles()]
    lisn_impedances = []
    for frequency in (150000, 1000000, 30000000):
        z = assumed_lisn_branch_impedance(frequency)
        lisn_impedances.append({"frequency_hz": frequency, "real_ohm": z.real,
                                "imag_ohm": z.imag, "magnitude_ohm": abs(z)})

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    for name, mode, _, bypass in cases:
        if bypass:
            continue
        rows = results[name]
        reference = results[f"{mode}_bypass"]
        for ax, col, conductor in zip(axes, (1, 3), ("L", "N")):
            ax.semilogx([r[0] for r in rows],
                        attenuation_db(rows, reference, col),
                        label=name)
            ax.set_ylabel(f"{conductor} attenuation (dB)")
            ax.grid(True, which="both")
            ax.legend()
    axes[-1].set_xlabel("Frequency (Hz)")
    fig.suptitle(CANDIDATE_STAMP, fontsize=9)
    fig.savefig(output / "candidate_attenuation.png", dpi=150)
    plt.close(fig)
    hashes = {str(path.relative_to(app_root)): sha256_file(path) for path in [*files, stackup, bom]}
    hashes[str(config_path.relative_to(app_root))] = sha256_file(config_path)
    hashes[str(Path(__file__).resolve().relative_to(EMC_ROOT))] = sha256_file(Path(__file__))
    hashes["emc_sim/spice_conducted.py"] = sha256_file(EMC_ROOT / "emc_sim" / "spice_conducted.py")
    generated_hashes = {path.name: sha256_file(path) for path in output.glob("*.cir")}
    peaks = {}
    for name, rows in results.items():
        peaks[name] = {}
        for column, conductor in ((1, "L"), (3, "N")):
            row = max(rows, key=lambda r: abs(complex(r[column], r[column + 1])))
            magnitude = abs(complex(row[column], row[column + 1]))
            peaks[name][conductor] = {
                "frequency_hz": row[0],
                "dbuv": 20 * math.log10(max(magnitude, 1e-18) / 1e-6),
            }
    assumptions = [
        f"Candidate folder: {candidate}; November 21 exports are not linked to the native archive or November 19 BOM and stackup.",
        "The candidate scenario is fixed in code; the config's source, network, component and sweep descriptions were checked for exact agreement, not used as parameter overrides.",
        f"Manifest inputs were hash-verified; manifest locked={manifest['locked']}, revision={manifest['revision']}. Candidate artifacts are independently hashed, not asserted to be in the manifest or revision-matched.",
        f"Stackup metadata: {stackup}; no PCB geometry or stackup is used in this lumped circuit model.",
        "User-selected BOM claims L1 UU9.8-10mH, C2 100nF X2, CY1 2.2nF Y1, R6 10D-7, RV1 14D431K ~440pF; fitted values and datasheets not verified.",
        "C2 and RV1 are on the input side of L1; CY1 bridges secondary rails, not PE. Unknown converter internals are not modeled.",
        "Assumed two 10mH windings, k=0.95, 0.99 or 0.999, 0.5 ohm each; R6 hot resistance 2 ohm; RV1 represented only as 440pF. No fuse impedance, nonlinear surge behavior or frequency-dependent parasitics.",
        "Assumed 100pF primary-secondary coupling, 100pF secondary-to-reference capacitance, 1Mohm secondary leakage, 100kohm primary source shunt and 1Gohm DC anchors; these are synthetic, not measured.",
        "Synthetic DM 1µA between primary terminals or CM 1µA per terminal to reference; equal phase. No converter/source spectrum is known.",
        "Bypass reference removes L1, C2 and RV1 and replaces L1 with 1mohm links; R6, source, LISNs, CY1 and assumed coupling remain. Attenuation is 20log10(|V_bypass|/|V_filtered|), separately at each receiver; negative values mean modeled amplification.",
        "Each assumed CISPR-style network branch uses 50µH series 5ohm, supply-side 8µF to reference, receiver 250nF series 50ohm; standard applicability and impedance tolerance are unverified.",
        f"Source provenance: {config['source']['provenance']}. Network provenance: {config['measurement_network']['provenance']}.",
    ]
    metadata = {
        "classification": CANDIDATE_STAMP, "candidate_dir": str(candidate),
        "source_hashes": hashes, "solver": "ngspice", "solver_version": spice_version,
        "manifest_sha256": sha256_file(app_root / "configs" / "revision_manifest.json"),
        "manifest_project_id": manifest["project_id"], "manifest_revision": manifest["revision"],
        "manifest_locked": manifest["locked"],
        "manifest_source_hashes": {entry["path"]: entry["sha256"] for entry in manifest["files"]},
        "source": config["source"], "measurement_network": config["measurement_network"],
        "frequency_band_hz": band, "assumptions": assumptions, "scenarios": list(results),
        "ac_grid_consistency": convergence,
        "generated_netlist_sha256": generated_hashes, "sampled_peaks": peaks,
        "full_synthetic_circuit_natural_modes": pole_analysis,
        "assumed_lisn_branch": {
            "method": "Driving-point Z=(Zs*Zr)/(Zs+Zr), Zs=5+s*50uH+1/(s*8uF+1/1Gohm), Zr=50+1/(s*250nF); polynomial roots are finite impedance poles.",
            "finite_impedance_poles": lisn_poles, "calculated_impedances": lisn_impedances,
        },
        "passive_network_check": "Generated R/L/C values are positive and mutual coupling satisfies |k|<1; no Touchstone network is used or validated.",
        "measurements": [],
    }
    write_run_metadata(output, metadata)
    write_report(
        output, question=CANDIDATE_STAMP + "\n\nHow do assumed choke coupling and synthetic CM/DM currents affect modeled receiver voltages?",
        evidence={"assumptions": assumptions, "calculations": [
            "Full synthetic circuit natural modes, not physical filter poles: " + str({
                key: [{"real_rad_s": p["real_rad_s"], "imag_rad_s": p["imag_rad_s"],
                       "oscillation_hz": p["oscillation_hz"]}
                      for p in analysis["poles"] if p["imag_rad_s"] > 0]
                for key, analysis in pole_analysis.items()
            }) + ". Negative imaginary conjugates and real modes are in run_metadata.json.",
            "Method: scaled RLC modified nodal descriptor; SVD/Schur algebraic reduction and generalized eigensolve. Frequencies are |Im(s)|/(2π), damping is Re(s) in rad/s; independent 1 kHz–100 kHz ngspice runs and in-band complex responses cross-check the same parsed network. Eigen residuals, alternate scaling comparison, and AC errors are recorded in run_metadata.json.",
            f"Assumed standalone LISN branch impedance poles (rad/s): {lisn_poles}. Calculated branch impedances: {lisn_impedances} ohms; no standard tolerance comparison.",
        ], "simulations": [
            "Attenuation curves compare same-mode filtered and bypass receiver phasors; see candidate_attenuation.png and response.dat files.",
            f"Interpolated 10240/40960-point-per-decade grid and sampled-peak checks: {convergence}.",
            f"Candidate resonance indicators: maximum sampled receiver magnitude and corresponding grid frequency for each filtered case (dBµV, Hz): { {key: value for key, value in peaks.items() if not key.endswith('_bypass')} }. These are response maxima, not identified circuit poles; a band-edge maximum is not evidence of a resonance.",
        ], "measurements": []},
        result="Synthetic sensitivity only; not predicted product emissions, compliance, or test margin.",
        limitations=["No validated converter model, component parasitics, applicable LISN, receiver detector, wiring, layout or enclosure.",
                     "Physical filter poles cannot be established from the assumed windings, coupling, parasitics, source and terminations. Full-circuit modes need not be observable at every port and cannot be attributed to L1 or any physical filter alone.",
                     "Grid consistency does not establish model accuracy or resolve all resonances; no S-parameter network was generated.",
                     "No physical testing is authorized by this simulation."],
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=EMC_ROOT / "smart_power_strip" / "configs" / "conducted_filter.yaml",
    )
    parser.add_argument(
        "--allow-candidate", action="store_true",
        help="Explicitly allow exploratory candidate inputs; manifest hashes are still verified.",
    )
    args = parser.parse_args()
    app_root = EMC_ROOT / "smart_power_strip"
    try:
        config_path = args.config.resolve()
        config_root = (app_root / "configs").resolve()
        try:
            relative_config = config_path.relative_to(config_root)
        except ValueError as exc:
            raise SpiceModelError(
                "conducted model config must be under smart_power_strip/configs"
            ) from exc
        config = load_conducted_config(config_path)
        if config.get("mode") == "candidate":
            if not args.allow_candidate:
                raise SpiceModelError("candidate config requires --allow-candidate")
            manifest = verify_manifest(
                app_root / "configs" / "revision_manifest.json",
                allow_candidate=args.allow_candidate, input_root=app_root,
            )
            validate_candidate_scenario(config)
            run_directory = run_candidate(config, config_path, app_root, manifest)
            print(f"{CANDIDATE_STAMP}\nResults: {run_directory}")
            return 0
        manifest = verify_manifest(
            app_root / "configs" / "revision_manifest.json",
            input_root=app_root,
        )
        netlist_path = Path(config["_resolved_netlist"]).resolve()
        locked_input_root = (app_root / "inputs" / "locked_rev").resolve()
        try:
            locked_relative_netlist = netlist_path.relative_to(locked_input_root)
        except ValueError as exc:
            raise SpiceModelError(
                "configured netlist must be inside smart_power_strip/inputs/locked_rev"
            ) from exc
        relative_netlist = (
            Path("inputs") / "locked_rev" / locked_relative_netlist
        )
        manifested_paths = {
            Path(entry["path"]).as_posix().casefold()
            for entry in manifest["files"]
        }
        if relative_netlist.as_posix().casefold() not in manifested_paths:
            raise SpiceModelError(
                "configured netlist is not listed in the revision manifest: "
                f"{relative_netlist.as_posix()}"
            )
        spice_version = ngspice_version()
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=EMC_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=EMC_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_directory = app_root / "runs" / "conducted_spice" / run_id
        result = run_ngspice(
            netlist_path,
            run_directory,
        )
        input_hashes = {
            entry["path"]: entry["sha256"] for entry in manifest["files"]
        }
        input_hashes[
            (Path("configs") / relative_config).as_posix()
        ] = sha256_file(config_path)
        run_metadata = {
            "scope": "user-supplied ngspice netlist run; no standards-receiver analysis",
            "project_id": manifest["project_id"],
            "revision": manifest["revision"],
            "git_commit": git_commit,
            "worktree_dirty": bool(git_status.strip()),
            "solver": "ngspice",
            "solver_version": spice_version,
            "solver_status": "completed",
            "exit_code": result.returncode,
            "source_hashes": input_hashes,
            "manifest_sha256": sha256_file(
                app_root / "configs" / "revision_manifest.json"
            ),
            "workflow_sha256": sha256_file(Path(__file__)),
            "netlist_sha256": sha256_file(netlist_path),
            "tool_versions": {
                "python": sys.version.split()[0],
                "ngspice": spice_version,
                "pyyaml": version("PyYAML"),
            },
            "frequency_band_hz": config["frequency_band_hz"],
            "source": config["source"],
            "measurement_network": config["measurement_network"],
            "artifacts_before_metadata": sorted(
                path.name for path in run_directory.iterdir()
            ),
            "measurements": [],
        }
        write_run_metadata(run_directory, run_metadata)
        write_report(
            run_directory,
            question="What circuit response does the supplied netlist produce for the explicitly configured source and measurement network?",
            evidence={
                "assumptions": [
                    f"Source: {config['source']['provenance']}",
                    f"Measurement network: {config['measurement_network']['provenance']}",
                ],
                "calculations": [],
                "simulations": [
                    f"ngspice exited with status {result.returncode}; inspect the saved logs and netlist outputs."
                ],
                "measurements": [],
            },
            result=(
                "The configured netlist completed. This workflow does not "
                "interpret its outputs as emissions or certification data."
            ),
            limitations=[
                "Netlist topology and device models are supplied inputs and are not independently validated.",
                "Transient FFT data are not equivalent to a standards receiver measurement.",
                "A configured circuit network does not establish an applicable LISN/AMN or product test setup.",
            ],
        )
    except (ManifestError, SpiceModelError, OSError) as exc:
        parser.exit(2, f"Conducted sweep blocked: {exc}\n")
    except subprocess.CalledProcessError as exc:
        parser.exit(2, f"Conducted sweep blocked: git provenance query failed: {exc}\n")
    print(f"ngspice completed; inspect and label outputs in {run_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
