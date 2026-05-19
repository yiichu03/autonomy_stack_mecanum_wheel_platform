#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
RUN_DIR="${SCRIPT_DIR}/tmp/route_planner_run"
PID_FILE="${RUN_DIR}/pids.env"

legacy_cleanup() {
  local patterns=(
    "ros2 launch vehicle_simulator system_simulation_with_route_planner.launch"
    "${SCRIPT_DIR}/install/local_planner/lib/local_planner/localPlanner"
    "${SCRIPT_DIR}/install/local_planner/lib/local_planner/pathFollower"
    "${SCRIPT_DIR}/install/terrain_analysis/lib/terrain_analysis/terrainAnalysis"
    "${SCRIPT_DIR}/install/terrain_analysis_ext/lib/terrain_analysis_ext/terrainAnalysisExt"
    "${SCRIPT_DIR}/install/ros_tcp_endpoint/lib/ros_tcp_endpoint/default_server_endpoint"
    "${SCRIPT_DIR}/install/vehicle_simulator/lib/vehicle_simulator/sim_image_repub"
    "${SCRIPT_DIR}/install/vehicle_simulator/lib/vehicle_simulator/vehicleSimulator"
    "${SCRIPT_DIR}/install/sensor_scan_generation/lib/sensor_scan_generation/sensorScanGeneration"
    "${SCRIPT_DIR}/install/far_planner/lib/far_planner/far_planner"
    "${SCRIPT_DIR}/src/base_autonomy/vehicle_simulator/mesh/unity/.*/Model.x86_64"
    "rviz2 -d .*src/route_planner/far_planner/rviz/default.rviz"
  )

  local matched=0
  for pattern in "${patterns[@]}"; do
    if pgrep -f "${pattern}" >/dev/null 2>&1; then
      matched=1
      echo "Stopping legacy processes matching: ${pattern}"
      pkill -f "${pattern}" 2>/dev/null || true
    fi
  done

  if [[ "${matched}" == "0" ]]; then
    echo "No route planner simulation processes found."
  else
    echo "Stopped legacy route planner simulation processes"
  fi
}

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No pid file found at ${PID_FILE}"
  echo "Falling back to legacy process cleanup..."
  legacy_cleanup
  exit 0
fi

read_pid() {
  local pid_var="$1"
  local pid
  pid="$(grep -E "^${pid_var}=" "${PID_FILE}" | head -n1 | cut -d= -f2- || true)"
  if [[ "${pid}" =~ ^[0-9]+$ ]]; then
    printf '%s' "${pid}"
  fi
}

for pid_var in RVIZ_PID ROS_LAUNCH_PID UNITY_PID; do
  pid="$(read_pid "${pid_var}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo "Stopping ${pid_var}=${pid}"
    kill -- "-${pid}" 2>/dev/null || kill "${pid}" 2>/dev/null || true
  fi
done

rm -f "${PID_FILE}"
echo "Stopped route planner simulation session"
