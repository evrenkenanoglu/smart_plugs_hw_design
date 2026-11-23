from check_case_paths import case_path_error


def test_case_path_error_accepts_exact_case(tmp_path):
    path = tmp_path / "DOCS" / "README.md"
    path.parent.mkdir()
    path.write_text("test", encoding="utf-8")

    assert case_path_error(path) is None


def test_case_path_error_detects_case_mismatch(tmp_path):
    actual = tmp_path / "Docs"
    actual.mkdir()
    (actual / "README.md").write_text("test", encoding="utf-8")

    error = case_path_error(tmp_path / "DOCS" / "README.md")

    assert error is not None
    assert "case mismatch" in error
    assert "'Docs'" in error
