import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from crowdent.storage import (
    AtomicNpzChunkWriter,
    SQLiteStorage,
    WriterLockError,
    export_replay_bundle,
)

NOW = datetime(2026, 8, 24, 10, 0, tzinfo=UTC)


def test_audit_records_form_a_verifiable_hash_chain(tmp_path: Path) -> None:
    database_path = tmp_path / "crowdent.db"
    with SQLiteStorage(database_path) as storage:
        first = storage.append_audit(
            event_type="instruction.created",
            actor_id="supervisor-1",
            actor_role="supervisor",
            payload={"instruction_id": "instruction-1"},
            timestamp=NOW,
        )
        second = storage.append_audit(
            event_type="instruction.accepted",
            actor_id="supervisor-1",
            actor_role="supervisor",
            payload={"instruction_id": "instruction-1"},
            timestamp=NOW,
        )

        assert first.previous_hash == "0" * 64
        assert second.previous_hash == first.entry_hash
        assert storage.verify_audit_chain() is True
        assert storage.schema_version == 1


def test_storage_enforces_one_writer_lock(tmp_path: Path) -> None:
    database_path = tmp_path / "crowdent.db"
    with SQLiteStorage(database_path):
        with pytest.raises(WriterLockError):
            SQLiteStorage(database_path)


def test_npz_chunks_are_atomic_and_manifested(tmp_path: Path) -> None:
    chunk_directory = tmp_path / "chunks"
    writer = AtomicNpzChunkWriter(chunk_directory)

    entry = writer.write_chunk(
        run_id="run-001",
        sequence=4,
        timestamp=NOW,
        arrays={"density": np.array([[1.0, 1.2], [1.1, 1.3]], dtype=np.float32)},
    )

    chunk_path = chunk_directory / entry.filename
    assert chunk_path.exists()
    assert hashlib.sha256(chunk_path.read_bytes()).hexdigest() == entry.sha256
    assert not list(chunk_directory.glob("*.tmp"))

    manifest = json.loads((chunk_directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["chunks"][0]["sha256"] == entry.sha256


def test_replay_bundle_contains_database_and_verified_chunks(tmp_path: Path) -> None:
    database_path = tmp_path / "crowdent.db"
    with SQLiteStorage(database_path) as storage:
        storage.append_event(
            event_type="run.started",
            payload={"run_id": "run-001"},
            timestamp=NOW,
        )

    chunks = tmp_path / "chunks"
    AtomicNpzChunkWriter(chunks).write_chunk(
        run_id="run-001",
        sequence=1,
        timestamp=NOW,
        arrays={"count": np.array([1, 2, 3], dtype=np.int64)},
    )
    destination = tmp_path / "replay.zip"

    result = export_replay_bundle(
        database_path=database_path,
        chunk_directory=chunks,
        destination=destination,
        exported_at=NOW,
    )

    assert result == destination
    with zipfile.ZipFile(destination) as bundle:
        members = set(bundle.namelist())
        assert "database/crowdent.db" in members
        assert "chunks/manifest.json" in members
        assert "bundle.json" in members
