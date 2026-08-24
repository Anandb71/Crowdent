"""Offline sensor adapters with provenance, privacy and source validation."""

from __future__ import annotations

import csv
import ipaddress
import json
import math
import re
import socket
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
_SAFE_RTSP_PATH = re.compile(r"^/[A-Za-z0-9._~/-]+$")
_IDENTIFIER_KEYS = {
    "device_id",
    "raw_device_id",
    "stable_id",
    "mac",
    "mac_address",
    "imei",
    "imsi",
    "advertising_id",
    "bssid",
}


def _parse_timestamp(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    timestamp: datetime
    entry_id: str
    expected_people_per_s: float
    units: str = "people_per_second"

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _parse_timestamp(self.timestamp))
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if (
            not math.isfinite(self.expected_people_per_s)
            or self.expected_people_per_s < 0
        ):
            raise ValueError("expected_people_per_s must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class CounterEvent:
    event_id: str
    timestamp: datetime
    counter_id: str
    count: int
    direction: str = "unknown"
    aligned_timestamp: datetime | None = None
    units: str = "people"

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _parse_timestamp(self.timestamp))
        if self.aligned_timestamp is not None:
            object.__setattr__(
                self,
                "aligned_timestamp",
                _parse_timestamp(self.aligned_timestamp),
            )
        if not self.event_id or not self.counter_id:
            raise ValueError("event_id and counter_id are required")
        if isinstance(self.count, bool) or int(self.count) != self.count or self.count < 0:
            raise ValueError("counter count must be a nonnegative integer")
        if self.direction not in {"in", "out", "unknown"}:
            raise ValueError("direction must be in, out or unknown")


@dataclass(frozen=True, slots=True)
class PassiveAggregate:
    event_id: str
    timestamp: datetime
    zone_id: str
    count: int
    window_s: float
    units: str = "anonymous_devices"

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _parse_timestamp(self.timestamp))
        if not self.event_id or not self.zone_id:
            raise ValueError("event_id and zone_id are required")
        if isinstance(self.count, bool) or int(self.count) != self.count or self.count < 0:
            raise ValueError("aggregate count must be a nonnegative integer")
        if not math.isfinite(self.window_s) or self.window_s <= 0:
            raise ValueError("window_s must be finite and positive")


def load_schedule_csv(path: Path | str) -> tuple[ScheduleEntry, ...]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return _schedule_rows(csv.DictReader(handle))


def load_schedule_json(path: Path | str) -> tuple[ScheduleEntry, ...]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, list):
        raise ValueError("schedule JSON must contain a list")
    return _schedule_rows(document)


def _schedule_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[ScheduleEntry, ...]:
    entries = tuple(
        ScheduleEntry(
            timestamp=_parse_timestamp(str(row["timestamp"])),
            entry_id=str(row["entry_id"]),
            expected_people_per_s=float(row["expected_people_per_s"]),
        )
        for row in rows
    )
    return tuple(sorted(entries, key=lambda item: (item.timestamp, item.entry_id)))


def load_counter_csv(path: Path | str) -> tuple[CounterEvent, ...]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return _counter_rows(csv.DictReader(handle))


def load_counter_json(path: Path | str) -> tuple[CounterEvent, ...]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, list):
        raise ValueError("counter JSON must contain a list")
    return _counter_rows(document)


def _counter_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[CounterEvent, ...]:
    events = tuple(
        CounterEvent(
            event_id=str(row["event_id"]),
            timestamp=_parse_timestamp(str(row["timestamp"])),
            counter_id=str(row["counter_id"]),
            count=int(row["count"]),
            direction=str(row.get("direction") or "unknown").lower(),
        )
        for row in rows
    )
    return tuple(sorted(events, key=lambda item: (item.timestamp, item.event_id)))


def parse_passive_aggregate(payload: Mapping[str, Any]) -> PassiveAggregate:
    lowered = {str(key).lower() for key in payload}
    if lowered & _IDENTIFIER_KEYS:
        raise ValueError("raw or stable device identifier is forbidden")
    return PassiveAggregate(
        event_id=str(payload["event_id"]),
        timestamp=_parse_timestamp(str(payload["timestamp"])),
        zone_id=str(payload["zone_id"]),
        count=int(payload["count"]),
        window_s=float(payload.get("window_s", 60.0)),
    )


@dataclass(slots=True)
class StreamDiagnostics:
    accepted: int = 0
    duplicates: int = 0
    stale: int = 0
    future: int = 0


class EventStream:
    def __init__(
        self,
        *,
        max_age_s: float,
        future_tolerance_s: float,
        alignment_s: float,
    ) -> None:
        if min(max_age_s, future_tolerance_s, alignment_s) < 0 or alignment_s == 0:
            raise ValueError("stream timing values must be nonnegative and alignment positive")
        self.max_age_s = float(max_age_s)
        self.future_tolerance_s = float(future_tolerance_s)
        self.alignment_s = float(alignment_s)
        self.diagnostics = StreamDiagnostics()
        self._seen: set[str] = set()

    def ingest(
        self,
        events: Iterable[CounterEvent],
        *,
        now: datetime,
    ) -> tuple[CounterEvent, ...]:
        current = _parse_timestamp(now)
        accepted: list[CounterEvent] = []
        for event in sorted(events, key=lambda item: (item.timestamp, item.event_id)):
            if event.event_id in self._seen:
                self.diagnostics.duplicates += 1
                continue
            self._seen.add(event.event_id)
            age = (current - event.timestamp).total_seconds()
            if age > self.max_age_s:
                self.diagnostics.stale += 1
                continue
            if age < -self.future_tolerance_s:
                self.diagnostics.future += 1
                continue
            epoch = event.timestamp.timestamp()
            aligned_epoch = math.floor(epoch / self.alignment_s) * self.alignment_s
            accepted.append(
                replace(
                    event,
                    aligned_timestamp=datetime.fromtimestamp(aligned_epoch, tz=UTC),
                )
            )
            self.diagnostics.accepted += 1
        return tuple(accepted)


@dataclass(frozen=True, slots=True)
class RecordedSource:
    path: Path


def validate_recorded_source(
    path: Path | str,
    *,
    allowed_root: Path | str | None = None,
) -> RecordedSource:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    resolved = source.resolve()
    if not resolved.is_file():
        raise ValueError("recorded source must be a file")
    if resolved.suffix.lower() not in _VIDEO_EXTENSIONS:
        raise ValueError("recorded source has an unsupported video extension")
    if allowed_root is not None:
        root = Path(allowed_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError("recorded source is outside the allowed root") from error
    return RecordedSource(path=resolved)


@dataclass(frozen=True, slots=True)
class RtspSource:
    scheme: str
    host: str
    port: int
    path: str

    @property
    def redacted_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"


def validate_rtsp_source(
    url: str,
    *,
    allowed_hosts: set[str] | frozenset[str] = frozenset(),
    resolve_dns: bool = True,
) -> RtspSource:
    if any(character in url for character in ("\n", "\r", "\x00", "`", "|")):
        raise ValueError("RTSP URL contains unsafe characters")
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"rtsp", "rtsps"}:
        raise ValueError("only rtsp and rtsps sources are supported")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials must be supplied through a secret store")
    if not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("RTSP URL must contain only a host and stream path")
    if not _SAFE_RTSP_PATH.fullmatch(parsed.path):
        raise ValueError("RTSP path contains unsafe or encoded shell text")
    host = parsed.hostname.lower()
    allowlisted = host in {item.lower() for item in allowed_hosts}
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    try:
        addresses.add(ipaddress.ip_address(host))
    except ValueError:
        if not resolve_dns:
            if not allowlisted:
                raise ValueError(
                    "unresolved RTSP host must be explicitly allowlisted"
                ) from None
        else:
            try:
                for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
                    addresses.add(ipaddress.ip_address(item[4][0]))
            except socket.gaierror as error:
                raise ValueError("RTSP host could not be resolved") from error
    if not allowlisted and any(_unsafe_address(address) for address in addresses):
        raise ValueError("private, loopback, link-local or reserved RTSP host is not allowlisted")
    try:
        port = parsed.port or 554
    except ValueError as error:
        raise ValueError("invalid RTSP port") from error
    if not 1 <= port <= 65535:
        raise ValueError("invalid RTSP port")
    return RtspSource(scheme=scheme, host=host, port=port, path=parsed.path)


def _unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    )


__all__ = [
    "CounterEvent",
    "EventStream",
    "PassiveAggregate",
    "RecordedSource",
    "RtspSource",
    "ScheduleEntry",
    "StreamDiagnostics",
    "load_counter_csv",
    "load_counter_json",
    "load_schedule_csv",
    "load_schedule_json",
    "parse_passive_aggregate",
    "validate_recorded_source",
    "validate_rtsp_source",
]
