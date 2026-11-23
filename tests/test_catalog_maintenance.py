import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / ".agents" / "mcp" / "catalog_maintenance.py"
SPEC = importlib.util.spec_from_file_location("catalog_maintenance", MODULE_PATH)
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


def create_database(path: Path, count: int) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.executemany(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        [
            ("index_version", "2"),
            ("built_at", "1795420816"),
            ("source_time", "1795395819"),
            ("n_parts", str(count)),
            ("n_fresh_30d", "1"),
            ("source_last_modified", "Mon, 23 Nov 2026 01:03:39 GMT"),
        ],
    )
    connection.execute("CREATE TABLE parts (lcsc TEXT PRIMARY KEY)")
    connection.commit()
    connection.close()


def test_validate_download_log_requires_contiguous_shards():
    complete = "\n".join(
        f"[jlcparts-mcp] downloading cache.z0{index} ({index}/3)"
        for index in (1, 2)
    ) + "\n[jlcparts-mcp] downloading cache.zip (3/3)"
    assert catalog.validate_download_log(complete) == ["cache.z01", "cache.z02", "cache.zip"]

    with pytest.raises(ValueError, match="Incomplete or duplicated"):
        catalog.validate_download_log(
            "[jlcparts-mcp] downloading cache.z01 (1/3)\n"
            "[jlcparts-mcp] downloading cache.zip (3/3)"
        )


def test_verify_database_checks_integrity_metadata_and_hash(tmp_path):
    database = tmp_path / "parts.sqlite3"
    create_database(database, 12)

    result = catalog.verify_database(database)

    assert result["sqlite_integrity_check"] == "ok"
    assert result["n_parts"] == 12
    assert len(result["sha256"]) == 64


def test_promotion_preserves_existing_database_and_writes_provenance(tmp_path):
    target = tmp_path / "active" / "parts.sqlite3"
    target.parent.mkdir()
    candidate = tmp_path / "candidate.sqlite3"
    create_database(target, 3)
    create_database(candidate, 8)

    result = catalog.promote_candidate(
        candidate,
        target,
        {"source_revision": "a" * 40, "downloaded_shards": ["cache.zip"]},
    )

    assert result["n_parts"] == 8
    assert Path(result["backup_database"]).is_file()
    assert Path(result["manifest"]).is_file()
    assert catalog.verify_database(target)["n_parts"] == 8
    assert catalog.verify_database(Path(result["backup_database"]))["n_parts"] == 3


def test_refresh_requires_explicit_server_stopped_confirmation(tmp_path):
    database = tmp_path / "parts.sqlite3"
    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "refresh",
            "--database",
            str(database),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "--confirm-server-stopped" in result.stderr
    assert not database.exists()
