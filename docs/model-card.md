# Model card (research)

Status: **UNTRAINED EXPORT PIPELINE FIXTURE — NOT FOR FIELD USE**

This repository ships a tiny fully-convolutional density network only to
prove PyTorch → ONNX → ONNX Runtime parity. It has no claimed accuracy.

## Intended use

- Verify the training extra can export a signed-shape ONNX graph
- Verify runtime `OnnxDensityAdapter` refuses SHA-256 mismatches
- Teach the manifest contract (`input_name`, `output_name`, NCHW shape,
  `people_per_square_metre`)

## Out of scope

- Crowd counting at a real venue
- Occlusion, night, rain, or camera-change robustness
- Any safety threshold or countdown

## Inputs / outputs

- Input: `image`, float32, shape `[1, 1, H, W]`, layout NCHW
- Output: `density`, float32, non-negative, units `people_per_square_metre`

## Training data

None. Weights are random within the export seed. Field models require an
approved dataset, venue hold-outs, calibration by density regime, a privacy
review, and an independently signed readiness manifest.

## Failure modes

Non-finite inputs, negative densities, or hash mismatches fail closed. The
safety layer maps those failures to `UNKNOWN` and suppresses advice.

## Runtime constraint

The `crowdent` runtime package must not import `torch`. Inference uses
ONNX Runtime with `CPUExecutionProvider`.
