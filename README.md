# Crowdent

**RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED**

Crowdent is an offline, uncertainty-aware research platform for crowd-crush
forecasting from existing venue sensors. It produces human-reviewed advisories.
It does not actuate gates, public-address systems, or signage, and it is not a
certified public-safety product.

Use this software only in a supervised research, tabletop, or recorded-replay
setting. Field deployments require independent venue calibration, hold-out
validation, a signed readiness manifest, and an explicit operational authority
that this repository does not grant.

## What it does

- Fuses camera-derived density and optical-flow velocity with optional
  schedules, counters, and anonymous zone aggregates.
- Forecasts route-aware crowd state with ensemble uncertainty and explicit
  SI units.
- Compares a no-action baseline against a hypothetical intervention on a
  shared initial ensemble.
- Suppresses countdown and advice whenever readiness is not `READY`.
- Records a hash-chained local audit trail of human advisory decisions.

## What it does not do

- No hardware actuation API, PLC, or signage driver.
- No cloud telemetry and no default LAN bind.
- No deployment certificate, NDMA approval, or operational warranty.
- No claim that Helbing 2007 defaults are universal venue thresholds.

Crowd pressure in this codebase is an **index** `density × velocity variance`
with units `s^-2`. It is not mechanical pressure in Pascals. Optical flow is
not a density estimator; density comes from an independent adapter.

## Quick start

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js 24, and npm.
There is no Docker image in this repository.

```powershell
uv sync
cd frontend
npm install
npm run build
cd ..
uv run crowdent doctor --json
uv run crowdent demo --no-browser
```

Then open `http://127.0.0.1:8000` if the frontend bundle exists, or run the
console separately:

```powershell
cd frontend
npm run dev
```

The deterministic demo is synthetic. Demo badges, `research_only: true`, and
`hardware_actuation_available: false` stay visible on every screen.

## Tests

```powershell
uv run ruff check src tests training
uv run mypy src/crowdent
uv run pytest
cd frontend
npm run check
```

Playwright end-to-end tests:

```powershell
cd frontend
npx playwright install chromium
npm run test:e2e
```

## Runtime modes

| Mode | Purpose |
| --- | --- |
| `DEMO_DETERMINISTIC` | Seeded synthetic venue. Docs enabled. Demo actor headers. |
| `REPLAY_RESEARCH` | Immutable recorded bundle. No live cameras required. |
| `FIELD_RESEARCH` | Local research run. Docs disabled. Authentication required. Field does not inherit demo values. |

Non-loopback binds require `network.allow_lan: true` in a validated YAML
profile. Copy `configs/crowdent.example.yaml` and replace the site id.

## Documentation

- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Algorithms and units](docs/algorithms.md)
- [Operator console](docs/operator.md)
- [Safety and readiness](docs/safety-readiness.md)
- [Offline deployment](docs/offline-deploy.md)
- [Validation](docs/validation.md)
- [Threat model](docs/threat-model.md)
- [Privacy](docs/privacy.md)
- [Model card](docs/model-card.md)
- [Data card](docs/data-card.md)
- [Troubleshooting](docs/troubleshooting.md)
- [References](docs/references.md)

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Citation

See [CITATION.cff](CITATION.cff). Literature defaults (Helbing 2007 and NDMA
crowd-management guidance) are cited in [docs/references.md](docs/references.md).
They are starting points for venue-specific calibration, not shipping thresholds.
