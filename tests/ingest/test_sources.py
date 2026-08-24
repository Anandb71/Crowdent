from __future__ import annotations

from pathlib import Path

import pytest

from crowdent.ingest import (
    RecordedSource,
    RtspSource,
    validate_recorded_source,
    validate_rtsp_source,
)


def test_recorded_source_is_confined_to_allowed_root(tmp_path) -> None:
    allowed = tmp_path / "recordings"
    allowed.mkdir()
    video = allowed / "sample.mp4"
    video.write_bytes(b"not-decoded-during-validation")

    source = validate_recorded_source(video, allowed_root=allowed)

    assert isinstance(source, RecordedSource)
    assert source.path == video.resolve()

    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError, match="allowed root"):
        validate_recorded_source(outside, allowed_root=allowed)


def test_recorded_source_rejects_non_video_extensions_and_missing_files(tmp_path) -> None:
    text = tmp_path / "input.txt"
    text.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="extension"):
        validate_recorded_source(text)
    with pytest.raises(FileNotFoundError):
        validate_recorded_source(tmp_path / "missing.mp4")


@pytest.mark.parametrize(
    "url",
    [
        "rtsp://127.0.0.1/live",
        "rtsp://10.0.0.4/live",
        "rtsp://169.254.1.1/live",
        "rtsp://[::1]/live",
        "http://8.8.8.8/live",
        "rtsp://user:secret@8.8.8.8/live",
        "rtsp://8.8.8.8/live;touch%20pwned",
    ],
)
def test_rtsp_source_rejects_ssrf_and_shell_unsafe_inputs(url: str) -> None:
    with pytest.raises(ValueError):
        validate_rtsp_source(url, resolve_dns=False)


def test_rtsp_source_returns_structured_value_not_shell_text() -> None:
    source = validate_rtsp_source("rtsps://8.8.8.8:322/live/camera-1", resolve_dns=False)

    assert isinstance(source, RtspSource)
    assert source.scheme == "rtsps"
    assert source.host == "8.8.8.8"
    assert source.port == 322
    assert source.path == "/live/camera-1"
    assert not hasattr(source, "command")


def test_rtsp_allowlist_can_admit_private_managed_camera() -> None:
    source = validate_rtsp_source(
        "rtsp://10.0.0.4/live",
        allowed_hosts={"10.0.0.4"},
        resolve_dns=False,
    )

    assert source.host == "10.0.0.4"


def test_recorded_path_type_is_path(tmp_path) -> None:
    video = tmp_path / "x.mkv"
    video.write_bytes(b"x")
    source = validate_recorded_source(video)
    assert isinstance(source.path, Path)
