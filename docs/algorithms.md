# Algorithms and units

Every numeric contract carries explicit SI units. If a quantity cannot be
assigned a unit, the code refuses to treat it as a physical measurement.

## Density and flow

Density is estimated independently of optical flow, in people per square
metre (`people/m^2`). Farneback optical flow produces image-plane velocities
that a surveyed homography maps into metres per second. Flow is not a
density estimator.

Crowd flux through a line is `density × velocity · n` with units
`people/(m·s)`.

## Crowd-pressure index

The crowd-pressure index is

```
P_index = density × velocity_variance
```

with units `s^-2`. This is **not** mechanical pressure in Pascals. The
label in code is `CrowdPressureIndex` and the unit string contains `index`.

Helbing, Johansson, and Al-Abideen (2007) reported a literature default near
`0.02 s^-2` for a related crowd-pressure signal and a flow around
`0.8 people/(m·s)`. Those numbers are **venue-calibrated literature
defaults**, not universal tripwires. A field profile must replace them with
surveyed, hold-out-validated thresholds.

## Speed-density relation

Route desired speeds use the Weidmann relation with a default free speed of
`1.34 m/s` and jam density `5.4 people/m^2`. Both are configurable. They are
not claimed to be India-specific or venue-universal.

## Routing and conservation

Travel times are a grid eikonal approximation (Dijkstra on four-connected
walkable cells). Desired directions point toward a lower travel-time
neighbour. Continuity is a first-order upwind finite-volume step with CFL
subcycling. Mass leaving through marked exits is accounted as outflow.
Negative density after a step is treated as a numerical failure.

## Assimilation and forecasts

A localized deterministic ensemble Kalman filter fuses linear observations
with distance-based covariance localisation and innovation gating. Forecasts
report p10 / p50 / p90 and threshold exceedance probabilities at lead times
5, 10, 15, 30, 45, and 60 minutes.

Counterfactuals branch from a **common initial ensemble**. A no-action
baseline and an intervention branch share the same starting members so the
comparison is a hypothetical simulation, not a causal claim about a live
venue.

## Fail-degraded numerics

Non-finite arrays, conservation failures, empty ensembles, or out-of-support
homography projections raise errors that safety maps to `UNKNOWN` or
`DEGRADED`. Countdown and advice are forbidden unless readiness is `READY`.
