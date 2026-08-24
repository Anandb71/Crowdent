# Agent notes

This repository is an offline crowd-risk **research** platform.

## Invariants

- Never add gate, PA, PLC, or signage actuation.
- Never emit countdown or advice unless `ReadinessState.READY`.
- Never import `torch` from `src/crowdent`.
- Never let field profiles inherit demo network or docs settings.
- Never bind non-loopback without `allow_lan: true`.
- Never accept device identifiers in passive aggregates.
- Crowd pressure is an index in `s^-2`, not Pascals.
- Optical flow is not density.
- Do not commit videos, weights, `.env`, or personal identifiers.
- Do not label releases deployment-ready.

## Tooling

- Python 3.13, uv, ruff, mypy, pytest
- Node 24, oxlint, vitest, Playwright, Vite
- Tests live in `tests/` and `frontend/src/*.test.tsx`

## Docs

User-facing documentation is under `docs/`. Keep the research-only warning
in README and the operator console.
