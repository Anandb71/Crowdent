#!/usr/bin/env sh
# Local research bootstrap. Not a production installer.
set -eu
cd "$(dirname "$0")/.."
uv sync
(cd frontend && npm ci && npm run build)
uv run crowdent doctor --json
echo "RESEARCH ONLY — NOT DEPLOYMENT CERTIFIED"
