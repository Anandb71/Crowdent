# Data card (research)

Status: **NO FIELD DATASET IS DISTRIBUTED IN THIS REPOSITORY**

## Demo data

The deterministic demo is synthetic. Zone names, densities, speeds, and
risk curves are fixtures. They must not be cited as empirical measurements.

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
