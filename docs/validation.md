# Validation

Validation in this repository is software and numerical evidence, not a
venue certification.

## Automated suite

- Python: `uv run pytest` (contracts, safety, ingest SSRF/privacy, numerics,
  storage, API, CLI doctor, runtime isolation from PyTorch).
- Lint and types: `uv run ruff check src tests training` and
  `uv run mypy src/crowdent`.
- Frontend: `npm run lint`, `npm run typecheck`, `npm run test`,
  `npm run build`.
- Playwright: `npm run test:e2e` against the local Vite server.

CI runs the Python suite on Ubuntu and Windows, the frontend check job, a
secret scan, SBOM generation, and CodeQL.

## Numerical checks

Continuity tests require non-negative density and mass balance within a
tight tolerance after accounting for exit outflow. Ensemble forecasts require
finite samples and at least two members. Homography calibration rejects
collinear or high-reprojection geometries. Crowd-pressure tests assert the
unit string is an index, not Pascals.

## Chaos / fail-degraded

Stale, conflicting, missing, calibration, OOD, ensemble, numerical, and
clock failures suppress countdown and advice. The operator console mirrors
that behaviour with the failure-injection control. The API has no `actuate`
or hardware routes.

## What this does not prove

Passing CI does not mean:

- the density model is accurate at a real venue
- Helbing or Weidmann defaults match a festival, station, or temple
- operators may rely on countdown during a live event
- the system is certified against NDMA or any other authority

Field use needs surveyed geometry, independent hold-outs by density regime,
privacy review, and a signed readiness manifest produced outside this repo.
