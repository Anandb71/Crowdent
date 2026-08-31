# StillDot

**Research demo — not deployment-ready.**

SIH26168 · AI-ML based Intelligent Dead Reckoning · ISRO · Smart Vehicles

Your phone loses GNSS because a roof got in the way, not because the
satellites failed. StillDot keeps a position estimate using only the
IMU the phone already has. No OBD wire. No internet. No actuation.

The network estimates **speed and uncertainty**. The filter estimates
**position**. We never integrate acceleration twice to get distance.

## Demo (the laptop fallback)

The pitch script says: if the phones fail, replay on the laptop. That
is this console.

```bash
uv sync --group dev
cd frontend && npm install && npm run build && cd ..
uv run stilldot demo
```

Open `http://127.0.0.1:8000`. Tap **START**. The room-walk path draws
live, then the drift figure is read out in metres and as a percentage
of distance travelled. The requirement is under 10%.

Airplane mode on a phone is the live path. This laptop replay is the
same engine on a surveyed synthetic path — labelled as such on screen.

## What is real, what is not

| Built and measured | Not built |
| --- | --- |
| Time-aligned IMU, alignment, virtual odometer, ZUPT, NHC, 10 Hz output | IO-VNBD training / country hold-out numbers |
| Room walk (50 m) and tunnel (1 km / 60 km/h) replays | Full invariant EKF on a Lie group |
| Naive ∫∫a comparison (the t² lesson) | Map matching against OpenStreetMap |
| Live DeviceMotion ingest | A published Indian-road score |

Do not quote an accuracy number without the scenario, the distance,
and the fact that these replays are synthetic.

## Tests

```bash
uv run ruff check src tests
uv run mypy src/stilldot
uv run pytest
cd frontend && npm run check
```

## Language

Never say “we used AI to predict the position.” Say: the network
estimates speed and uncertainty; the filter estimates position.

## License

Apache License 2.0. See [LICENSE](LICENSE).
