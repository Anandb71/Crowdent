# Operator console

The console is a dark control-room UI for a single local operator. It is a
research instrument, not a certified command system.

## Permanent banners

Every view shows:

- `DEMO · SYNTHETIC` in deterministic demo mode
- `RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED`
- `No hardware actuation`
- `No cloud telemetry`

## Layout

- Venue map with ranked zones (density, speed, crowd-pressure index, sensor
  health).
- Side-by-side chart: no-action p10/p50/p90 versus a named intervention.
- Sensor health list with age and quality flags.
- Instruction lifecycle panel.
- Failure-injection control for tabletop drills.

## Human lifecycle

Recommendations never execute. The recorded states are:

1. Draft
2. Acknowledge review
3. Supervisor accepts or rejects
4. Human-reported physical action confirmed

`PHYSICAL ACTION CONFIRMED` means a person reported that something happened
outside the software. It does not mean Crowdent moved a gate.

## Failure injection

The demo can inject `stale`, `conflict`, or `clock` faults. Those states
hide countdown (`--:--`) and replace advice with
`No recommendation available`. Use this during tabletop exercises to
practice fail-degraded behaviour.

## Keyboard

Primary controls are reachable by tab order. The first control in the demo
is pause/play for synthetic playback.

## Data source

On load the console asks `GET /api/v1/demo/snapshot`. If the API is
unreachable it falls back to the bundled synthetic snapshot so the UI can
still be reviewed offline.
