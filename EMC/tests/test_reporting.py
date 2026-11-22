import json

import pytest

from emc_sim.reporting import create_run_directory, write_report, write_run_metadata


def test_run_directories_are_non_overwriting(tmp_path):
    run = create_run_directory(tmp_path, "case-a")
    assert run.is_dir()
    with pytest.raises(FileExistsError):
        create_run_directory(tmp_path, "case-a")
    with pytest.raises(ValueError):
        create_run_directory(tmp_path, "../escape")


def test_metadata_is_json_and_never_overwritten(tmp_path):
    run = create_run_directory(tmp_path, "run")
    path = write_run_metadata(run, {"assumptions": ["eps_r=4.2"]})
    assert json.loads(path.read_text(encoding="utf-8"))["assumptions"] == ["eps_r=4.2"]
    with pytest.raises(FileExistsError):
        write_run_metadata(run, {"changed": True})


def test_report_has_evidence_types_and_lab_boundary(tmp_path):
    run = create_run_directory(tmp_path, "report")
    path = write_report(
        run,
        question="Compare two modeled layouts.",
        evidence={
            "assumptions": [],
            "calculations": [],
            "simulations": ["openEMS model output"],
            "measurements": [],
        },
        result="No compliance conclusion.",
        limitations=["No physical board measured."],
    )
    report = path.read_text(encoding="utf-8")
    assert "What Only a Qualified Lab Can Answer" in report
    assert "Assumptions" in report
    assert "Calculations" in report
    assert "Simulations" in report
    assert "Measurements" in report
    with pytest.raises(ValueError, match="Missing evidence categories"):
        write_report(
            run,
            question="x",
            evidence={"assumptions": []},
            result="y",
            limitations=[],
        )
