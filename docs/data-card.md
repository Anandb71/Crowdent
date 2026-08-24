# Data card (research)

Status: **NO FIELD DATASET IS DISTRIBUTED IN THIS REPOSITORY**

## Demo data

The deterministic demo is synthetic. Zone names, densities, speeds, and
risk curves are fixtures. They must not be cited as empirical measurements.

## Public datasets

`crowdent.datasets` is a registry of public crowd datasets: where they
live, their published access terms as last reviewed by a human, and which
Crowdent claim each can falsify. Crowdent performs no download and
accepts no licence on an operator's behalf. See
[research/datasets.md](research/datasets.md) and run
`crowdent dataset list`.

Hash every local copy with `crowdent dataset manifest`. Manifests hold
hashes and relative paths only, never imagery, so they are safe to commit
and should accompany any published result.

## What may be added locally

Operators may place surveyed geometry, recorded video, and approved
aggregates under `data/` on a research machine. That directory is gitignored
except for `README.md`.

## Collection principles

- Use existing venue sensors with documented consent and purpose limitation.
- Prefer anonymous zone counts over device identifiers.
- Keep timezone-aware timestamps. Naive timestamps are rejected.
- Record calibration (homography support polygon, RMSE, condition number)
  beside any video used for training or replay.

## Retention

Default: no raw video. Chunk retention is seven days in the example field
profile. Shorten this if local policy requires it.

## Prohibited in git

- Videos and images of real crowds
- ONNX/PyTorch weights
- SQLite databases and `.npz` run chunks
- Student IDs, personal emails, phone numbers
- `.env` files and TLS private keys
