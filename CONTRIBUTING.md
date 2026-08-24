# Contributing

**RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED.** Do not add hardware actuation,
cloud telemetry, or "deployment-ready" language.

## Before you start

1. Read [docs/safety-readiness.md](docs/safety-readiness.md) and
   [docs/privacy.md](docs/privacy.md).
2. Keep Python 3.13 and Node 24.
3. Do not commit videos, weights, `.env` files, or personal identifiers.

## Development loop

```powershell
uv sync
uv run ruff check --fix src tests training
uv run mypy src/crowdent
uv run pytest
cd frontend
npm ci
npm run check
```

## Pull requests

- Use the PR template.
- Add or update tests for behaviour changes.
- Keep units, provenance, and readiness visible on new contracts.
- Field profiles must not inherit demo defaults.
- Runtime code must not import `torch`.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file public issues for credential or
SSRF bypasses.
