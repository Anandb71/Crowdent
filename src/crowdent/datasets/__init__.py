"""Public dataset registry and local-copy verification.

This package never downloads anything and never accepts a licence on an
operator's behalf. It records where public crowd datasets live and what
Crowdent would use them for, and it hashes local copies so a benchmark
result can name the exact bytes it was computed from.
"""

from crowdent.datasets.manifest import (
    DatasetManifest,
    FileRecord,
    ManifestVerification,
    build_manifest,
    hash_file,
    read_manifest,
    verify_manifest,
    write_manifest,
)
from crowdent.datasets.registry import (
    DATASETS,
    Dataset,
    DatasetAccess,
    DatasetTask,
    SizeBand,
    acquisition_plan,
    all_datasets,
    find_datasets,
    get_dataset,
)

__all__ = [
    "DATASETS",
    "Dataset",
    "DatasetAccess",
    "DatasetManifest",
    "DatasetTask",
    "FileRecord",
    "ManifestVerification",
    "SizeBand",
    "acquisition_plan",
    "all_datasets",
    "build_manifest",
    "find_datasets",
    "get_dataset",
    "hash_file",
    "read_manifest",
    "verify_manifest",
    "write_manifest",
]
