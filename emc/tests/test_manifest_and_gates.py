import hashlib
import json

import pytest

from emc_sim.manifest import ManifestError, verify_manifest
from emc_sim.openems_runner import OpenEMSError, compare_mesh_values, validate_run_metadata


def _write_manifest(tmp_path, *, locked=True, content=b"matched inputs"):
    source = tmp_path / "input.bin"
    source.write_bytes(content)
    manifest = {
        "schema_version": 1,
        "project_id": "smart-plug-test",
        "revision": "rev-a",
        "locked": locked,
        "files": [
            {
                "path": source.name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "revision": "rev-a",
            }
        ],
    }
    path = tmp_path / "revision_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, source, manifest


def test_manifest_verifies_locked_revision_hashes(tmp_path):
    path, _, expected = _write_manifest(tmp_path)
    assert verify_manifest(path) == expected


def test_manifest_can_resolve_paths_from_application_root(tmp_path):
    app_root = tmp_path / "application"
    config_dir = app_root / "configs"
    input_dir = app_root / "inputs" / "locked_rev"
    config_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)
    payload = b"matched gerber"
    (input_dir / "top.gbr").write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "project_id": "smart-plug-test",
        "revision": "rev-b",
        "locked": True,
        "files": [
            {
                "path": "inputs/locked_rev/top.gbr",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    }
    manifest_path = config_dir / "revision_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_manifest(manifest_path, input_root=app_root) == manifest


def test_manifest_blocks_unlocked_or_hash_mismatch(tmp_path):
    path, source, manifest = _write_manifest(tmp_path, locked=False)
    with pytest.raises(ManifestError, match="not locked"):
        verify_manifest(path)
    manifest["locked"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")
    source.write_bytes(b"changed input")
    with pytest.raises(ManifestError, match="SHA-256 mismatch"):
        verify_manifest(path)


@pytest.mark.parametrize("relative", ["..\\escape.bin", "../escape.bin", "C:\\outside.bin"])
def test_manifest_rejects_paths_outside_manifest_root(tmp_path, relative):
    path = tmp_path / "revision_manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "smart-plug-test",
                "revision": "rev-a",
                "locked": True,
                "files": [{"path": relative, "sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="relative path|input root"):
        verify_manifest(path)


def test_manifest_rejects_cross_revision_input(tmp_path):
    path, _, manifest = _write_manifest(tmp_path)
    manifest["files"][0]["revision"] = "rev-b"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="different revision"):
        verify_manifest(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_id", "TODO_VERIFY_FROM_STAGE_0", "project_id"),
        ("revision", "UNCONFIRMED", "revision"),
    ],
)
def test_manifest_rejects_placeholder_project_identity(tmp_path, field, value, message):
    path, _, manifest = _write_manifest(tmp_path)
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match=message):
        verify_manifest(path)


def test_openems_gate_requires_energy_and_mesh_convergence(tmp_path):
    path = tmp_path / "run_metadata.json"
    base = {
        "solver_status": "end_criteria_reached",
        "solver_end_criteria_reached": True,
        "timestep_count": 1200,
        "maximum_timestep_limit": 5000,
        "mesh_convergence": {"passed": True},
    }
    path.write_text(json.dumps(base), encoding="utf-8")
    assert validate_run_metadata(path)["timestep_count"] == 1200
    base["solver_status"] = "unconverged_max_timesteps"
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(OpenEMSError, match="energy end criterion"):
        validate_run_metadata(path)
    base["solver_status"] = "end_criteria_reached"
    base["mesh_convergence"]["passed"] = False
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(OpenEMSError, match="Mesh convergence"):
        validate_run_metadata(path)


def test_openems_gate_can_explicitly_check_energy_only(tmp_path):
    path = tmp_path / "run_metadata.json"
    path.write_text(
        json.dumps(
            {
                "solver_status": "end_criteria_reached",
                "solver_end_criteria_reached": True,
                "timestep_count": 10,
                "maximum_timestep_limit": 100,
            }
        ),
        encoding="utf-8",
    )
    assert validate_run_metadata(path, require_mesh_convergence=False)


def test_openems_gate_can_require_boundary_convergence(tmp_path):
    path = tmp_path / "run_metadata.json"
    base = {
        "solver_status": "end_criteria_reached",
        "solver_end_criteria_reached": True,
        "timestep_count": 10,
        "maximum_timestep_limit": 100,
        "mesh_convergence": {"passed": True},
        "boundary_convergence": {"passed": False},
    }
    path.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(OpenEMSError, match="Boundary convergence"):
        validate_run_metadata(path, require_boundary_convergence=True)
    base["boundary_convergence"]["passed"] = True
    path.write_text(json.dumps(base), encoding="utf-8")
    assert validate_run_metadata(path, require_boundary_convergence=True)


def test_openems_gate_rejects_invalid_energy_metadata(tmp_path):
    path = tmp_path / "run_metadata.json"
    path.write_text(
        json.dumps(
            {
                "solver_status": "end_criteria_reached",
                "solver_end_criteria_reached": True,
                "timestep_count": 10,
                "maximum_timestep_limit": 100,
                "final_energy_to_sampled_peak_energy_ratio": float("nan"),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OpenEMSError, match="final_energy"):
        validate_run_metadata(path, require_mesh_convergence=False)


def test_mesh_comparison_uses_caller_selected_tolerance():
    assert compare_mesh_values(2.0, 2.01, relative_tolerance=0.01) == pytest.approx(
        0.01 / 2.01
    )
    with pytest.raises(OpenEMSError, match="exceeding"):
        compare_mesh_values(1.0, 1.1, relative_tolerance=0.05)
