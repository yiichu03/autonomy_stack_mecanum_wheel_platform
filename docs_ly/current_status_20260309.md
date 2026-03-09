# 当前状态总览（2026-03-09）

项目目录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform`

## 1. 当前已经稳定具备的能力

截至 2026-03-09，当前工作区已经具备下面这些能力：

1. Scout Mini + Hesai XT32 + RealSense D455 + FAST-LIO2 主链路已跑通
2. `system_scout_hesai.launch.py` 可以直接用于 Base Autonomy 调试
3. `system_scout_hesai_with_far_planner.launch.py` 可以直接用于带 FAR 的全局到点规划调试
4. `pathFollower` 已直接发布 `/cmd_vel (Twist)`，不再依赖额外的 Python relay 才能驱动 Scout
5. RViz 中已能同时看到：
   `goal / waypoint / free_goal / global path / VGraph / free_paths / terrain_map`
6. 主 launch 默认已写入规划与控制调试日志到
   `runtime_logs/navigation_debug/<时间戳>/`

## 2. 当前实际运行入口

当前应优先使用的入口是：

1. `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py`
2. `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py`

不再建议把旧的原仓库入口当作当前主流程说明文档。

## 3. 当前数据主链

当前主链可以概括成：

```text
/lidar_points + /camera/imu
  -> FAST-LIO2
  -> /state_estimation_raw + /registered_scan_raw
  -> odom_frame_relay.py + registeredScanFrameRelay
  -> /state_estimation + /registered_scan
  -> terrain_analysis / terrain_analysis_ext / localPlanner / far_planner
  -> /path
  -> pathFollower
  -> /cmd_vel
```

这和 2 月底很多文档里写的“FAST-LIO 还只是计划接入”已经不一样了。

## 4. 当前最重要的已知问题

当前最重要的问题不是“系统起不来”，而是：

1. 导航链路已经能运行
2. 但局部规划与控制链路仍偶尔出现左右旋转、目标不可达
3. 当前更强的怀疑点在 `localPlanner` 的 `twoWayDrive=false` 分支
4. 不是所有异常都算代码问题，部分日志异常可能来自人工遥控或重新设置 goal

详细分析见：

1. `docs_ly/navigation_debug_spin_issue_20260309.md`

## 5. 当前文档应该怎么读

如果是为了继续项目，不建议再把 2 月底的状态文档直接当作当前事实。

建议阅读顺序：

1. `docs_ly/run_guide.md`
   当前真实运行步骤
2. `docs_ly/current_status_20260309.md`
   当前系统状态总览
3. `docs_ly/navigation_debug_spin_issue_20260309.md`
   当前乱转问题分析与代码阅读导引
4. `docs_ly/project_status_20260228.md`
   2 月底的阶段性记录，主要看背景
5. `docs_ly/strategy_overview_20260228.md`
   2 月底的整体路线思考，主要看背景

## 6. 当前哪些旧结论已经过时

下面这些旧结论现在不应再默认当真：

1. “FAST-LIO2 还没真正接进主 launch”
2. “需要额外 Python relay 才能把 `TwistStamped` 转成 Scout 需要的 `/cmd_vel`”
3. “far_planner 还没有接进当前主入口”
4. “当前还没有统一的规划/控制调试日志”

这些在当前代码里都已经不是事实。

## 7. 当前仍需后续确认的事项

即使主链已经跑通，下面几项仍值得继续确认：

1. `localPlanner` 在 `twoWayDrive=false` 时的候选路径选择是否还会错误产出后向路径
2. 车体尺寸当前仍是保守包络值 `0.70 x 0.60 m`，不是更精细的真实碰撞模型
3. 实机阶段仍需要继续确认 Scout 底盘方向、低速行为与急停安全性
4. 如果后续要稳定推进 FAR / TARE，需要在当前局部规划问题稳定后再继续
