# Models

No trained weights are stored in git.

Place local ONNX files here during research. Each file needs a sibling
`<name>.manifest.json` with SHA-256, input/output names, NCHW shape, and
`research_only: true`.

The checked-in `density.example.json` is a **shape contract**, not a model.

Runtime inference uses ONNX Runtime only. PyTorch belongs in the optional
`crowdent[training]` extra.
