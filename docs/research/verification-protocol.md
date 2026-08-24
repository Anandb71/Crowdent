# Verification protocol

How to find out whether a Crowdent forecast is any good, using
`crowdent.verification`. This is a protocol, not a result. Running it
produces evidence; it does not produce a certification, and nothing in
this document authorises field deployment.

## The two questions

A probabilistic forecast has to answer both, and passing one without the
other is worthless:

1. **Is it skilful?** Does it beat a trivial baseline?
2. **Is it honest?** When it says ninety percent, does the truth land
   inside the interval ninety percent of the time?

A forecast can be sharp and wrong, or calibrated and useless. Question 1
is answered by a proper scoring rule. Question 2 is answered by
calibration diagnostics. Crowdent reports both, and refuses to summarise
them into a single number, because a single number is what lets an
overconfident system look healthy.

## Scores, and why these ones

| Tool | Answers | Orientation |
| --- | --- | --- |
| `crps_ensemble` | Overall quality of the whole predictive distribution | Lower is better |
| `energy_score` | Same, but for zones jointly, so spatial correlation counts | Lower is better |
| `pinball_loss` | Quality of the published quantiles specifically | Lower is better |
| `brier_decomposition` | Quality of threshold-exceedance probabilities, split into reliability and resolution | Lower Brier is better |
| `rank_histogram` | Is the ensemble the right width? | Flat is calibrated |
| `spread_skill_ratio` | Same question, as one number | One is calibrated |
| `interval_coverage` | Does the stated interval contain the truth? | Match the attainable rate |

CRPS is used rather than RMSE because RMSE scores only the ensemble mean
and is blind to whether the uncertainty was reasonable. CRPS reduces to
absolute error when the ensemble collapses to a point, so a deterministic
forecast is still comparable — it simply cannot win by hiding its spread.

The fair (unbiased) CRPS estimator is the default, so a 20-member run and
a 200-member run can be compared without the larger ensemble winning for
free.

## Baselines are mandatory

An absolute CRPS is close to meaningless. On a quiet timeline where
nothing happens, a forecast that predicts "no change" forever scores
beautifully. Always pass `baseline_by_lead`:

- **Persistence** (`persistence_baseline`) — the state does not change.
  This is the baseline to beat, and it is harder than it sounds at short
  lead times.
- **Schedule-only** (`schedule_baseline`) — arrivals applied with no
  dynamics. Beating this is what justifies the numerics.
- **No-assimilation** (`no_assimilation_baseline`) — the model runs open
  loop. Beating this is what justifies the EnKF.

If the CRPS skill against persistence is at or below zero, the forecast
engine is contributing nothing at that lead time, and the report says so
in `warnings` rather than burying it.

## Reading the calibration output

`spread_skill_ratio` near 1.0 means the ensemble spread matches its
actual error. The report flags two failure directions, and they are not
symmetric in consequence:

- **Below 0.85 — under-dispersed.** The ensemble is overconfident. The
  interval on the operator's screen is tighter than the physics supports,
  which invites a human to trust precision that is not there. This is the
  dangerous direction and the one to fix first.
- **Above 1.25 — over-dispersed.** The interval is honest but too wide to
  act on. This wastes lead time rather than creating false confidence.

The rank histogram shows the same thing with more detail. A U shape means
the truth keeps falling outside the ensemble: under-dispersion. A dome
means over-dispersion. A slope means bias.

### Coverage is compared against what the ensemble size can attain

A finite ensemble cannot deliver an arbitrary interval. Dropping `k`
members from each tail of `m` exchangeable members gives coverage of
exactly `(m - 2k - 1) / (m + 1)`. A 40-member ensemble asked for 90
percent can offer 90.2 percent; a 12-member ensemble can only reach about
85 percent, no matter how well calibrated it is.

`interval_coverage` therefore reports `attainable` alongside `nominal`,
and `deviation` is measured against `attainable`. Judging a small
ensemble against its nominal level would condemn a perfectly honest
forecast for being small. If you need a genuine 90 percent interval, the
fix is more members, not a better model.

## The protocol

1. **Twin experiment first.** Run the model against synthetic truth from
   the same model, where the true state is known exactly. Assimilation
   and scoring must behave correctly here before real data is worth
   collecting. A twin experiment that fails calibration indicates a bug,
   not a venue.
2. **Then recorded timelines.** Use a replay bundle. Score every lead
   time against persistence.
3. **Stratify by regime.** Aggregate scores hide the cases that matter.
   Report low, moderate and high density separately. A model can look
   excellent overall and be useless above 4 people per square metre,
   which is the only regime anyone cares about.
4. **Report warnings verbatim.** `VerificationReport.warnings` is the
   part a reviewer should read first. Do not summarise it away.
5. **Record the data identity.** Produce a dataset manifest
   (`crowdent dataset manifest`) beside every result so the score names
   the exact bytes it came from.

## Example

```python
from crowdent.numerics import persistence_baseline
from crowdent.verification import verify_ensemble_forecast

report = verify_ensemble_forecast(
    forecasts_by_lead,          # {minutes: (cases, members)}
    observations_by_lead,       # {minutes: (cases,)}
    baseline_by_lead=baselines, # persistence
    threshold=0.02,             # crowd pressure index, s^-2
    nominal_coverage=0.9,
)

for warning in report.warnings:
    print(warning)
```

The `threshold` argument scores the exceedance probability that actually
drives an advisory, which is a different question from whether the mean
state was right. A model can track density well and still be badly
calibrated about crossing the line that matters.

## What a passing report does not mean

`VerificationReport.calibrated` is a screening result. It means the
diagnostics found nothing alarming on that timeline. It is not readiness,
it is not certification, and no code path treats it as either. The
verification package holds no readiness state, emits no countdown, and
has no hardware interface.

Field use still requires surveyed geometry, independent hold-outs by
density regime, privacy review, and a signed readiness manifest produced
outside this repository. See [../validation.md](../validation.md) and
[../safety-readiness.md](../safety-readiness.md).
