#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 github|bitbucket /home/rho/Documents/data/lio_eval/bags/<bag_name> [fastlio_config.yaml|config_name]" >&2
  exit 1
fi

VARIANT_RAW="$1"
BAG_DIR="$(realpath "$2")"
if [[ ! -d "$BAG_DIR" ]]; then
  echo "Bag directory not found: $BAG_DIR" >&2
  exit 1
fi

case "$VARIANT_RAW" in
  github|official)
    VARIANT="github"
    FASTLIO_SETUP="/home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash"
    DEFAULT_CONFIG="hesai_xt32.yaml"
    ;;
  bitbucket)
    VARIANT="bitbucket"
    FASTLIO_SETUP="/home/rho/Documents/liuyi/projects/thermal_nav/fastlio_ws/install_bitbucket/setup.bash"
    DEFAULT_CONFIG="hesai32_nus_carter_realsenseimu.yaml"
    ;;
  *)
    echo "Unsupported variant: $VARIANT_RAW (use github or bitbucket)" >&2
    exit 1
    ;;
esac

CONFIG_SPEC="${3:-$DEFAULT_CONFIG}"
BAG_NAME="$(basename "$BAG_DIR")"
RESULT_DIR="/home/rho/Documents/data/lio_eval/results/${BAG_NAME}/${VARIANT}_ariadne"
LAUNCH_LOG="${RESULT_DIR}/launch.log"
PLAY_LOG="${RESULT_DIR}/play.log"
INPUT_INFO="${RESULT_DIR}/input_bag_info.txt"
CONFIG_USED="${RESULT_DIR}/config_used.txt"

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
source_without_nounset "$FASTLIO_SETUP"
source_without_nounset /home/rho/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source_without_nounset /home/rho/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source_without_nounset /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash

ros2 bag info "$BAG_DIR" > "$INPUT_INFO"
printf 'variant=%s\nfastlio_config=%s\n' "$VARIANT" "$CONFIG_SPEC" > "$CONFIG_USED"

LAUNCH_PID=""

cleanup() {
  set +e
  if [[ -n "$LAUNCH_PID" ]] && kill -0 "$LAUNCH_PID" 2>/dev/null; then
    kill -INT "$LAUNCH_PID" 2>/dev/null || true
    wait "$LAUNCH_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

echo "[ariadne] bag: $BAG_DIR"
echo "[ariadne] variant: $VARIANT"
echo "[ariadne] config: $CONFIG_SPEC"
echo "[ariadne] results: $RESULT_DIR"

ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  use_sim_time:=true \
  ariadneMapResolution:=0.3 \
  ariadneSensorRange:=10.0 \
  ariadneNodeResolution:=1.0 \
  maxSpeed:=0.3 \
  ariadnePublishGraph:=true \
  vehicleLength:=0.90 \
  vehicleWidth:=0.80 \
  fastlioVariant:="$VARIANT" \
  fastlioConfig:="$CONFIG_SPEC" \
  > "$LAUNCH_LOG" 2>&1 &
LAUNCH_PID=$!

sleep 8
if ! kill -0 "$LAUNCH_PID" 2>/dev/null; then
  echo "ARiADNE replay launch exited early. Check $LAUNCH_LOG" >&2
  exit 1
fi

ros2 bag play "$BAG_DIR" --clock > "$PLAY_LOG" 2>&1

sleep 3

kill -INT "$LAUNCH_PID" 2>/dev/null || true
wait "$LAUNCH_PID" 2>/dev/null || true
LAUNCH_PID=""

trap - EXIT

echo "[ariadne] done"
echo "[ariadne] launch log: $LAUNCH_LOG"
echo "[ariadne] play log: $PLAY_LOG"
