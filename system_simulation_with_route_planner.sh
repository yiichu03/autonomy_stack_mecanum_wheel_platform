#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
RUN_DIR="${SCRIPT_DIR}/tmp/route_planner_run"
PID_FILE="${RUN_DIR}/pids.env"

UNITY_WORLD="${UNITY_WORLD:-environment}"
ROUTE_PLANNER_CONFIG="${ROUTE_PLANNER_CONFIG:-indoor}"
LAUNCH_ARGS=("$@")
UNITY_BIN="${SCRIPT_DIR}/src/base_autonomy/vehicle_simulator/mesh/unity/${UNITY_WORLD}/Model.x86_64"
RVIZ_CONFIG_PATH="${SCRIPT_DIR}/src/route_planner/far_planner/rviz/default.rviz"
STOP_SCRIPT="${SCRIPT_DIR}/stop_system_simulation_with_route_planner.sh"

UNITY_PID=""
ROS_LAUNCH_PID=""
RVIZ_PID=""
CLEANED_UP=0

mkdir -p "${RUN_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  echo "Found existing pid file: ${PID_FILE}"
  echo "Run ${STOP_SCRIPT} first if the previous session is still active."
  exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/install/setup.bash" ]]; then
  echo "Missing install/setup.bash in ${SCRIPT_DIR}"
  exit 1
fi

if [[ ! -x "${UNITY_BIN}" ]]; then
  echo "Unity executable not found or not executable: ${UNITY_BIN}"
  exit 1
fi

if [[ ! -f "${RVIZ_CONFIG_PATH}" ]]; then
  echo "RViz config not found: ${RVIZ_CONFIG_PATH}"
  exit 1
fi

cd "${SCRIPT_DIR}"
set +u
source ./install/setup.bash
set -u

write_pid_file() {
  cat > "${PID_FILE}" <<EOF
UNITY_PID=${UNITY_PID:-}
ROS_LAUNCH_PID=${ROS_LAUNCH_PID:-}
RVIZ_PID=${RVIZ_PID:-}
EOF
}

cleanup() {
  set +e
  if [[ "${CLEANED_UP}" == "1" ]]; then
    return
  fi
  CLEANED_UP=1

  if [[ -x "${STOP_SCRIPT}" ]]; then
    "${STOP_SCRIPT}" >/dev/null 2>&1 || true
  else
    rm -f "${PID_FILE}"
  fi
}

handle_signal() {
  local signal_name="$1"
  local exit_code="$2"
  echo
  echo "Received ${signal_name}, stopping route planner simulation..."
  cleanup
  exit "${exit_code}"
}

trap cleanup EXIT
trap 'handle_signal INT 130' INT
trap 'handle_signal TERM 143' TERM

start_bg() {
  local name="$1"
  shift
  setsid "$@" >/dev/null 2>&1 < /dev/null &
  START_BG_PID=$!
  echo "${name} started: pid=${START_BG_PID}" >&2
}

start_bg unity "${UNITY_BIN}"
UNITY_PID="${START_BG_PID}"
write_pid_file
sleep 3

start_bg ros_launch ros2 launch vehicle_simulator system_simulation_with_route_planner.launch "route_planner_config:=${ROUTE_PLANNER_CONFIG}" "${LAUNCH_ARGS[@]}"
ROS_LAUNCH_PID="${START_BG_PID}"
write_pid_file
sleep 1

start_bg rviz ros2 run rviz2 rviz2 -d "${RVIZ_CONFIG_PATH}"
RVIZ_PID="${START_BG_PID}"
write_pid_file

set +e
wait "${RVIZ_PID}"
RVIZ_STATUS=$?
set -e

cleanup
trap - EXIT INT TERM
exit "${RVIZ_STATUS}"
