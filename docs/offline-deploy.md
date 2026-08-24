# Offline deployment

This is a **local research packaging** guide. It is not a production
operations runbook and it does not make Crowdent deployment-certified.

## Bind and network

Default host is `127.0.0.1`. A non-loopback bind requires
`network.allow_lan: true` and must not use a wildcard trusted host. CORS is
empty in field profiles. OpenAPI docs are disabled in field mode.

Do not expose the process to the public internet.

## Files on disk

Copy the repository, Python virtual environment from `uv sync`,
`frontend/dist`, and a validated YAML profile. Keep secrets out of git:

- `.env` is gitignored. Use `.env.example` as a template.
- Model weights (`*.onnx`, `*.pt`) are gitignored.
- Recorded video is gitignored.
- Runtime state lives under `.crowdent/` by default.

## Replay bundles

`crowdent replay bundle.zip --verify-only` checks required members,
`research_only: true`, and SHA-256 hashes. Serve a verified bundle only in
`REPLAY_RESEARCH`.

## Storage

One writer per SQLite path. WAL + `synchronous=FULL`. Audit records are
append-only and hash-chained. Chunk writes are atomic (temp file then
replace).

## Bootstrap (Windows)

```powershell
uv sync
cd frontend
npm ci
npm run build
cd ..
uv run crowdent doctor --json
```

## Bootstrap (POSIX)

```sh
uv sync
cd frontend && npm ci && npm run build && cd ..
uv run crowdent doctor --json
```

## What not to do

- Do not label a GitHub release "production" or "deployment-ready".
- Do not ship untrained ONNX fixtures as field models.
- Do not store device identifiers, credentials, or student IDs in the repo.
