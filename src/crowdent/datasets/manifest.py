"""Checksum manifests for locally held dataset copies.

A published benchmark number is worthless if nobody can tell which copy
of the data produced it. A manifest records the SHA-256 of every file in
a local dataset directory so a later run can prove it is scoring the same
bytes. Manifests contain hashes and relative paths only, never imagery,
so unlike the datasets themselves they are safe to commit.

This module reads and hashes local files. It performs no network access.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_CHUNK_BYTES = 1 << 20
_MANIFEST_VERSION = 1


@dataclass(frozen=True, slots=True)
class FileRecord:
    """One file inside a dataset directory."""

    path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size_bytes": self.size_bytes, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FileRecord:
        digest = str(payload["sha256"])
        if len(digest) != 64 or not all(char in "0123456789abcdef" for char in digest):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return cls(
            path=str(payload["path"]),
            size_bytes=int(payload["size_bytes"]),
            sha256=digest,
        )


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Every file in one local dataset copy, with its hash."""

    dataset: str
    created_at: datetime
    files: tuple[FileRecord, ...]

    @property
    def total_bytes(self) -> int:
        return sum(record.size_bytes for record in self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": _MANIFEST_VERSION,
            "dataset": self.dataset,
            "created_at": self.created_at.isoformat(),
            "file_count": len(self.files),
            "total_bytes": self.total_bytes,
            "research_only": True,
            "files": [record.to_dict() for record in self.files],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DatasetManifest:
        version = int(payload.get("manifest_version", 0))
        if version != _MANIFEST_VERSION:
            raise ValueError(f"unsupported manifest version {version}")
        created = datetime.fromisoformat(str(payload["created_at"]))
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return cls(
            dataset=str(payload["dataset"]),
            created_at=created,
            files=tuple(FileRecord.from_dict(item) for item in payload["files"]),
        )


@dataclass(frozen=True, slots=True)
class ManifestVerification:
    """Difference between a manifest and what is on disk right now."""

    dataset: str
    matched: int
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True only when every recorded file is present and unchanged.

        Unexpected extra files do not fail verification. They are reported
        because a stray file usually means a partial download, but they
        cannot corrupt a score computed from the recorded files.
        """

        return not self.missing and not self.changed

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "ok": self.ok,
            "matched": self.matched,
            "missing": list(self.missing),
            "changed": list(self.changed),
            "unexpected": list(self.unexpected),
            "research_only": True,
        }


def hash_file(path: Path) -> str:
    """SHA-256 of one file, read in chunks so large media does not load into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    root: Path,
    *,
    dataset: str,
    now: datetime | None = None,
) -> DatasetManifest:
    """Hash every file under ``root``, recording paths relative to it."""

    directory = Path(root)
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")
    records = [
        FileRecord(
            path=item.relative_to(directory).as_posix(),
            size_bytes=item.stat().st_size,
            sha256=hash_file(item),
        )
        for item in _walk(directory)
    ]
    records.sort(key=lambda record: record.path)
    return DatasetManifest(
        dataset=dataset,
        created_at=now or datetime.now(UTC),
        files=tuple(records),
    )


def verify_manifest(root: Path, manifest: DatasetManifest) -> ManifestVerification:
    """Re-hash a local copy and report what drifted from the manifest."""

    directory = Path(root)
    if not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")
    missing: list[str] = []
    changed: list[str] = []
    matched = 0
    for record in manifest.files:
        candidate = directory / record.path
        if not candidate.is_file():
            missing.append(record.path)
            continue
        if candidate.stat().st_size != record.size_bytes:
            changed.append(record.path)
            continue
        if hash_file(candidate) != record.sha256:
            changed.append(record.path)
            continue
        matched += 1
    recorded = {record.path for record in manifest.files}
    on_disk = {item.relative_to(directory).as_posix() for item in _walk(directory)}
    return ManifestVerification(
        dataset=manifest.dataset,
        matched=matched,
        missing=tuple(missing),
        changed=tuple(changed),
        unexpected=tuple(sorted(on_disk - recorded)),
    )


def write_manifest(manifest: DatasetManifest, path: Path) -> None:
    """Write a manifest as indented JSON."""

    Path(path).write_text(
        json.dumps(manifest.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def read_manifest(path: Path) -> DatasetManifest:
    """Read a manifest written by :func:`write_manifest`."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    return DatasetManifest.from_dict(payload)


def _walk(directory: Path) -> Iterator[Path]:
    for item in sorted(directory.rglob("*")):
        if item.is_file():
            yield item


__all__ = [
    "DatasetManifest",
    "FileRecord",
    "ManifestVerification",
    "build_manifest",
    "hash_file",
    "read_manifest",
    "verify_manifest",
    "write_manifest",
]
