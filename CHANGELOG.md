# Changelog

All notable changes to this project are documented here.

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
