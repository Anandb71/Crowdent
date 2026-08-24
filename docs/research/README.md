# Research notes

Background and method for the parts of Crowdent that make empirical
claims. These documents are research material, not certification, and
nothing here authorises field deployment.

- [Literature review](literature.md) — where forecast lead time actually
  comes from, and why physical precursors give seconds rather than
  minutes.
- [Dataset survey](datasets.md) — which public datasets can falsify which
  Crowdent claim, and the order to acquire them in. Crowdent downloads
  nothing.
- [Verification protocol](verification-protocol.md) — how to test whether
  a forecast is skilful and whether its uncertainty is honest, using
  `crowdent.verification`.

## The short version

The published physics precursors of crowd turbulence give about one
second of warning from positional fluctuations, and tens of seconds from
the collective oscillation reported at San Fermín. Neither is enough for
a human to reach a gate.

Usable lead time comes instead from mass conservation and from scheduled
arrivals, which are knowable before density becomes dangerous. That is an
argument for treating the schedule tier as the primary source of warning
and the physics precursors as *confirmation* that a dangerous regime has
been entered.

A forecast that cannot beat persistence is not a forecast, and an
interval that does not contain the truth as often as it claims is
decoration. Both are now testable in this repository, and neither has
been established on field data.
