"""Verify and non-destructively refresh the local JLC Parts MCP database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / ".mcp.json"
EXPECTED_INDEX_VERSION = 2
DOWNLOAD_LINE = re.compile(r"downloading (cache\.z\d+|cache\.zip) \((\d+)/(\d+)\)")


def default_database_path() -> Path:
    data_dir = os.environ.get("JLCPARTS_MCP_DATA")
    if data_dir:
        return Path(data_dir).expanduser() / "parts.sqlite3"
    return Path.home() / ".cache" / "jlcparts-mcp" / "parts.sqlite3"


def package_revision() -> tuple[str, str]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    args = config["mcpServers"]["jlcparts"]["args"]
    source = args[args.index("--from") + 1]
    revision = source.rsplit("@", 1)[-1]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(f"JLC Parts MCP source is not pinned to a full commit: {source}")
    return source, revision


def _read_metadata(database: Path) -> dict[str, str]:
    if not database.is_file():
        raise FileNotFoundError(f"Catalog database does not exist: {database}")
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity_check failed: {integrity}")
        metadata = dict(connection.execute("SELECT key, value FROM meta"))
    finally:
        connection.close()
    return metadata


def _utc_from_epoch(metadata: dict[str, str], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"Invalid catalog timestamp {key}={value!r}") from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_database(database: Path) -> dict[str, object]:
    database = database.expanduser().resolve()
    metadata = _read_metadata(database)
    try:
        index_version = int(metadata["index_version"])
        part_count = int(metadata["n_parts"])
    except (KeyError, ValueError) as error:
        raise ValueError("Catalog metadata is missing a valid index_version or n_parts") from error
    if index_version != EXPECTED_INDEX_VERSION:
        raise ValueError(
            f"Unsupported catalog index version {index_version}; expected {EXPECTED_INDEX_VERSION}"
        )
    if part_count <= 0:
        raise ValueError(f"Catalog contains no indexed parts: n_parts={part_count}")
    source_last_modified = metadata.get("source_last_modified")
    if not source_last_modified:
        raise ValueError("Catalog metadata has no source_last_modified value")
    return {
        "database": str(database),
        "size_bytes": database.stat().st_size,
        "sha256": _sha256_file(database),
        "index_version": index_version,
        "n_parts": part_count,
        "n_fresh_30d": int(metadata.get("n_fresh_30d", "0")),
        "source_last_modified": source_last_modified,
        "source_time_utc": _utc_from_epoch(metadata, "source_time"),
        "built_at_utc": _utc_from_epoch(metadata, "built_at"),
        "sqlite_integrity_check": "ok",
    }


def validate_download_log(output: str) -> list[str]:
    progress = [
        (name, int(index), int(total))
        for name, index, total in DOWNLOAD_LINE.findall(output)
    ]
    if not progress:
        raise ValueError("Build output did not report catalog shard downloads")
    total = progress[0][2]
    expected_names = [f"cache.z{index:02d}" for index in range(1, total)] + ["cache.zip"]
    if any(entry[2] != total for entry in progress):
        raise ValueError(f"Inconsistent shard totals in build output: {progress}")
    if [entry[1] for entry in progress] != list(range(1, total + 1)):
        raise ValueError(f"Incomplete or duplicated shard download sequence: {progress}")
    names = [entry[0] for entry in progress]
    if names != expected_names:
        raise ValueError(f"Unexpected shard sequence; expected {expected_names}, received {names}")
    return names


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    suffix = 2
    while True:
        candidate = path.with_name(f"{path.name}-{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def promote_candidate(
    candidate: Path,
    target: Path,
    provenance: dict[str, object],
) -> dict[str, object]:
    candidate = candidate.expanduser().resolve()
    target = target.expanduser().resolve()
    if candidate == target:
        raise ValueError("Candidate and active database paths must be different")
    candidate_info = verify_database(candidate)
    target.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = None
    if target.exists():
        backup = _unique_path(target.with_name(f"{target.name}.backup-{timestamp}"))
        shutil.copy2(target, backup)
    try:
        os.replace(candidate, target)
    except OSError as error:
        backup_note = f" Previous database backup: {backup}." if backup else ""
        raise RuntimeError(
            f"Could not promote the verified candidate to {target}; the active database was not replaced."
            f"{backup_note} Stop the MCP server if it has the file open, then retry."
        ) from error

    manifest_path = _unique_path(target.with_name(f"{target.name}.provenance-{timestamp}.json"))
    manifest = {
        **candidate_info,
        **provenance,
        "database": str(target),
        "target_database": str(target),
        "backup_database": str(backup) if backup else None,
        "promoted_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except OSError as error:
        raise RuntimeError(
            f"Database was promoted to {target}, but provenance manifest could not be written. "
            f"The previous database remains at {backup}."
        ) from error
    manifest["manifest"] = str(manifest_path)
    return manifest


def refresh_database(target: Path) -> dict[str, object]:
    source, revision = package_revision()
    target = target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".jlcparts-candidate-", dir=target.parent) as work:
        data_dir = Path(work) / "data"
        data_dir.mkdir()
        environment = os.environ.copy()
        environment["JLCPARTS_MCP_DATA"] = str(data_dir)
        environment["JLCPARTS_MCP_LIVE"] = "0"
        result = subprocess.run(
            ["uvx", "--from", source, "jlcparts-mcp", "build"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode:
            raise RuntimeError(
                f"Candidate catalog build failed with exit code {result.returncode}; "
                "the active database was not modified."
            )
        if "Database updated:" not in output:
            raise RuntimeError(
                "Candidate build did not report a database update; the active database was not modified."
            )
        shards = validate_download_log(output)
        candidate = data_dir / "parts.sqlite3"
        return promote_candidate(
            candidate,
            target,
            {
                "source": source,
                "source_revision": revision,
                "catalog_data_url": os.environ.get(
                    "JLCPARTS_DATA_URL", "https://yaqwsx.github.io/jlcparts/data"
                ),
                "downloaded_shards": shards,
                "shard_sequence_complete": True,
                "build_log_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="check the local database without modifying it")
    verify.add_argument("--database", type=Path, default=default_database_path())
    refresh = subparsers.add_parser(
        "refresh",
        help="build and verify a candidate, back up the active database, then promote it",
    )
    refresh.add_argument("--database", type=Path, default=default_database_path())
    refresh.add_argument(
        "--confirm-server-stopped",
        action="store_true",
        help="acknowledge that the JLC Parts MCP server is stopped before replacing its database",
    )
    args = parser.parse_args()
    try:
        if args.command == "verify":
            source, revision = package_revision()
            result = verify_database(args.database)
            result.update({"source": source, "source_revision": revision})
        else:
            if not args.confirm_server_stopped:
                raise ValueError(
                    "Stop the JLC Parts MCP server and pass --confirm-server-stopped before refreshing."
                )
            result = refresh_database(args.database)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Catalog maintenance failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
