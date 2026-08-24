"""Manifests must notice every way a local dataset copy can drift."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from crowdent.datasets import (
    DatasetManifest,
    build_manifest,
    hash_file,
    read_manifest,
    verify_manifest,
    write_manifest,
)


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    root = tmp_path / "shanghaitech-a"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "images" / "IMG_1.txt").write_text("frame one", encoding="utf-8")
    (root / "train" / "images" / "IMG_2.txt").write_text("frame two", encoding="utf-8")
    (root / "labels.csv").write_text("id,count\n1,4\n", encoding="utf-8")
    return root


def test_manifest_records_every_file_with_a_relative_posix_path(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    paths = [record.path for record in manifest.files]
    assert paths == [
        "labels.csv",
        "train/images/IMG_1.txt",
        "train/images/IMG_2.txt",
    ]
    assert manifest.total_bytes > 0
    assert all(len(record.sha256) == 64 for record in manifest.files)


def test_a_clean_copy_verifies(copy: Path) -> None:
    result = verify_manifest(copy, build_manifest(copy, dataset="shanghaitech-a"))
    assert result.ok is True
    assert result.matched == 3
    assert result.missing == ()
    assert result.changed == ()
    assert result.unexpected == ()


def test_edited_content_of_the_same_length_is_still_detected(copy: Path) -> None:
    """Size checks are a shortcut, not the guarantee. The hash is the guarantee."""

    manifest = build_manifest(copy, dataset="shanghaitech-a")
    (copy / "train" / "images" / "IMG_1.txt").write_text("frame ONE", encoding="utf-8")
    result = verify_manifest(copy, manifest)
    assert result.ok is False
    assert result.changed == ("train/images/IMG_1.txt",)
    assert result.matched == 2


def test_a_truncated_download_is_detected(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    (copy / "labels.csv").write_text("id", encoding="utf-8")
    result = verify_manifest(copy, manifest)
    assert result.ok is False
    assert result.changed == ("labels.csv",)


def test_a_deleted_file_is_reported_as_missing(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    (copy / "labels.csv").unlink()
    result = verify_manifest(copy, manifest)
    assert result.ok is False
    assert result.missing == ("labels.csv",)


def test_extra_files_are_reported_but_do_not_fail_verification(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    (copy / "notes.md").write_text("scratch", encoding="utf-8")
    result = verify_manifest(copy, manifest)
    assert result.ok is True
    assert result.unexpected == ("notes.md",)


def test_manifest_round_trips_through_json(copy: Path, tmp_path: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    destination = tmp_path / "manifest.json"
    write_manifest(manifest, destination)
    restored = read_manifest(destination)
    assert restored.dataset == manifest.dataset
    assert restored.files == manifest.files
    assert restored.created_at == manifest.created_at


def test_serialized_manifest_declares_research_only(copy: Path) -> None:
    payload = build_manifest(copy, dataset="shanghaitech-a").to_dict()
    assert payload["research_only"] is True
    assert payload["manifest_version"] == 1
    assert payload["file_count"] == 3


def test_verification_result_serializes(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    payload = json.loads(json.dumps(verify_manifest(copy, manifest).to_dict()))
    assert payload["ok"] is True
    assert payload["research_only"] is True


def test_hash_file_matches_a_known_digest(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert hash_file(target) == expected


def test_large_files_hash_without_loading_into_memory(tmp_path: Path) -> None:
    target = tmp_path / "big.bin"
    target.write_bytes(b"\x00" * (3 * (1 << 20) + 17))
    assert len(hash_file(target)) == 64


def test_naive_timestamps_are_rejected(copy: Path) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    payload = manifest.to_dict()
    payload["created_at"] = datetime(2026, 8, 24, 12, 0, 0).isoformat()
    with pytest.raises(ValueError, match="timezone-aware"):
        DatasetManifest.from_dict(payload)


def test_unsupported_manifest_versions_are_rejected(copy: Path) -> None:
    payload = build_manifest(copy, dataset="shanghaitech-a").to_dict()
    payload["manifest_version"] = 99
    with pytest.raises(ValueError, match="unsupported manifest version"):
        DatasetManifest.from_dict(payload)


def test_malformed_digests_are_rejected(copy: Path) -> None:
    payload = build_manifest(copy, dataset="shanghaitech-a").to_dict()
    payload["files"][0]["sha256"] = "NOTAHASH"
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        DatasetManifest.from_dict(payload)


def test_building_a_manifest_of_a_missing_directory_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        build_manifest(tmp_path / "absent", dataset="shanghaitech-a")


def test_verifying_against_a_missing_directory_fails_loudly(
    copy: Path, tmp_path: Path
) -> None:
    manifest = build_manifest(copy, dataset="shanghaitech-a")
    with pytest.raises(NotADirectoryError):
        verify_manifest(tmp_path / "absent", manifest)


def test_manifest_timestamps_can_be_pinned_for_reproducibility(copy: Path) -> None:
    moment = datetime(2026, 8, 24, 9, 30, tzinfo=UTC)
    manifest = build_manifest(copy, dataset="shanghaitech-a", now=moment)
    assert manifest.created_at == moment
