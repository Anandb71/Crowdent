# Literature review: where the lead time actually comes from

This document exists to answer one question honestly: **how far ahead can
a crowd-crush risk be seen, and by what signal?** The answer constrains
what Crowdent may claim, and it is less flattering than the pitch for
this class of system usually admits.

Everything here is literature. Crowdent has reproduced none of it. Values
quoted are starting points for venue-specific calibration, never shipping
thresholds. See [references.md](../references.md) for the citation list
this document extends.

## 1. The transition sequence

Helbing, Johansson and Al-Abideen (2007) analysed video of the 2006 Hajj
and described crowd motion passing through three regimes as density
rises: laminar flow, then stop-and-go waves travelling upstream against
the crowd, then *crowd turbulence*, in which clusters are pushed in
apparently random directions and force is released in irregular bursts.

That work is the origin of the quantity this repository calls the crowd
pressure index: local density multiplied by the variance of velocity,
with units `s^-2`. The commonly cited precursor value near `0.02 s^-2`
comes from this line of work.

Two properties of that index matter for the architecture:

- It is **not** mechanical pressure in Pascals. The repository enforces
  this in code and in tests, and the distinction must survive every
  rewrite of the operator console.
- It is a *state* variable, not a forecast. Observing that turbulence has
  begun is observing that the dangerous regime has already arrived.

## 2. How much warning do physical precursors actually give?

This is where the literature is sobering.

Bottinelli and Silverberg (2018) took a model-free approach to video of
an Oasis concert crowd, applying mode analysis from materials science to
attendee positional fluctuations. They were able to forecast the spatial
pattern of collective motion and identify temporal patterns preceding a
density wave — with a lead time of **approximately one second**. They
name extending that window as future work.

Gu, Guiselin, Bain, Zuriguel and Bartolo (2025) analysed confined crowds
at the San Fermín festival across four years, at densities reaching
roughly nine people per square metre. Above a critical density, they
found that hundreds of people spontaneously organise into macroscopic
chiral oscillators — a periodic orbital motion with a period of about
**eighteen seconds**, arising with no external stimulus. The onset
density and the precise transition should be read from the paper rather
than from this summary.

Both results are real and important. Neither delivers minutes.

**The consequence for Crowdent is structural.** A system that promised
5 to 60 minutes of lead time from turbulence precursors would be
misrepresenting the physics. Seconds of warning is enough to explain what
is happening; it is not enough for a human to walk to a gate.

## 3. Where minutes actually come from

Lead time on the scale a human can act on does not come from the
turbulent state at all. It comes from quantities that are knowable
*before* density becomes dangerous:

| Source | Mechanism | Order of lead time |
| --- | --- | --- |
| Scheduled arrivals | Train timetable, session end, procession start | Tens of minutes |
| Mass conservation | Counted inflow with bounded egress capacity | Minutes |
| Route geometry | Travel time along a constrained path | Minutes |
| Density and flow state | Current occupancy against capacity | Minutes |
| Collective oscillation | Onset above critical density | Tens of seconds |
| Positional fluctuations | Pre-wave spatiotemporal structure | About one second |

The top of that table is arithmetic, not machine learning. If a platform
empties 2,000 people into a corridor whose egress capacity is known, the
resulting occupancy is a conservation calculation, and it can be run
before anybody is uncomfortable. This is the tier the deck calls Tier 0,
and the literature supports treating it as the primary source of usable
warning rather than as a nicety.

The bottom of the table is where the physics precursors live. They are
valuable for a different job: **confirming that the dangerous regime has
been entered**, and thereby validating or falsifying a forecast that was
issued earlier from conservation.

## 4. Modelling at high density

Chatagnon, Tordeux and Chraibi (2025) review the state of the art in
dense crowd dynamics and describe a shift away from conventional
pedestrian models toward frameworks built specifically for high density,
where physical contact and force transmission between bodies dominate.
Their conclusion is explicit that further experimental and modelling work
is needed to capture high-density dynamics.

The practical reading for this repository: a speed-density relation such
as Weidmann's is a defensible default in the laminar and congested
regimes, and it is *outside its fitted range* in the turbulent regime.
Crowdent should degrade rather than extrapolate confidently there, which
is what the readiness machinery is for.

## 5. What Crowdent has not shown

Stated plainly, so nobody has to infer it:

- No reproduction of the Helbing transition sequence on any dataset.
- No reproduction of the 18-second oscillation of Gu et al.
- No hold-out validation of the density model at a real venue.
- No evidence that `0.02 s^-2` is the correct threshold for any specific
  site. It is a literature value from one setting.
- No demonstration that forecast uncertainty is calibrated on field data.
  The machinery to test that now exists in `crowdent.verification`, and
  the protocol is in [verification-protocol.md](verification-protocol.md),
  but a protocol is not a result.

## 6. Open questions worth a Review 2

1. **Does conservation-based forecasting beat persistence?** This is the
   first question, it needs no new sensor, and it is answerable today on
   recorded timelines with `verify_ensemble_forecast`. A CRPS skill score
   at or below zero against persistence would mean the forecast engine is
   adding nothing.
2. **Is the ensemble calibrated, or merely confident?** Rank histogram
   and spread-skill on a recorded timeline answer this directly.
3. **Can the oscillation of Gu et al. be detected from an ordinary venue
   camera** rather than the instrumented overhead view they used? If yes,
   it is a strong confirmation signal. If no, it stays literature.
4. **Does the pressure index lead or lag occupancy** in the Jülich
   experiments? A precursor that lags is not a precursor.

## Bibliography

Bottinelli, A., and Silverberg, J. L. (2018). Can high-density human
collective motion be forecasted by spatiotemporal fluctuations?
*arXiv:1809.07875* [physics.soc-ph].
https://arxiv.org/abs/1809.07875

Chatagnon, T., Tordeux, A., and Chraibi, M. (2025). Exploring Dense Crowd
Dynamics: State of the Art and Emerging Paradigms. *arXiv:2505.05826*.
https://arxiv.org/abs/2505.05826

Gu, F., Guiselin, B., Bain, N., Zuriguel, I., and Bartolo, D. (2025).
Emergence of collective oscillations in massive human crowds. *Nature*,
638(8049). https://doi.org/10.1038/s41586-024-08514-6
Data and code: https://doi.org/10.5281/zenodo.14050598 (CC BY 4.0)

Helbing, D., Johansson, A., and Al-Abideen, H. Z. (2007). Dynamics of
crowd disasters: An empirical study. *Physical Review E*, 75(4), 046109.
https://doi.org/10.1103/PhysRevE.75.046109

Forschungszentrum Jülich, Institute for Advanced Simulation 7.
*Pedestrian Dynamics Data Archive*. https://doi.org/10.34735/ped.da
