#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[compat] run_official_replay.sh is kept for backward compatibility."
echo "[compat] Results are now stored under results/<bag>/github."
exec bash "${SCRIPT_DIR}/run_github_replay.sh" "$@"
