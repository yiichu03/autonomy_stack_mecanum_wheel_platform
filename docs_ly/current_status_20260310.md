# 当前状态总览（2026-03-10）

> 这份文档保留 2026-03-10 时点的判断。  
> 截至 2026-03-11，如需看最新状态，请优先阅读 `docs_ly/current_status_20260311.md`。

> 本文替代 `current_status_20260309.md`，记录 2026-03-10 调试会话后的最新状态。

项目目录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform`

---

## 1. 当前已经稳定具备的能力

截至 2026-03-10，系统已经具备：

1. Scout Mini + Hesai XT32 + RealSense D455 + FAST-LIO2 主链路已跑通
2. `system_scout_hesai.launch.py` 可以直接用于 Base Autonomy 调试
3. `system_scout_hesai_with_far_planner.launch.py` 可以直接用于带 FAR 的全局到点规划调试
4. `pathFollower` 已直接发布 `/cmd_vel (Twist)`，不再依赖额外的 Python relay
5. RViz 中可以同时看到：
   `goal / waypoint / free_goal / global path / VGraph / free_paths / terrain_map`
6. 主 launch 默认开启调试日志：
   `runtime_logs/navigation_debug/<时间戳>/`
7. **鬼路径根因已定位**（见下文第 3 节）

---

## 2. 当前数据主链

```text
/lidar_points + /camera/imu
  -> fastlio_mapping
  -> /state_estimation_raw + /registered_scan_raw + /fastlio_path (历史轨迹，已隔离)
  -> odom_frame_relay.py + registeredScanFrameRelay
  -> /state_estimation + /registered_scan
  -> terrain_analysis / terrain_analysis_ext / localPlanner / far_planner
  -> /path
  -> pathFollower
  -> /cmd_vel
```

`/fastlio_path` 是 FAST-LIO2 内部历史轨迹，已通过 topic remap 与导航栈隔离（见第 3 节）。

---

## 3. 鬼路径问题（Ghost Path）

### 根因

`fastlio_mapping` 默认会把走过的里程计历史轨迹发布到 `/path` 话题。
`pathFollower` 同时订阅 `/path`，会把收到的任何路径当作导航指令执行。
结果：pathFollower 会被 FAST-LIO2 历史轨迹驱动，不断让车辆驶向"车辆曾经在的位置"，表现为：

- 车辆靠近目标后突然后退
- `path_size` 每隔约 1.7 秒增加 1（轨迹每帧累积一个点）
- `target_x / target_y` 指向车辆身后约 1.5 m 处

### 已实施的修复

在 `system_scout_hesai.launch.py` 的 `fastlio_mapping` 节点 remappings 中增加：

```python
('/path', '/fastlio_path'),  # FAST-LIO2 历史轨迹，避免 pathFollower 误当导航路径
```

### 重要：修复需要重新编译才能生效

Python launch 文件是从 `install/` 目录运行的，修改 `src/` 下的 launch 文件后必须重新编译：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build --packages-select vehicle_simulator
source install/setup.bash
```

然后重新运行导航栈，鬼路径才会消失。

### 日志验证方法

检查 `path_follower.csv`：
- 修复前：`path_size` 字段会出现 `15 → 16 → 17 → ...`（每次 +1）的递增序列
- 修复后：只应看到 `localPlanner` 发出的正常路径（size 根据场景变化，不会单调递增）

---

## 4. 近目标点无法停止问题（Near-Goal Obstacle Blocking）

### 现象

车辆距离目标点约 0.13 ~ 0.20 m 时，无法继续靠近，也不触发 `freeze_status=1` 停止。

### 根因分析

`local_planner.csv` 日志显示：

- `obstacle_right_points = planner_right_points`（右侧路径组全部被识别为障碍）
- `joy_dir` 指向右前方（-10° 到 -70°），但 `selected_rot_deg` 只能在 0° 附近
- `path_points` 维持最小值（15～21），始终不会减少到 1
- `freeze_status` 始终为 0

根本原因：目标点附近的地形被 `terrain_analysis` 标记为障碍区，右侧路径全部不可用，车辆无法闭合最后 0.13 m 的距离。
`freeze_status=1` 的触发条件是路径规划点数降到接近 1（路径终点到达目标），而当目标区域被障碍阻断时，`localPlanner` 永远无法将规划路径延伸至目标，所以 `freeze_status` 永远不会触发。

### 确认方法

在 RViz 中查看 `/terrain_map`，对目标点位置的地面点颜色进行检查：
- 绿色：可通行
- 红色/黄色：障碍

同时注意 far_planner 的可视化：
- 只出现**红球**（`original_goal`），没有**绿球**（`free_goal`）
- 说明 far_planner 认为目标点不可达（在障碍区内或无法规划路径）

### 当前状态

该问题在鬼路径修复完成后，将是下一个优先排查的问题。

---

## 5. 当前已知问题优先级

| 优先级 | 问题 | 状态 |
|--------|------|------|
| P0 | 鬼路径：FAST-LIO2 `/path` 干扰 pathFollower | **已修复，待重新编译生效** |
| P1 | 近目标点无法停止（障碍误检测阻断最后 0.13 m） | 待排查 `/terrain_map` |
| P2 | far_planner 绿球从不出现（goal 在障碍区内） | 与 P1 同根因 |
| P3 | vehicleLength/Width 仍是保守包络值 0.70×0.60 m | 留待实机精细调试 |

---

## 6. 文档阅读顺序

建议新会话开始时按以下顺序阅读：

1. `docs_ly/run_guide.md` — 运行步骤（含鬼路径修复重编译说明）
2. `docs_ly/current_status_20260310.md` — 本文档，最新状态
3. `docs_ly/navigation_debug_spin_issue_20260309.md` — 详细调试分析（含鬼路径发现过程）
4. `docs_ly/tare_integration_plan.md` — 探索规划模块 TARE 接入分析

---

## 7. 旧结论中已经过时的部分

以下旧结论已经不适用：

1. "当前乱转更可能来自 `twoWayDrive=false` 分支逻辑"
   → 已确认主因是 FAST-LIO2 的鬼路径干扰
2. "需要关注 `twoWayDrive=false` 的后向路径问题"
   → 在鬼路径干扰消除前，这个判断无法被真正验证
3. "localPlanner 会偶尔产出后向路径"
   → 尚未最终排除，但优先级低于鬼路径
