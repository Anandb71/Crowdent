"""Crash-safe local storage and replay bundle export."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Self, cast

import numpy as np

from crowdent.contracts import AuditRecord

SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


class WriterLockError(RuntimeError):
    """Raised when another writer owns a database."""


@dataclass(frozen=True, slots=True)
class ChunkEntry:
    run_id: str
    sequence: int
    timestamp: str
    filename: str
    sha256: str
    arrays: tuple[str, ...]


class SQLiteStorage:
    """Single-writer SQLite store with an append-only audit chain."""

    _guard: ClassVar[threading.Lock] = threading.Lock()
    _open_paths: ClassVar[set[Path]] = set()

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._closed = False
        with self._guard:
            if self.database_path in self._open_paths:
                raise WriterLockError(f"writer already active for {self.database_path}")
            self._open_paths.add(self.database_path)
        try:
            self._connection = sqlite3.connect(
                self.database_path,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._initialize_schema()
        except Exception:
            with self._guard:
                self._open_paths.discard(self.database_path)
            raise

    @property
    def schema_version(self) -> int:
        row = self._connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"])

    def _initialize_schema(self) -> None:
        self._connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE
            );
            INSERT INTO metadata(key, value) VALUES('schema_version', '1')
            ON CONFLICT(key) DO NOTHING;
            COMMIT;
            """
        )
        if self.schema_version != SCHEMA_VERSION:
            raise RuntimeError(f"unsupported storage schema {self.schema_version}")

    def append_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        timestamp: datetime,
    ) -> int:
        _require_aware(timestamp)
        payload_json = _canonical_json(payload)
        cursor = self._connection.execute(
            "INSERT INTO events(timestamp, event_type, payload_json) VALUES(?, ?, ?)",
            (timestamp.isoformat(), event_type, payload_json),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an event sequence")
        return int(cursor.lastrowid)

    def append_audit(
        self,
        *,
        event_type: str,
        actor_id: str,
        actor_role: str,
        payload: dict[str, Any],
        timestamp: datetime,
    ) -> AuditRecord:
        _require_aware(timestamp)
        previous = self._connection.execute(
            "SELECT entry_hash FROM audit ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous["entry_hash"]) if previous else ZERO_HASH
        payload_json = _canonical_json(payload)
        digest_payload = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "payload": json.loads(payload_json),
            "previous_hash": previous_hash,
        }
        entry_hash = hashlib.sha256(
            _canonical_json(digest_payload).encode("utf-8")
        ).hexdigest()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO audit(
                    timestamp, event_type, actor_id, actor_role, payload_json,
                    previous_hash, entry_hash
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    event_type,
                    actor_id,
                    actor_role,
                    payload_json,
                    previous_hash,
                    entry_hash,
                ),
            )
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an audit sequence")
        return AuditRecord(
            sequence=int(cursor.lastrowid),
            timestamp=timestamp,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            payload=json.loads(payload_json),
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )

    def list_audit(self, *, limit: int = 1000) -> tuple[AuditRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT sequence, timestamp, event_type, actor_id, actor_role,
                   payload_json, previous_hash, entry_hash
            FROM audit ORDER BY sequence ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            AuditRecord(
                sequence=int(row["sequence"]),
                timestamp=datetime.fromisoformat(str(row["timestamp"])),
                event_type=str(row["event_type"]),
                actor_id=str(row["actor_id"]),
                actor_role=str(row["actor_role"]),
                payload=json.loads(str(row["payload_json"])),
                previous_hash=str(row["previous_hash"]),
                entry_hash=str(row["entry_hash"]),
            )
            for row in rows
        )

    def verify_audit_chain(self) -> bool:
        expected_previous = ZERO_HASH
        for record in self.list_audit():
            if record.previous_hash != expected_previous:
                return False
            digest_payload = {
                "timestamp": record.timestamp.isoformat(),
                "event_type": record.event_type,
                "actor_id": record.actor_id,
                "actor_role": record.actor_role,
                "payload": record.payload,
                "previous_hash": record.previous_hash,
            }
            expected_hash = hashlib.sha256(
                _canonical_json(digest_payload).encode("utf-8")
            ).hexdigest()
            if record.entry_hash != expected_hash:
                return False
            expected_previous = record.entry_hash
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()
        self._closed = True
        with self._guard:
            self._open_paths.discard(self.database_path)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AtomicNpzChunkWriter:
    """Writes immutable compressed array chunks and an atomic manifest."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.directory / "manifest.json"

    def write_chunk(
        self,
        *,
        run_id: str,
        sequence: int,
        timestamp: datetime,
        arrays: dict[str, np.ndarray],
    ) -> ChunkEntry:
        _require_aware(timestamp)
        if sequence < 0:
            raise ValueError("sequence must be nonnegative")
        if not arrays:
            raise ValueError("at least one array is required")
        normalized: dict[str, np.ndarray] = {}
        for name, value in arrays.items():
            array = np.asarray(value)
            if array.dtype.kind in "fc" and not np.all(np.isfinite(array)):
                raise ValueError(f"array {name!r} contains non-finite values")
            normalized[name] = array
        safe_run = _SAFE_ID.sub("_", run_id).strip("._") or "run"
        filename = f"{safe_run}-{sequence:08d}.npz"
        destination = self.directory / filename
        temporary = self.directory / f".{filename}.{os.getpid()}.tmp"
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, **normalized)  # type: ignore[arg-type]
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
        entry = ChunkEntry(
            run_id=run_id,
            sequence=sequence,
            timestamp=timestamp.isoformat(),
            filename=filename,
            sha256=sha256,
            arrays=tuple(sorted(normalized)),
        )
        manifest = self._read_manifest()
        manifest["chunks"] = [
            item
            for item in manifest["chunks"]
            if not (
                item.get("run_id") == run_id and int(item.get("sequence", -1)) == sequence
            )
        ]
        manifest["chunks"].append(asdict(entry))
        manifest["chunks"].sort(key=lambda item: (item["run_id"], int(item["sequence"])))
        self._write_manifest(manifest)
        return entry

    def _read_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema_version": SCHEMA_VERSION, "chunks": []}
        document = cast(
            dict[str, Any],
            json.loads(self.manifest_path.read_text(encoding="utf-8")),
        )
        if document.get("schema_version") != SCHEMA_VERSION:
            raise RuntimeError("unsupported chunk manifest schema")
        return document

    def _write_manifest(self, document: dict[str, Any]) -> None:
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.manifest_path)


def export_replay_bundle(
    *,
    database_path: Path | str,
    chunk_directory: Path | str,
    destination: Path | str,
    exported_at: datetime | None = None,
) -> Path:
    """Export a self-verifying replay archive."""

    exported = exported_at or datetime.now(UTC)
    _require_aware(exported)
    database = Path(database_path)
    chunks = Path(chunk_directory)
    output = Path(destination)
    manifest_path = chunks / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_files: list[dict[str, str]] = []
    for item in manifest.get("chunks", []):
        path = chunks / str(item["filename"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"chunk hash mismatch: {path.name}")
        bundle_files.append({"path": f"chunks/{path.name}", "sha256": digest})
    database_digest = hashlib.sha256(database.read_bytes()).hexdigest()
    bundle_files.append({"path": "database/crowdent.db", "sha256": database_digest})
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": exported.isoformat(),
        "research_only": True,
        "files": bundle_files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database, "database/crowdent.db")
        archive.write(manifest_path, "chunks/manifest.json")
        for item in manifest.get("chunks", []):
            archive.write(chunks / str(item["filename"]), f"chunks/{item['filename']}")
        archive.writestr("bundle.json", json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    return output


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")


__all__ = [
    "AtomicNpzChunkWriter",
    "ChunkEntry",
    "SQLiteStorage",
    "WriterLockError",
    "export_replay_bundle",
]
