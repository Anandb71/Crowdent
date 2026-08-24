# Troubleshooting

## `crowdent demo` opens but the console is empty

Build the frontend (`npm run build` in `frontend/`) or run Vite on
`127.0.0.1:5173`. `doctor` reports whether `frontend/dist/index.html`
exists.

## Health ready returns 503

`/health/ready` is 503 until a `READY` forecast is present. Live (`/health/live`)
stays 200. This is intentional: readiness is not liveness.

## Countdown shows `--:--`

Readiness is not `READY`. Check the failure-injection control in demo, or
quality flags on `/api/v1/forecasts/latest`. Stale, conflicting, missing,
calibration, OOD, ensemble, numerical, and clock faults all suppress advice.

## `allow_lan` validation error

The host is not loopback. Set `network.allow_lan: true` only for an
intentional LAN research bind, and never with a wildcard trusted host.

## Field mode 401

Field research requires `X-Crowdent-Actor` and `X-Crowdent-Role`. Demo mode
injects a demo operator for local exploration only.

## Writer already active

SQLite allows one writer per path. Close the other Crowdent process or use
a different `storage.root`.

## RTSP rejected

Private, loopback, link-local, and reserved hosts need an explicit
allowlist. Credentials in the URL are rejected. Paths must match a safe
character set.

## Type or lint failures after a local edit

```powershell
uv run ruff check --fix src tests training
uv run mypy src/crowdent
cd frontend
npm run check
```

## Still stuck

Open a bug with the output of `uv run crowdent doctor --json`, OS, Python
version, and a redacted config. Do not attach real video or credentials.
