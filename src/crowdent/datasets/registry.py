"""A registry of public crowd datasets relevant to Crowdent.

**This module performs no network access.** It records where public
datasets live, what they cost in disk, what their published access terms
were when this registry was last reviewed, and what Crowdent would
actually use each one for. Acquisition is a deliberate human act: read
the terms, accept them yourself, download to a research machine, then
point Crowdent at the local copy and verify checksums.

The registry is not legal advice and is not a redistribution channel.
Terms change. ``terms_reviewed`` records when a human last read the
homepage, and every record must be re-checked against its ``homepage``
before use. No dataset file is vendored into this repository, and
``data/`` stays gitignored.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DatasetTask(StrEnum):
    """What the annotations support."""

    COUNTING = "counting"
    LOCALIZATION = "localization"
    TRAJECTORY = "trajectory"
    VIDEO_DENSITY = "video_density"


class DatasetAccess(StrEnum):
    """How a copy is obtained.

    ``OPEN`` means an explicit open license is published. ``RESEARCH_USE``
    means the page grants research use, usually conditioned on citation.
    ``REGISTRATION`` means a form, email request, or signed agreement
    stands between you and the data. Crowdent never completes any of
    these on an operator's behalf.
    """

    OPEN = "open"
    RESEARCH_USE = "research_use"
    REGISTRATION = "registration"


class SizeBand(StrEnum):
    """Coarse disk cost, recorded as a band because exact sizes drift."""

    SMALL = "small"  # under 1 GB
    MEDIUM = "medium"  # 1 GB to 10 GB
    LARGE = "large"  # 10 GB to 100 GB
    VERY_LARGE = "very_large"  # over 100 GB


@dataclass(frozen=True, slots=True)
class Dataset:
    """One public dataset and its relevance to crowd-risk forecasting."""

    identifier: str
    name: str
    year: int
    task: DatasetTask
    access: DatasetAccess
    license: str
    homepage: str
    citation: str
    samples: int
    annotations: int | None
    size_band: SizeBand
    modality: str
    crowdent_use: str
    caveats: tuple[str, ...]
    terms_reviewed: date

    def __post_init__(self) -> None:
        if not self.identifier or " " in self.identifier:
            raise ValueError("identifier must be a nonempty slug without spaces")
        if not self.homepage.startswith("https://"):
            raise ValueError(f"{self.identifier}: homepage must be an https URL")
        if self.samples <= 0:
            raise ValueError(f"{self.identifier}: samples must be positive")
        if self.annotations is not None and self.annotations <= 0:
            raise ValueError(f"{self.identifier}: annotations must be positive")
        if not self.crowdent_use:
            raise ValueError(f"{self.identifier}: record why Crowdent would use this")

    @property
    def needs_human_acceptance(self) -> bool:
        """True when a person must accept terms before any download."""

        return self.access is not DatasetAccess.OPEN


_REVIEWED = date(2026, 8, 24)

#: Curated registry. Ordered by how directly each dataset supports the
#: physics Crowdent actually claims, not by popularity.
DATASETS: tuple[Dataset, ...] = (
    Dataset(
        identifier="sanfermin-oscillations",
        name="Collective oscillations in massive human crowds (San Fermín)",
        year=2025,
        task=DatasetTask.VIDEO_DENSITY,
        access=DatasetAccess.OPEN,
        license="CC BY 4.0",
        homepage="https://zenodo.org/records/14050598",
        citation=(
            "Gu, Guiselin, Bain, Zuriguel and Bartolo, Emergence of collective "
            "oscillations in massive human crowds, Nature 638, 2025, "
            "doi:10.1038/s41586-024-08514-6; data doi:10.5281/zenodo.14050598"
        ),
        samples=4,
        annotations=None,
        size_band=SizeBand.MEDIUM,
        modality=(
            "field recordings of a confined mass gathering across four festival years, "
            "with derived density, speed, orientation and chirality maps"
        ),
        crowdent_use=(
            "The closest public analogue to Crowdent's operating regime: a real confined "
            "mass gathering measured up to roughly 9 people per square metre, released as "
            "density and velocity fields rather than raw faces. It supplies both a "
            "validation target for the density-velocity state and a candidate precursor, "
            "since the reported spontaneous oscillation appears above a density threshold "
            "and has a period of order twenty seconds."
        ),
        caveats=(
            "Four events at one venue. A threshold measured here is evidence about crowd "
            "physics, not a transferable venue setting.",
            "Derived fields, not per-person trajectories; sample count is festival years.",
            "The oscillation is a published finding this repository has not reproduced. "
            "Treat it as a hypothesis to test, not as a shipped detector.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="juelich-ped-da",
        name="Pedestrian Dynamics Data Archive (Forschungszentrum Jülich)",
        year=2020,
        task=DatasetTask.TRAJECTORY,
        access=DatasetAccess.OPEN,
        license="CC BY-SA 4.0 on many experiments; per-experiment terms vary",
        homepage="https://ped.fz-juelich.de/database",
        citation="Forschungszentrum Jülich, Pedestrian Dynamics Data Archive, doi:10.34735/ped.da",
        samples=1000,
        annotations=None,
        size_band=SizeBand.LARGE,
        modality="controlled laboratory experiments; video plus PeTrack trajectories",
        crowdent_use=(
            "The primary validation set for this repository. Individual trajectories at "
            "controlled high density give an empirical density-speed fundamental diagram "
            "to test weidmann_speed against, and the velocity variance needed to check the "
            "crowd pressure index end to end."
        ),
        caveats=(
            "Laboratory experiments, not a mela. Geometry and motivation are controlled, "
            "so results transfer as physics, not as venue thresholds.",
            "Per-experiment licensing differs; check each experiment page, not just the root.",
            "Sample count is a rough count of experiment series, not images.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="fudan-shanghaitech",
        name="Fudan-ShanghaiTech (FDST) video crowd counting",
        year=2019,
        task=DatasetTask.VIDEO_DENSITY,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the FDST paper",
        homepage="https://github.com/sweetyy83/Lstn_fdst_dataset",
        citation="Fang et al., Locality-Constrained Spatial Transformer Network, ICME 2019",
        samples=15000,
        annotations=394081,
        size_band=SizeBand.MEDIUM,
        modality="100 surveillance videos, 1080x1920, per-frame head annotations",
        crowdent_use=(
            "Video with consecutive frames, so density and optical-flow velocity can be "
            "estimated on the same footage. That pairing is what Crowdent fuses, and still "
            "images cannot exercise it."
        ),
        caveats=("Surveillance viewpoints; density is moderate rather than crush-level.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="drone-crowd",
        name="DroneCrowd (VisDrone)",
        year=2019,
        task=DatasetTask.TRAJECTORY,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the VisDrone benchmark",
        homepage="https://github.com/VisDrone/VisDrone-Dataset",
        citation="Zhu et al., Detection and Tracking Meet Drones Challenge, TPAMI 2021",
        samples=33600,
        annotations=4864280,
        size_band=SizeBand.LARGE,
        modality="112 drone video clips, 1080x1920, head points with track identities",
        crowdent_use=(
            "Overhead viewpoint with track identities, which is the cleanest public source "
            "for per-person velocity and therefore for velocity variance. Overhead geometry "
            "also keeps homography error small."
        ),
        caveats=(
            "Moving camera. Ego-motion must be removed before optical flow means anything.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="worldexpo-10",
        name="WorldExpo'10 crowd counting",
        year=2015,
        task=DatasetTask.COUNTING,
        access=DatasetAccess.REGISTRATION,
        license="Research use; request access from the authors",
        homepage="https://www.ee.cuhk.edu.hk/~xgwang/expo.html",
        citation="Zhang et al., Cross-scene Crowd Counting via Deep CNN, CVPR 2015",
        samples=3980,
        annotations=199923,
        size_band=SizeBand.MEDIUM,
        modality="1132 surveillance sequences with region-of-interest and perspective maps",
        crowdent_use=(
            "Ships perspective maps alongside the footage, so it is the natural fixture for "
            "testing calibrate_homography and the image-to-ground projection against a "
            "published reference rather than a synthetic checkerboard."
        ),
        caveats=("Older, lower-resolution footage; access is by request.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="nwpu-crowd",
        name="NWPU-Crowd",
        year=2020,
        task=DatasetTask.LOCALIZATION,
        access=DatasetAccess.REGISTRATION,
        license="Research use; complete the author access form",
        homepage="https://gjy3035.github.io/NWPU-Crowd-Sample-Code/",
        citation="Wang et al., NWPU-Crowd: A Large-Scale Benchmark, TPAMI 2021",
        samples=5109,
        annotations=2133375,
        size_band=SizeBand.LARGE,
        modality="high-resolution stills, box and point labels, held-out online test server",
        crowdent_use=(
            "Largest congested benchmark with a sequestered test split, so density-model "
            "claims can be reported without the usual test-set leakage."
        ),
        caveats=(
            "Counts reach thousands per image; resolution is high and disk cost follows.",
            "Test labels are withheld and scored on the maintainers' server.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="jhu-crowd-plus-plus",
        name="JHU-CROWD++",
        year=2020,
        task=DatasetTask.LOCALIZATION,
        access=DatasetAccess.REGISTRATION,
        license="Research use; download form on the dataset homepage",
        homepage="https://www.crowd-counting.com",
        citation="Sindagi et al., JHU-CROWD++, TPAMI 2020",
        samples=4372,
        annotations=1515005,
        size_band=SizeBand.MEDIUM,
        modality="stills with weather labels, blur and occlusion flags, head points",
        crowdent_use=(
            "Weather and degradation labels map directly onto Crowdent quality flags, so it "
            "is the right set for testing that a sick input degrades readiness instead of "
            "silently producing a confident number."
        ),
        caveats=("Adverse-weather subsets are small; do not over-read per-condition results.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="ucf-qnrf",
        name="UCF-QNRF",
        year=2018,
        task=DatasetTask.LOCALIZATION,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the QNRF paper",
        homepage="https://www.crcv.ucf.edu/data/ucf-qnrf/",
        citation="Idrees et al., Composition Loss for Counting, ECCV 2018",
        samples=1535,
        annotations=1251642,
        size_band=SizeBand.MEDIUM,
        modality="high-resolution stills of very dense gatherings, point annotations",
        crowdent_use=(
            "Contains pilgrimage-scale gatherings at densities close to Crowdent's operating "
            "regime, which most counting sets never reach."
        ),
        caveats=(
            "Web-collected imagery with wide viewpoint variation and no camera calibration.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="shanghaitech-a",
        name="ShanghaiTech Part A",
        year=2016,
        task=DatasetTask.COUNTING,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the MCNN paper",
        homepage="https://github.com/desenzhou/ShanghaiTechDataset",
        citation="Zhang et al., Single-Image Crowd Counting via MCNN, CVPR 2016",
        samples=482,
        annotations=241677,
        size_band=SizeBand.SMALL,
        modality="congested free-view stills, point annotations",
        crowdent_use=(
            "Small and fast, so it works as the smoke-test fixture for the density adapter "
            "and the ONNX export path before anything larger is downloaded."
        ),
        caveats=("Too small to support a headline accuracy claim.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="shanghaitech-b",
        name="ShanghaiTech Part B",
        year=2016,
        task=DatasetTask.COUNTING,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the MCNN paper",
        homepage="https://github.com/desenzhou/ShanghaiTechDataset",
        citation="Zhang et al., Single-Image Crowd Counting via MCNN, CVPR 2016",
        samples=716,
        annotations=88488,
        size_band=SizeBand.SMALL,
        modality="fixed-camera street scenes, point annotations",
        crowdent_use=(
            "Fixed viewpoints at sparse-to-moderate density; useful as the low-density end "
            "of a calibration curve so the model is not tuned only on crush conditions."
        ),
        caveats=("Sparse scenes; not representative of the regime that causes harm.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="gcc",
        name="GTA5 Crowd Counting (GCC), synthetic",
        year=2019,
        task=DatasetTask.LOCALIZATION,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; derived from GTA5, cite the GCC paper",
        homepage="https://github.com/gjy3035/GCC-CL",
        citation="Wang et al., Learning from Synthetic Data for Crowd Counting, CVPR 2019",
        samples=15211,
        annotations=7625843,
        size_band=SizeBand.LARGE,
        modality="synthetic scenes with exact ground truth, controlled weather and time",
        crowdent_use=(
            "Exact ground truth and no real person in frame, so it carries no privacy load. "
            "The right place to pretrain and to build twin experiments where the true state "
            "is known and assimilation can be scored honestly."
        ),
        caveats=(
            "Synthetic. A result here is evidence about the method, never about a venue.",
            "Derived from a commercial game engine; check the terms before redistributing.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="rgbt-cc",
        name="RGBT-CC (RGB-thermal crowd counting)",
        year=2021,
        task=DatasetTask.COUNTING,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the RGBT-CC paper",
        homepage="https://lingboliu.com/RGBT_Crowd_Counting.html",
        citation="Liu et al., Cross-Modal Collaborative Representation Learning, CVPR 2021",
        samples=2030,
        annotations=138389,
        size_band=SizeBand.SMALL,
        modality="aligned RGB and thermal pairs, point annotations",
        crowdent_use=(
            "Night and low-light behaviour. Many crowd incidents happen after dark, and an "
            "RGB-only density model degrades there without saying so."
        ),
        caveats=("Thermal sensors are not present at most venues Crowdent targets.",),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="eth-ucy",
        name="ETH and UCY pedestrian trajectories",
        year=2009,
        task=DatasetTask.TRAJECTORY,
        access=DatasetAccess.RESEARCH_USE,
        license="Research use; cite the ETH and UCY papers",
        homepage="https://github.com/crowdbotp/OpenTraj",
        citation="Pellegrini et al., ICCV 2009; Lerner et al., Eurographics 2007",
        samples=1500,
        annotations=None,
        size_band=SizeBand.SMALL,
        modality="overhead world-coordinate trajectories across five scenes, 2.5 Hz",
        crowdent_use=(
            "Already in world coordinates, so route-choice and desired-direction behaviour "
            "can be checked without any homography of our own in the loop."
        ),
        caveats=(
            "Low density. It exercises route choice, not crush physics.",
            "Sample count is pedestrians tracked, not frames.",
        ),
        terms_reviewed=_REVIEWED,
    ),
    Dataset(
        identifier="atc-shopping-mall",
        name="ATC shopping centre pedestrian tracking",
        year=2013,
        task=DatasetTask.TRAJECTORY,
        access=DatasetAccess.REGISTRATION,
        license="Research use with citation; request access from ATR",
        homepage="https://dil.atr.jp/crest2010_HRI/ATC_dataset/",
        citation="Brščić et al., Person Tracking in Large Public Spaces, THMS 2013",
        samples=92,
        annotations=None,
        size_band=SizeBand.LARGE,
        modality="92 days of trajectories from 49 3D range sensors in one building",
        crowdent_use=(
            "Long horizon in a fixed geometry, which is what a schedule-driven Tier 0 "
            "forecast needs: recurring daily and weekly inflow patterns in a real venue."
        ),
        caveats=(
            "A shopping centre, not a mass gathering. Sample count is days, not frames.",
            "Range-sensor tracks, so it validates counting and flow rather than imagery.",
        ),
        terms_reviewed=_REVIEWED,
    ),
)

_BY_IDENTIFIER = {dataset.identifier: dataset for dataset in DATASETS}


def all_datasets() -> tuple[Dataset, ...]:
    """Every registered dataset."""

    return DATASETS


def get_dataset(identifier: str) -> Dataset:
    """Look up one dataset, or raise with the list of known identifiers."""

    try:
        return _BY_IDENTIFIER[identifier]
    except KeyError as error:
        known = ", ".join(sorted(_BY_IDENTIFIER))
        raise KeyError(f"unknown dataset {identifier!r}; known datasets: {known}") from error


def find_datasets(
    *,
    task: DatasetTask | None = None,
    access: DatasetAccess | None = None,
    max_size: SizeBand | None = None,
) -> tuple[Dataset, ...]:
    """Filter the registry. ``max_size`` keeps bands at or below the given band."""

    order = {
        SizeBand.SMALL: 0,
        SizeBand.MEDIUM: 1,
        SizeBand.LARGE: 2,
        SizeBand.VERY_LARGE: 3,
    }
    selected: Iterable[Dataset] = DATASETS
    if task is not None:
        selected = (item for item in selected if item.task is task)
    if access is not None:
        selected = (item for item in selected if item.access is access)
    if max_size is not None:
        ceiling = order[max_size]
        selected = (item for item in selected if order[item.size_band] <= ceiling)
    return tuple(selected)


def acquisition_plan(dataset: Dataset, *, destination: str = "data/<identifier>") -> str:
    """Human-readable acquisition steps. Crowdent never runs these for you."""

    lines = [
        f"{dataset.name} ({dataset.identifier})",
        f"  homepage       {dataset.homepage}",
        f"  access         {dataset.access.value}",
        f"  license        {dataset.license}",
        f"  disk           {dataset.size_band.value}",
        f"  terms reviewed {dataset.terms_reviewed.isoformat()}",
        "",
        "Steps:",
        f"  1. Open {dataset.homepage} and read the current terms yourself.",
    ]
    if dataset.access is DatasetAccess.REGISTRATION:
        lines.append(
            "  2. Complete the access request the authors require. "
            "Crowdent will not submit forms or accept terms on your behalf."
        )
    else:
        lines.append("  2. Confirm the license still permits your intended use.")
    lines.extend(
        [
            f"  3. Download to {destination} on the research machine. "
            "data/ is gitignored; never commit imagery or weights.",
            "  4. Record checksums:  crowdent dataset manifest <identifier> --path <dir>",
            "  5. Re-verify later:   crowdent dataset verify <identifier> --path <dir>",
            "",
            f"Cite: {dataset.citation}",
        ]
    )
    if dataset.caveats:
        lines.append("")
        lines.append("Caveats:")
        lines.extend(f"  - {caveat}" for caveat in dataset.caveats)
    return "\n".join(lines)


def __iter__() -> Iterator[Dataset]:  # pragma: no cover - convenience only
    return iter(DATASETS)


__all__ = [
    "DATASETS",
    "Dataset",
    "DatasetAccess",
    "DatasetTask",
    "SizeBand",
    "acquisition_plan",
    "all_datasets",
    "find_datasets",
    "get_dataset",
]
