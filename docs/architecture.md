# Architecture

Crowdent is an offline modular monolith: one Python process, one SQLite
writer, and a React operator console. There is no microservice mesh and no
cloud control plane.

## Processes

```
sensors / recorded files / synthetic demo
        │
        ▼
  ingest adapters ──► perception ──► numerics ──► safety
        │                │              │            │
        └────────────────┴──────────────┴────────────┘
                         │
                         ▼
              ResearchService (advisory only)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     FastAPI API    SQLite+WAL     static console
```

The console is a local SPA. In demo mode FastAPI can serve `frontend/dist`.
In development Vite talks to the API on loopback.

## Layers

| Layer | Package | Responsibility |
| --- | --- | --- |
| Contracts | `crowdent.contracts` | Frozen Pydantic models, units, provenance, readiness |
| Runtime | `crowdent.runtime` | Immutable YAML profiles; field does not inherit demo |
| Ingest | `crowdent.ingest` | Schedules, counters, anonymous aggregates, recorded video, RTSP allowlists |
| Perception | `crowdent.perception` | Homography, Farneback flow, ONNX density, crowd-pressure index |
| Numerics | `crowdent.numerics` | Weidmann speeds, eikonal routes, upwind continuity, localized EnKF |
| Safety | `crowdent.safety` | Fail-degraded readiness and advisory-only policy |
| Auth | `crowdent.auth` | Argon2, TOTP, JWT sessions, role checks |
| Storage | `crowdent.storage` | Single-writer SQLite, hash-chained audit, atomic `.npz` chunks |
| API | `crowdent.api` | FastAPI research surface, no actuation routes |
| Console | `frontend/` | Ranked zones, ensemble chart, human lifecycle |

## Runtime modes

`DEMO_DETERMINISTIC`, `REPLAY_RESEARCH`, and `FIELD_RESEARCH` are immutable
for a process lifetime. Switching modes requires a new process and a new
config hash.

## Data stores

- SQLite in WAL mode with one writer lock per database path.
- Append-only audit records with a SHA-256 hash chain.
- Atomic NumPy chunk files plus a manifest for replay export.
- Raw video is off by default and never required for the demo.

## Non-goals

- No actuator, PLC, or digital-signage client.
- No automatic instruction execution.
- PyTorch is training-only. Runtime inference uses ONNX Runtime.
