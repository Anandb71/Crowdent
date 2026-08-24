# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- `crowdent.verification`: proper scoring rules (fair CRPS, energy score,
  pinball loss, Brier score with Murphy decomposition) and calibration
  diagnostics (Talagrand rank histogram, reliability curve, spread-skill
  ratio, interval coverage), plus lead-time verification reports that
  flag under-dispersion, missing coverage, and absent skill over baseline.
- `crowdent.datasets`: registry of fourteen public crowd datasets with
  access terms, size bands, caveats, and the Crowdent claim each one can
  falsify. SHA-256 manifests for local copies so a benchmark result can
  name the exact bytes it scored.
- CLI: `crowdent dataset list`, `show`, `manifest`, and `verify`.
- Research notes under `docs/research/`: literature review on forecast
  lead time, dataset survey, and the verification protocol.

### Changed

- Interval coverage is computed from order statistics and reported
  against the coverage a finite ensemble can actually attain, so a
  correctly calibrated small ensemble is no longer flagged as miscalibrated.
- Frontend dependencies updated (`lucide-react`, `oxlint`).

### Safety

- The verification package holds no readiness state, emits no countdown,
  and has no hardware interface. `VerificationReport.calibrated` is a
  screening result and is never treated as readiness.
- The datasets package performs no network access and accepts no licence
  on an operator's behalf. A test asserts it imports no HTTP client.

## 0.1.0 — 2026-08-24

### Added

- Offline modular monolith: FastAPI research API, SQLite WAL storage, React
  operator console.
- Runtime modes `DEMO_DETERMINISTIC`, `REPLAY_RESEARCH`, `FIELD_RESEARCH`.
- Versioned contracts with units, provenance, quality flags, and readiness.
- Fail-degraded safety policy: no countdown or advice unless `READY`.
- Ingest adapters for schedules, counters, anonymous aggregates, recorded
  video path confinement, and RTSP allowlists.
- Perception: homography, Farneback flow, ONNX density adapter, crowd-pressure
  index (`s^-2`, not Pascals).
- Numerics: Weidmann speeds, eikonal routes, upwind continuity, localized
  deterministic EnKF, quantile forecasts, fair counterfactuals.
- Human advisory lifecycle with hash-chained audit.
- Deterministic synthetic demo and local CLI (`demo`, `replay`, `serve`,
  `doctor`).
- Apache-2.0 licensing, documentation, and GitHub CI.

### Safety

- No hardware actuation API.
- Loopback bind by default.
- PyTorch isolated to the optional training extra.
