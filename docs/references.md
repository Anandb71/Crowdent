# References

Literature values below are **starting points for venue-specific
calibration**. They are not shipping thresholds and they are not a
certification.

## Crowd dynamics

Helbing, D., Johansson, A., and Al-Abideen, H. Z. (2007). Dynamics of
crowd disasters: An empirical study. *Physical Review E*, 75(4), 046109.
https://doi.org/10.1103/PhysRevE.75.046109

Reported literature defaults commonly cited from this line of work include
a crowd-pressure signal near `0.02 s^-2` and flows near `0.8 people/(m·s)`.
Crowdent treats crowd pressure as an index (`density × velocity variance`,
units `s^-2`), not as mechanical Pascals.

Weidmann, U. (1993). *Transporttechnik der Fussgänger*. Schriftenreihe des
IVT, ETH Zürich. Used here as a default speed-density curve
(`v0 ≈ 1.34 m/s`, jam density ≈ `5.4 people/m^2`), overridable per site.

Bottinelli, A., and Silverberg, J. L. (2018). Can high-density human
collective motion be forecasted by spatiotemporal fluctuations?
*arXiv:1809.07875*. https://arxiv.org/abs/1809.07875
Reports roughly one second of lead time from positional fluctuations,
which is why Crowdent does not source its lead time from precursors.

Gu, F., Guiselin, B., Bain, N., Zuriguel, I., and Bartolo, D. (2025).
Emergence of collective oscillations in massive human crowds. *Nature*,
638(8049). https://doi.org/10.1038/s41586-024-08514-6
Data and code under CC BY 4.0: https://doi.org/10.5281/zenodo.14050598

Chatagnon, T., Tordeux, A., and Chraibi, M. (2025). Exploring Dense Crowd
Dynamics: State of the Art and Emerging Paradigms. *arXiv:2505.05826*.
https://arxiv.org/abs/2505.05826

Forschungszentrum Jülich, Institute for Advanced Simulation 7.
*Pedestrian Dynamics Data Archive*. https://doi.org/10.34735/ped.da

See [research/literature.md](research/literature.md) for how these
results constrain what Crowdent may claim.

## Operations guidance

National Disaster Management Authority (India). *Managing crowds at events
and venues of mass gathering: A guide for administrators and organizers*.
https://ndma.gov.in/sites/default/files/PDF/Reports/managingcrowdsguide.pdf

That guide is operational context. Crowdent does not implement NDMA
approval, and passing the test suite is not NDMA compliance.

## Numerical methods

- Dijkstra / fast-marching style eikonal approximations on grids for
  travel time.
- First-order upwind finite-volume continuity for conservation.
- Deterministic ensemble Kalman filter with covariance localisation
  (Evensen; Hunt / Ott localisation family). These are research
  implementations, not a claim of optimality for every venue.
- Forecast verification follows standard ensemble practice: the fair
  (unbiased) CRPS estimator, the Murphy decomposition of the Brier score
  into reliability, resolution and uncertainty, and the Talagrand rank
  histogram. See [research/verification-protocol.md](research/verification-protocol.md).

## Software

Crowdent 0.1.0, Apache License 2.0. See `CITATION.cff`.
