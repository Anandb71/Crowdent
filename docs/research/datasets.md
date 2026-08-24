# Dataset survey

The machine-readable registry is `crowdent.datasets` and is the source of
truth; this document is the reasoning behind it. Browse it with:

```bash
uv run crowdent dataset list
```

**No dataset is distributed with this repository, and Crowdent downloads
nothing.** Acquisition is a deliberate human act: read the terms, accept
them yourself, download to a research machine, then hash the copy. The
registry records what each homepage published when a human last read it,
on the `terms_reviewed` date. Terms change; re-check before you rely on
one. This is not legal advice.

## The gap this has to close

Crowdent claims to fuse **density** with **velocity variance** to produce
a crowd pressure index in `s^-2`. Almost every popular crowd dataset
supports only the first half. ShanghaiTech, UCF-QNRF, NWPU-Crowd and
JHU-CROWD++ are still images with head points: excellent for training a
density model, structurally incapable of validating anything involving
velocity, because a still frame has none.

So the survey is organised by what a dataset can actually falsify, not by
citation count.

## Tier 1 — validates the physics Crowdent claims

**`sanfermin-oscillations`** (CC BY 4.0, open). Field recordings of a
confined mass gathering at densities reaching roughly 9 people per square
metre, released as density, speed, orientation and chirality maps rather
than raw faces. This is the closest public analogue to Crowdent's
operating regime, and it is openly licensed. Use it to check that the
density-velocity state estimate behaves at crush-relevant densities, and
as the testbed for the oscillation precursor described in
[literature.md](literature.md).

**`juelich-ped-da`** (CC BY-SA 4.0 on many experiments, open). Controlled
laboratory experiments with per-person trajectories from PeTrack. This is
the set that can produce an empirical density-speed fundamental diagram
to test `weidmann_speed` against, and the per-person velocities needed to
compute velocity variance directly rather than inferring it from optical
flow. Per-experiment licensing differs — check each experiment page.

Together these two are open, need no registration, and between them cover
both the controlled and the field end of the same physics. **Start here.**

## Tier 2 — validates the perception pipeline

**`fudan-shanghaitech`** and **`drone-crowd`** are video, so density and
optical-flow velocity can be estimated on the same footage. That pairing
is the thing Crowdent actually does, and no still-image dataset can
exercise it. DroneCrowd additionally carries track identities, giving
per-person velocity as a check on the flow estimate. It is filmed from a
moving platform, so ego-motion has to be removed before optical flow
means anything.

**`worldexpo-10`** ships perspective maps with the footage, making it the
natural fixture for testing `calibrate_homography` and the image-to-ground
projection against a published reference instead of a synthetic
checkerboard. Access is by request.

## Tier 3 — trains and benchmarks the density model

`nwpu-crowd`, `jhu-crowd-plus-plus`, `ucf-qnrf`, `shanghaitech-a`,
`shanghaitech-b`. Standard counting and localisation benchmarks. Use
`shanghaitech-a` as the small, fast smoke-test fixture for the ONNX
export path before downloading anything large.

`jhu-crowd-plus-plus` is the most useful of these for Crowdent
specifically, because its weather, blur and occlusion labels map onto the
quality flags that drive readiness. It is the right set for testing that
a degraded input **lowers readiness** rather than silently producing a
confident number.

`ucf-qnrf` reaches pilgrimage-scale densities that most counting sets
never approach.

## Tier 4 — supporting

`gcc` is synthetic, has exact ground truth, and contains no real person,
so it carries no privacy load. It is the right place to pretrain and to
build twin experiments where the true state is known and assimilation can
be scored honestly. A result on GCC is evidence about the method, never
about a venue.

`rgbt-cc` covers night and low-light, where an RGB-only density model
degrades without announcing it. `eth-ucy` and `atc-shopping-mall` give
world-coordinate trajectories for route-choice and long-horizon schedule
behaviour respectively.

## Suggested order

1. `juelich-ped-da` — fundamental diagram, velocity variance. Open.
2. `sanfermin-oscillations` — field densities, precursor hypothesis. Open.
3. `shanghaitech-a` — smoke-test the density adapter. Small.
4. `fudan-shanghaitech` — first real density-plus-flow fusion test.
5. `gcc` — twin experiments and pretraining.
6. Registration-gated sets, once there is a result worth scaling.

Steps 1 to 3 need no registration and cost little disk. There is no
reason to download 40 GB before the pipeline runs on 200 MB.

## Handling rules

- `data/` is gitignored except `README.md`. Never commit imagery, weights,
  `.npz` chunks, or SQLite databases. See [../privacy.md](../privacy.md).
- Hash every local copy so a benchmark result names the exact bytes:

  ```bash
  uv run crowdent dataset manifest juelich-ped-da --path data/juelich-ped-da
  uv run crowdent dataset verify juelich-ped-da --path data/juelich-ped-da --manifest data/juelich-ped-da.manifest.json
  ```

  Manifests contain hashes and relative paths only, never imagery, so
  unlike the datasets themselves they are safe to commit and are worth
  committing beside any published result.
- Cite every dataset you use. The registry carries the citation string.
- A public dataset is not a venue. None of these licences its subjects to
  your site, and no threshold fitted on them is a shipping threshold.
