#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
# Public image pulls need no Windows credential helper. Keep the user's config intact.
export DOCKER_CONFIG="$repo_root/utils/lan/docker-client"
export DOCKER_HOST=unix:///var/run/docker.sock
mkdir -p "$DOCKER_CONFIG"
if [ ! -f "$DOCKER_CONFIG/config.json" ]; then
    printf '%s\n' '{"auths":{}}' > "$DOCKER_CONFIG/config.json"
fi
python3 utils/lan/prepare-demo.py
nuctl="$repo_root/utils/lan/bin/nuctl"
"$nuctl" get project cvat --platform local >/dev/null 2>&1 || "$nuctl" create project cvat --platform local
"$nuctl" deploy --project-name cvat \
    --path "$repo_root/serverless/custom-models/generated/yolo11n-demo" \
    --file "$repo_root/serverless/custom-models/generated/yolo11n-demo/function.yaml" \
    --platform local
"$nuctl" get functions --platform local
