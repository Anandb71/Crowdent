# Validation

Validation in this repository is software and numerical evidence, not a
venue certification.

## Automated suite

- Python: `uv run pytest` (contracts, safety, ingest SSRF/privacy, numerics,
  storage, API, CLI doctor, runtime isolation from PyTorch, forecast
  verification and calibration, dataset registry and manifests).
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

## Forecast verification

`crowdent.verification` provides the evidence that a forecast is worth
showing a human: fair CRPS and energy score against a stated baseline,
Brier score with the Murphy decomposition for threshold exceedance, and
calibration diagnostics (rank histogram, spread-skill ratio, interval
coverage). Reports flag under-dispersion, coverage below what the
ensemble size can attain, and any lead time with no skill over its
baseline.

The unit tests check these against closed forms rather than against
themselves: ensemble CRPS is compared with the analytic Gaussian CRPS,
the Brier decomposition identity is asserted exactly, the energy score is
shown to reduce to CRPS in one dimension, and propriety is checked by
confirming that a biased or overconfident ensemble scores worse than an
honest one.

Running a verification report is not validation of a venue. See
[research/verification-protocol.md](research/verification-protocol.md)
for the protocol and its limits.

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
