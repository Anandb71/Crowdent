# Safety and readiness

Crowdent is fail-degraded by construction. Advice is a privilege of a
healthy research run, not a default.

## Readiness states

| State | Meaning | Countdown | Advice |
| --- | --- | --- | --- |
| `READY` | Configured checks passed | Allowed | Allowlisted recommendations only |
| `DEGRADED` | Stale or conflicting sources | Forbidden | Forbidden |
| `UNKNOWN` | Missing input, invalid calibration, OOD, ensemble failure, numerical failure, or clock error | Forbidden | Forbidden |

The `Forecast` contract refuses to serialise countdown or advice unless
`readiness == READY`.

## Quality flags

- `STALE_INPUT`
- `CONFLICTING_INPUT`
- `MISSING_INPUT`
- `INVALID_CALIBRATION`
- `OUT_OF_DOMAIN`
- `ENSEMBLE_FAILURE`
- `NUMERICAL_FAILURE`
- `CLOCK_ERROR`

## Recommendation policy

Allowed actions are configured per profile. Defaults are `PAUSE_INFLOW`,
`METER_INFLOW`, and `HOLD_ARRIVAL`. Tokens containing `ACTUATE`,
`AUTOMATIC`, or `EVACUATE_NOW` are blocked even if a caller asks for them.

There is no actuation client. `hardware_actuation_available` is always
`false` on health, status, forecast, and instruction payloads.

## Instruction lifecycle

Transitions are explicit, authorised, and audited:

`draft → acknowledged → accepted | rejected`
`accepted → physical_action_confirmed`
`draft | acknowledged → expired` when TTL elapses

An auditor can read the hash-chained audit log. An auditor cannot create or
accept instructions.

## Research-gated operations

A field profile should set `require_signed_readiness_manifest: true`. The
software still does not certify a venue. Certification is an external
process involving surveyed geometry, hold-out validation, privacy review,
and an operational authority outside this repository.
