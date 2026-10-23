#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
export DOCKER_CONFIG="$repo_root/utils/lan/docker-client"
export DOCKER_HOST=unix:///var/run/docker.sock
mkdir -p "$DOCKER_CONFIG"
if [ ! -f "$DOCKER_CONFIG/config.json" ]; then
    printf '%s\n' '{"auths":{}}' > "$DOCKER_CONFIG/config.json"
fi
nuctl="$repo_root/utils/lan/bin/nuctl"
if [ ! -x "$nuctl" ]; then
    echo 'Install nuctl 1.16.3 at utils/lan/bin/nuctl first.' >&2
    exit 1
fi
models=("$@")
if [ ${#models[@]} -eq 0 ]; then
    models=(sam-vit-b mobile-sam sam2-1-tiny)
fi
python3 utils/lan/prepare-sam.py --models "${models[@]}"
"$nuctl" get project cvat --platform local >/dev/null 2>&1 || "$nuctl" create project cvat --platform local
for model in "${models[@]}"; do
    "$nuctl" deploy --project-name cvat --platform local \
        --path "$repo_root/serverless/custom-models/generated/$model" \
        --file "$repo_root/serverless/custom-models/generated/$model/function.yaml"
done
"$nuctl" get functions --platform local
