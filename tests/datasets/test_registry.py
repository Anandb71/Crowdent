"""The registry must stay honest: no bundled data, no silent downloads, no invented terms."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from crowdent.datasets import (
    DATASETS,
    DatasetAccess,
    DatasetTask,
    SizeBand,
    acquisition_plan,
    all_datasets,
    find_datasets,
    get_dataset,
)

_NETWORK_TOKENS = (
    "import requests",
    "import httpx",
    "import urllib",
    "from urllib",
    "import socket",
    "urlretrieve",
    "urlopen",
)


def test_the_datasets_package_cannot_reach_the_network() -> None:
    """Acquisition is a human act. The package must hold no client at all."""

    root = Path(__file__).resolve().parents[2] / "src" / "crowdent" / "datasets"
    offenders = [
        f"{path.name}: {token}"
        for path in root.rglob("*.py")
        for token in _NETWORK_TOKENS
        if token in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_identifiers_are_unique() -> None:
    identifiers = [dataset.identifier for dataset in DATASETS]
    assert len(identifiers) == len(set(identifiers))


def test_every_record_carries_terms_a_human_can_check() -> None:
    for dataset in DATASETS:
        assert dataset.homepage.startswith("https://"), dataset.identifier
        assert dataset.license, dataset.identifier
        assert dataset.citation, dataset.identifier
        assert dataset.caveats, dataset.identifier
        assert dataset.crowdent_use, dataset.identifier
        assert isinstance(dataset.terms_reviewed, date), dataset.identifier


def test_no_record_claims_a_right_to_redistribute() -> None:
    for dataset in DATASETS:
        assert "redistribut" not in dataset.license.lower(), dataset.identifier


def test_registration_datasets_are_marked_as_needing_human_acceptance() -> None:
    gated = find_datasets(access=DatasetAccess.REGISTRATION)
    assert gated
    for dataset in gated:
        assert dataset.needs_human_acceptance is True


def test_only_explicitly_open_datasets_skip_human_acceptance() -> None:
    for dataset in DATASETS:
        expected = dataset.access is not DatasetAccess.OPEN
        assert dataset.needs_human_acceptance is expected


def test_the_registry_covers_the_physics_this_repository_claims() -> None:
    """Density alone cannot validate a velocity-variance pressure index."""

    tasks = {dataset.task for dataset in DATASETS}
    assert DatasetTask.TRAJECTORY in tasks
    assert DatasetTask.VIDEO_DENSITY in tasks
    assert DatasetTask.LOCALIZATION in tasks


def test_a_trajectory_dataset_is_available_without_registration() -> None:
    """A researcher with no institutional contacts must still be able to start."""

    open_trajectories = find_datasets(
        task=DatasetTask.TRAJECTORY, access=DatasetAccess.OPEN
    )
    assert open_trajectories


def test_find_datasets_filters_and_composes() -> None:
    assert find_datasets() == all_datasets()
    small = find_datasets(max_size=SizeBand.SMALL)
    assert small
    assert all(item.size_band is SizeBand.SMALL for item in small)
    medium_or_less = find_datasets(max_size=SizeBand.MEDIUM)
    assert set(small).issubset(set(medium_or_less))
    combined = find_datasets(task=DatasetTask.COUNTING, max_size=SizeBand.SMALL)
    assert all(
        item.task is DatasetTask.COUNTING and item.size_band is SizeBand.SMALL
        for item in combined
    )


def test_find_datasets_can_return_nothing_without_raising() -> None:
    assert find_datasets(task=DatasetTask.TRAJECTORY, max_size=SizeBand.SMALL) is not None


def test_unknown_identifier_lists_the_known_ones() -> None:
    with pytest.raises(KeyError, match="unknown dataset"):
        get_dataset("not-a-dataset")
    try:
        get_dataset("not-a-dataset")
    except KeyError as error:
        assert "juelich-ped-da" in str(error)


def test_acquisition_plan_tells_the_reader_to_read_the_terms_themselves() -> None:
    dataset = get_dataset("nwpu-crowd")
    plan = acquisition_plan(dataset)
    assert dataset.homepage in plan
    assert "read the current terms yourself" in plan
    assert "will not submit forms or accept terms on your behalf" in plan
    assert dataset.citation in plan


def test_acquisition_plan_reminds_the_reader_that_data_stays_out_of_git() -> None:
    plan = acquisition_plan(get_dataset("shanghaitech-a"))
    assert "gitignored" in plan
    assert "never commit" in plan


def test_acquisition_plan_honours_a_custom_destination() -> None:
    plan = acquisition_plan(get_dataset("ucf-qnrf"), destination="/mnt/research/qnrf")
    assert "/mnt/research/qnrf" in plan


def test_no_dataset_file_is_vendored_into_the_repository() -> None:
    data = Path(__file__).resolve().parents[2] / "data"
    tracked = {item.name for item in data.iterdir() if item.is_file()}
    assert tracked <= {"README.md", ".gitkeep"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("identifier", "has space", "slug without spaces"),
        ("homepage", "http://example.org", "https URL"),
        ("samples", 0, "samples must be positive"),
        ("annotations", 0, "annotations must be positive"),
        ("crowdent_use", "", "record why Crowdent"),
    ],
)
def test_malformed_records_are_rejected(field: str, value: object, message: str) -> None:
    from dataclasses import replace

    with pytest.raises(ValueError, match=message):
        replace(get_dataset("shanghaitech-a"), **{field: value})
