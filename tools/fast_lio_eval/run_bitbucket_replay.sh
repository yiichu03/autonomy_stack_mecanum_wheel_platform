#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 /home/rho/Documents/data/lio_eval/bags/<bag_name> [bitbucket_config.yaml]" >&2
  exit 1
fi

BAG_DIR="$(realpath "$1")"
if [[ ! -d "$BAG_DIR" ]]; then
  echo "Bag directory not found: $BAG_DIR" >&2
  exit 1
fi

DEFAULT_CONFIG_DIR="/home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install_bitbucket/fast_lio/share/fast_lio/config"
CONFIG_SPEC="${2:-hesai32_nus_carter_realsenseimu.yaml}"
if [[ -f "$CONFIG_SPEC" ]]; then
  BITBUCKET_CONFIG="$(realpath "$CONFIG_SPEC")"
else
  BITBUCKET_CONFIG="${DEFAULT_CONFIG_DIR}/${CONFIG_SPEC}"
fi
if [[ ! -f "$BITBUCKET_CONFIG" ]]; then
  echo "Bitbucket config not found: $BITBUCKET_CONFIG" >&2
  exit 1
fi
BITBUCKET_CONFIG_FILE="$(basename "$BITBUCKET_CONFIG")"

BAG_NAME="$(basename "$BAG_DIR")"
RESULT_DIR="/home/rho/Documents/data/lio_eval/results/${BAG_NAME}/bitbucket"
OUTPUT_BAG="${RESULT_DIR}/out_topics"
LAUNCH_LOG="${RESULT_DIR}/launch.log"
PLAY_LOG="${RESULT_DIR}/play.log"
RECORD_LOG="${RESULT_DIR}/record.log"
INPUT_INFO="${RESULT_DIR}/input_bag_info.txt"
OUTPUT_INFO="${RESULT_DIR}/output_bag_info.txt"
CONFIG_USED="${RESULT_DIR}/config_used.txt"
CONFIG_SNAPSHOT="${RESULT_DIR}/${BITBUCKET_CONFIG_FILE}"

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
  # ROS setup scripts are not nounset-safe.
  source "$1"
  set -u
}

source_without_nounset /opt/ros/humble/setup.bash
source_without_nounset /home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install_bitbucket/setup.bash

ros2 bag info "$BAG_DIR" > "$INPUT_INFO"
printf 'bitbucket_config=%s\n' "$BITBUCKET_CONFIG" > "$CONFIG_USED"
cp "$BITBUCKET_CONFIG" "$CONFIG_SNAPSHOT"

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

echo "[bitbucket] bag: $BAG_DIR"
echo "[bitbucket] results: $RESULT_DIR"
echo "[bitbucket] config: $BITBUCKET_CONFIG"

ros2 launch fast_lio mapping_online.launch.py \
  config_yaml:="$BITBUCKET_CONFIG" \
  rviz:=false \
  > "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

sleep 5
if ! kill -0 "$LAUNCH_PID" 2>/dev/null; then
  echo "Bitbucket FAST-LIO exited early. Check $LAUNCH_LOG" >&2
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

echo "[bitbucket] done"
echo "[bitbucket] launch log: $LAUNCH_LOG"
echo "[bitbucket] output bag: $OUTPUT_BAG"
