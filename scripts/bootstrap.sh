#!/usr/bin/env sh
# Local research bootstrap. Not a production installer.
set -eu
cd "$(dirname "$0")/.."
uv sync --group dev
(cd frontend && npm ci && npm run build)
uv run stilldot doctor
echo "RESEARCH DEMO — NOT DEPLOYMENT-READY"
