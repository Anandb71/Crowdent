from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from crowdent.ingest import (
    CounterEvent,
    EventStream,
    load_counter_csv,
    load_counter_json,
    load_schedule_csv,
    load_schedule_json,
    parse_passive_aggregate,
)


def test_csv_and_json_schedule_adapters_are_deterministic_and_unit_explicit(tmp_path) -> None:
    csv_path = tmp_path / "schedule.csv"
    csv_path.write_text(
        "timestamp,entry_id,expected_people_per_s\n"
        "2026-08-24T10:05:00Z,north,2.5\n"
        "2026-08-24T10:00:00Z,north,1.5\n",
        encoding="utf-8",
    )
    json_path = tmp_path / "schedule.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-08-24T10:00:00Z",
                    "entry_id": "north",
                    "expected_people_per_s": 1.5,
                }
            ]
        ),
        encoding="utf-8",
    )

    csv_entries = load_schedule_csv(csv_path)
    json_entries = load_schedule_json(json_path)

    assert [entry.expected_people_per_s for entry in csv_entries] == [1.5, 2.5]
    assert json_entries[0] == csv_entries[0]
    assert csv_entries[0].timestamp.tzinfo is UTC


def test_counter_adapters_validate_counts_and_order_records(tmp_path) -> None:
    csv_path = tmp_path / "counter.csv"
    csv_path.write_text(
        "event_id,timestamp,counter_id,count,direction\n"
        "b,2026-08-24T10:01:00Z,c-1,3,out\n"
        "a,2026-08-24T10:00:00Z,c-1,5,in\n",
        encoding="utf-8",
    )
    json_path = tmp_path / "counter.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "a",
                    "timestamp": "2026-08-24T10:00:00Z",
                    "counter_id": "c-1",
                    "count": 5,
                    "direction": "in",
                }
            ]
        ),
        encoding="utf-8",
    )

    csv_events = load_counter_csv(csv_path)
    json_events = load_counter_json(json_path)

    assert [event.event_id for event in csv_events] == ["a", "b"]
    assert json_events[0] == csv_events[0]

    csv_path.write_text(
        "event_id,timestamp,counter_id,count\n"
        "a,2026-08-24T10:00:00Z,c-1,-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="nonnegative"):
        load_counter_csv(csv_path)


@pytest.mark.parametrize(
    "forbidden_key",
    ["device_id", "raw_device_id", "stable_id", "mac_address", "imei", "advertising_id"],
)
def test_passive_aggregate_rejects_raw_or_stable_device_identifiers(
    forbidden_key: str,
) -> None:
    payload = {
        "event_id": "agg-1",
        "timestamp": "2026-08-24T10:00:00Z",
        "zone_id": "zone-a",
        "count": 12,
        forbidden_key: "persistent-secret",
    }

    with pytest.raises(ValueError, match="identifier"):
        parse_passive_aggregate(payload)


def test_passive_aggregate_accepts_only_anonymous_counts() -> None:
    aggregate = parse_passive_aggregate(
        {
            "event_id": "agg-1",
            "timestamp": "2026-08-24T10:00:00Z",
            "zone_id": "zone-a",
            "count": 12,
            "window_s": 60,
        }
    )

    assert aggregate.count == 12
    assert aggregate.window_s == 60.0


def test_event_stream_deduplicates_orders_checks_freshness_and_aligns() -> None:
    now = datetime(2026, 8, 24, 10, 2, 0, tzinfo=UTC)
    stream = EventStream(
        max_age_s=180.0,
        future_tolerance_s=2.0,
        alignment_s=60.0,
    )
    newer = CounterEvent(
        event_id="b",
        timestamp=now - timedelta(seconds=10),
        counter_id="c-1",
        count=3,
        direction="in",
    )
    older = CounterEvent(
        event_id="a",
        timestamp=now - timedelta(seconds=70),
        counter_id="c-1",
        count=2,
        direction="in",
    )

    accepted = stream.ingest([newer, older, newer], now=now)

    assert [event.event_id for event in accepted] == ["a", "b"]
    assert stream.diagnostics.duplicates == 1
    assert accepted[0].aligned_timestamp.second == 0
    assert accepted[1].aligned_timestamp.second == 0

    stale = CounterEvent(
        event_id="stale",
        timestamp=now - timedelta(seconds=181),
        counter_id="c-1",
        count=1,
    )
    future = CounterEvent(
        event_id="future",
        timestamp=now + timedelta(seconds=3),
        counter_id="c-1",
        count=1,
    )
    assert stream.ingest([stale, future], now=now) == ()
    assert stream.diagnostics.stale == 1
    assert stream.diagnostics.future == 1
