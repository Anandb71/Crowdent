# Agent notes

StillDot is an offline smartphone dead-reckoning **research demo**
for SIH26168.

## Invariants

- Never add gate, PA, PLC, or signage actuation.
- Never import `torch` from `src/stilldot`.
- Never bind non-loopback without an explicit, refused-by-default check.
- Never claim a deployment-ready release.
- Never quote drift without distance, duration, and scenario.
- Optical-flow / crowd-density leftovers do not belong in this tree.
- Do not commit videos, `.env`, or personal identifiers.
- Do not download IO-VNBD from the engine. Record terms; do not ingest.
- The network estimates speed and uncertainty. The filter estimates
  position. Do not train a network to emit coordinates.

## Tooling

- Python 3.13, uv, ruff, mypy, pytest
- Node 24, oxlint, vitest, Playwright, Vite
- Tests live in `tests/` and `frontend/src/*.test.tsx`

## Docs

User-facing documentation is under `docs/` and `README.md`. Keep the
research-only warning on the console and in the README.
