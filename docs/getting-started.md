# Getting started

**RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED.** Crowdent runs locally. It does
not grant operational authority and it does not talk to gates or PA systems.

## Prerequisites

- Python 3.13 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) 0.11 or later
- Node.js 24 (see `.node-version`) and npm
- Windows, Linux, or macOS. No Docker image is provided.

Optional:

- A GPU is not required. ONNX Runtime uses the CPU provider.
- PyTorch is an optional `training` extra and must not be imported by the
  runtime package.

## Install

From the repository root:

```powershell
uv sync
cd frontend
npm ci
npm run build
cd ..
uv run crowdent doctor --json
```

`doctor` checks Python version, local scientific imports, loopback defaults,
and whether `frontend/dist` exists. A missing frontend bundle is a warning,
not a hard failure.

## Run the deterministic demo

```powershell
uv run crowdent demo --no-browser
```

The API listens on `127.0.0.1:8000`. If `frontend/dist/index.html` exists,
the same process serves the operator console. Otherwise start Vite:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

The demo snapshot is synthetic. Treat every number as a fixture.

## Other commands

```powershell
uv run crowdent replay path\to\bundle.zip --verify-only
uv run crowdent serve --config configs\crowdent.example.yaml --profile field
```

Field mode disables OpenAPI docs and requires `X-Crowdent-Actor` plus
`X-Crowdent-Role` headers. Copy the example YAML, set a surveyed `site_id`,
and keep `allow_lan: false` unless you have an explicit LAN research need.

## Configuration

Profiles live under `configs/`. Field does not inherit demo CORS, ports, or
docs flags. Invalid YAML, extra keys, and non-loopback binds without
`allow_lan` fail closed.

## Next reading

- [Architecture](architecture.md)
- [Operator console](operator.md)
- [Safety and readiness](safety-readiness.md)
- [Offline deployment](offline-deploy.md)
