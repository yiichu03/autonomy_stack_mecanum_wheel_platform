#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /home/rho/Documents/data/lio_eval/bags/<bag_name> [github_config.yaml]" >&2
  exit 1
fi

BAG_DIR="$(realpath "$1")"
if [[ ! -d "$BAG_DIR" ]]; then
  echo "Bag directory not found: $BAG_DIR" >&2
  exit 1
fi

DEFAULT_CONFIG_DIR="/home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/fast_lio/share/fast_lio/config"
CONFIG_SPEC="${2:-hesai_xt32.yaml}"
if [[ -f "$CONFIG_SPEC" ]]; then
  GITHUB_CONFIG="$(realpath "$CONFIG_SPEC")"
else
  GITHUB_CONFIG="${DEFAULT_CONFIG_DIR}/${CONFIG_SPEC}"
fi
if [[ ! -f "$GITHUB_CONFIG" ]]; then
  echo "GitHub config not found: $GITHUB_CONFIG" >&2
  exit 1
fi
GITHUB_CONFIG_DIR="$(dirname "$GITHUB_CONFIG")"
GITHUB_CONFIG_FILE="$(basename "$GITHUB_CONFIG")"

BAG_NAME="$(basename "$BAG_DIR")"
RESULT_DIR="/home/rho/Documents/data/lio_eval/results/${BAG_NAME}/github"
OUTPUT_BAG="${RESULT_DIR}/out_topics"
LAUNCH_LOG="${RESULT_DIR}/launch.log"
PLAY_LOG="${RESULT_DIR}/play.log"
RECORD_LOG="${RESULT_DIR}/record.log"
INPUT_INFO="${RESULT_DIR}/input_bag_info.txt"
OUTPUT_INFO="${RESULT_DIR}/output_bag_info.txt"
CONFIG_USED="${RESULT_DIR}/config_used.txt"
CONFIG_SNAPSHOT="${RESULT_DIR}/${GITHUB_CONFIG_FILE}"

if [[ -d "$RESULT_DIR" ]]; then
  if [[ -z "$(find "$RESULT_DIR" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
    rmdir "$RESULT_DIR"
  else
    echo "Result directory already exists: $RESULT_DIR" >&2
    echo "Remove or rename it before rerunning." >&2
    exit 1
  fi
elif [[ -e "$RESULT_DIR" ]]; then
  echo "Result path exists and is not a directory: $RESULT_DIR" >&2
  exit 1
fi

mkdir -p "$RESULT_DIR"

source_without_nounset() {
  set +u
  source "$1"
  set -u
}

source_without_nounset /opt/ros/humble/setup.bash
source_without_nounset /home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash

ros2 bag info "$BAG_DIR" > "$INPUT_INFO"
printf 'github_config=%s\n' "$GITHUB_CONFIG" > "$CONFIG_USED"
cp "$GITHUB_CONFIG" "$CONFIG_SNAPSHOT"

LAUNCH_PID=""
RECORD_PID=""

cleanup() {
  set +e
  if [[ -n "$RECORD_PID" ]] && kill -0 "$RECORD_PID" 2>/dev/null; then
    kill -INT "$RECORD_PID" 2>/dev/null || true
    wait "$RECORD_PID" 2>/dev/null || true
  fi
  if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
    kill -INT "$LAUNCH_PID" 2>/dev/null || true
    wait "$LAUNCH_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

echo "[github] bag: $BAG_DIR"
echo "[github] results: $RESULT_DIR"
echo "[github] config: $GITHUB_CONFIG"

ros2 launch fast_lio mapping.launch.py \
  config_path:="$GITHUB_CONFIG_DIR" \
  config_file:="$GITHUB_CONFIG_FILE" \
  use_sim_time:=true \
  rviz:=false \
  > "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

sleep 5
if ! kill -0 "$LAUNCH_PID" 2>/dev/null; then
  echo "GitHub FAST-LIO exited early. Check $LAUNCH_LOG" >&2
  exit 1
fi

ros2 bag record \
  -o "$OUTPUT_BAG" \
  /Odometry /cloud_registered /path \
  > "$RECORD_LOG" 2>&1 &
RECORD_PID=$!

sleep 3
if ! kill -0 "$RECORD_PID" 2>/dev/null; then
  echo "ros2 bag record exited early. Check $RECORD_LOG" >&2
  exit 1
fi

ros2 bag play "$BAG_DIR" --clock > "$PLAY_LOG" 2>&1

sleep 3

kill -INT "$RECORD_PID" 2>/dev/null || true
wait "$RECORD_PID" 2>/dev/null || true
RECORD_PID=""

kill -INT "$LAUNCH_PID" 2>/dev/null || true
wait "$LAUNCH_PID" 2>/dev/null || true
LAUNCH_PID=""

ros2 bag info "$OUTPUT_BAG" > "$OUTPUT_INFO"

trap - EXIT

echo "[github] done"
echo "[github] launch log: $LAUNCH_LOG"
echo "[github] output bag: $OUTPUT_BAG"
