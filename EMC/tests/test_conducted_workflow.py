import copy
import importlib.util
from pathlib import Path
import sys

import pytest

from emc_sim import manifest as manifest_module
from emc_sim.spice_conducted import SpiceModelError, validate_candidate_scenario


EMC_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = EMC_ROOT / "smart_power_strip" / "workflows" / "02_filter_conducted_sweep.py"
SPEC = importlib.util.spec_from_file_location("conducted_workflow", WORKFLOW)
assert SPEC is not None and SPEC.loader is not None
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)
@pytest.fixture
def candidate_config():
    parent = EMC_ROOT / "smart_power_strip" / "inputs" / "locked_rev" / "MAIN_OMRON"
    return {
        "mode": "candidate",
        "source_revision": "MAIN_OMRON_MCP_CANDIDATE_20261121_1753",
        "candidate_dir": "candidate",
        "stackup_metadata": "stackup",
        "_resolved_candidate_dir": str(parent / "MCP_CANDIDATE_20261121_1753"),
        "_resolved_stackup_metadata": str(parent / "MCP_LIVE_20261119_203444_LayerStackup.json"),
        "frequency_band_hz": [150000, 30000000],
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


def test_candidate_requires_explicit_opt_in(monkeypatch, candidate_config, capsys):
    monkeypatch.setattr(sys, "argv", [str(WORKFLOW)])
    monkeypatch.setattr(workflow, "load_conducted_config", lambda _: candidate_config)
    monkeypatch.setattr(workflow, "verify_manifest", lambda *a, **k: pytest.fail("manifest should not be reached"))
    monkeypatch.setattr(workflow, "run_candidate", lambda *a: pytest.fail("simulation should not run"))
    with pytest.raises(SystemExit) as exc:
        workflow.main()
    assert exc.value.code == 2
    assert "requires --allow-candidate" in capsys.readouterr().err


def test_candidate_verifies_manifest_before_simulation(monkeypatch, candidate_config):
    monkeypatch.setattr(sys, "argv", [str(WORKFLOW), "--allow-candidate"])
    monkeypatch.setattr(workflow, "load_conducted_config", lambda _: candidate_config)
    calls = []
    checked = {"locked": False}
    monkeypatch.setattr(workflow, "verify_manifest",
                        lambda path, **kwargs: calls.append((path, kwargs)) or checked)
    monkeypatch.setattr(workflow, "run_candidate", lambda config, path, root, manifest:
                        calls.append(("run", manifest)) or root / "runs" / "example")
    assert workflow.main() == 0
    assert calls[0][1] == {"allow_candidate": True, "input_root": EMC_ROOT / "smart_power_strip"}
    assert calls[1] == ("run", checked)


def test_candidate_rejects_bad_manifest_hash_even_with_opt_in(monkeypatch, candidate_config, capsys):
    monkeypatch.setattr(sys, "argv", [str(WORKFLOW), "--allow-candidate"])
    monkeypatch.setattr(workflow, "load_conducted_config", lambda _: candidate_config)
    monkeypatch.setattr(manifest_module, "load_manifest", lambda _: {
        "schema_version": 1, "project_id": "test", "revision": "UNCONFIRMED",
        "locked": False, "files": [{"path": "input.bin", "sha256": "f" * 64}],
    })
    monkeypatch.setattr(Path, "is_file", lambda _: True)
    monkeypatch.setattr(manifest_module, "sha256_file", lambda _: "0" * 64)
    monkeypatch.setattr(workflow, "run_candidate", lambda *a: pytest.fail("simulation should not run"))
    with pytest.raises(SystemExit) as exc:
        workflow.main()
    assert exc.value.code == 2
    assert "SHA-256 mismatch" in capsys.readouterr().err


def test_non_candidate_manifest_remains_strict_with_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(WORKFLOW), "--allow-candidate"])
    monkeypatch.setattr(workflow, "load_conducted_config", lambda _: {"mode": "locked"})
    calls = []
    def reject(path, **kwargs):
        calls.append(kwargs)
        raise manifest_module.ManifestError("Revision manifest is not locked")
    monkeypatch.setattr(workflow, "verify_manifest", reject)
    with pytest.raises(SystemExit) as exc:
        workflow.main()
    assert exc.value.code == 2
    assert calls == [{"input_root": EMC_ROOT / "smart_power_strip"}]
    assert "not locked" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("section", "key", "changed"),
    [
        ("components", "C2", "220 nF"),
        ("components", "extra", "modeled"),
        ("source", "description", "100 uA DM"),
        ("source", "provenance", "measured converter"),
        ("measurement_network", "description", "other LISN"),
    ],
)
def test_candidate_scenario_rejects_unmodeled_config_edits(candidate_config, section, key, changed):
    config = copy.deepcopy(candidate_config)
    config[section][key] = changed
    with pytest.raises(SpiceModelError, match="fixed simulated scenario"):
        validate_candidate_scenario(config)


def test_candidate_scenario_accepts_matching_config(candidate_config):
    validate_candidate_scenario(candidate_config)


@pytest.mark.parametrize("field,value", [
    ("source_revision", "different-board"),
    ("sweep", ["DM k 0.9"]),
    ("unexpected_model_parameter", 42),
])
def test_candidate_rejects_changed_scenario_or_unknown_fields(candidate_config, field, value):
    candidate_config[field] = value
    with pytest.raises(SpiceModelError):
        validate_candidate_scenario(candidate_config)
