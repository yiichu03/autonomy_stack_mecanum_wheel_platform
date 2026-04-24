#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /home/rho/Documents/data/lio_eval/bags/<bag_name>" >&2
  exit 1
fi

BAG_DIR="$(realpath "$1")"
if [[ ! -d "$BAG_DIR" ]]; then
  echo "Bag directory not found: $BAG_DIR" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAG_NAME="$(basename "$BAG_DIR")"
RESULT_ROOT="/home/rho/Documents/data/lio_eval/results/${BAG_NAME}"
SUMMARY_FILE="${RESULT_ROOT}/compare_summary.md"

echo "[pair] running github replay..."
bash "${SCRIPT_DIR}/run_github_replay.sh" "$BAG_DIR"

echo "[pair] running bitbucket replay..."
bash "${SCRIPT_DIR}/run_bitbucket_replay.sh" "$BAG_DIR"

mkdir -p "$RESULT_ROOT"

printf '%s\n' "# ${BAG_NAME} Replay Summary" > "$SUMMARY_FILE"
printf '\n%s\n' "- input bag: \`${BAG_DIR}\`" >> "$SUMMARY_FILE"
printf '%s\n' "- github results: \`${RESULT_ROOT}/github\`" >> "$SUMMARY_FILE"
printf '%s\n' "- bitbucket results: \`${RESULT_ROOT}/bitbucket\`" >> "$SUMMARY_FILE"
printf '\n%s\n' "## Check First" >> "$SUMMARY_FILE"
printf '%s\n' "- compare \`launch.log\` for warnings such as \`No Effective Points!\`" >> "$SUMMARY_FILE"
printf '%s\n' "- inspect \`output_bag_info.txt\` for /Odometry, /cloud_registered, /path counts" >> "$SUMMARY_FILE"
printf '%s\n' "- replay the saved \`out_topics\` bags in RViz if you want to inspect trajectories visually" >> "$SUMMARY_FILE"

echo "[pair] done"
echo "[pair] summary: $SUMMARY_FILE"
