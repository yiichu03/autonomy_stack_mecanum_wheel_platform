# 当前状态总览（2026-03-11）

> 本文记录 2026-03-11 时点的最新状态。  
> 如果与 `current_status_20260310.md` 或更早讨论记录冲突，以本文为准。

项目目录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform`

## 1. 当前已经稳定具备的能力

截至 2026-03-11，当前系统已经具备：

1. Scout Mini + Hesai XT32 + RealSense D455 + FAST-LIO2 主链路可正常运行
2. `system_scout_hesai.launch.py` 可用于 Base Autonomy 调试
3. `system_scout_hesai_with_far_planner.launch.py` 可用于 FAR 全局到点规划调试
4. `pathFollower` 已直接发布 `/cmd_vel (Twist)`
5. RViz 中可直接查看 `goal / waypoint / free_goal / global path / VGraph / free_paths / terrain_map`
6. 主 launch 默认写调试日志到 `runtime_logs/navigation_debug/<时间戳>/`

## 2. 当前已确认的关键事实

### 2.1 `/path` 冲突已经定位并修正

之前导致大量调试结论被污染的主因已经确认：

1. `fastlio_mapping` 默认也会发布 `nav_msgs/Path` 到 `/path`
2. `pathFollower` 同时订阅 `/path`
3. 结果是 FAST-LIO2 历史轨迹和 `localPlanner` 导航路径混在了一起

当前的修正口径是：

1. FAST-LIO2 历史轨迹改走 `/fastlio_path`
2. 导航用 `/path` 应只由 `localPlanner` 发布

运行时应这样验证：

```bash
ros2 topic info /path --verbose
ros2 topic info /fastlio_path --verbose
```

### 2.2 当前数据主链

```text
/lidar_points + /camera/imu
  -> fastlio_mapping
  -> /state_estimation_raw + /registered_scan_raw + /fastlio_path
  -> odom_frame_relay.py + registeredScanFrameRelay
  -> /state_estimation + /registered_scan
  -> terrain_analysis / terrain_analysis_ext / localPlanner / far_planner
  -> /path
  -> pathFollower
  -> /cmd_vel
```

### 2.3 系统现在是“能运行”，不是“已完全收敛”

当前最准确的状态不是“还没跑通”，而是：

1. 主链已经能启动、出图、出路径、出速度
2. 远距离或中距离导航通常已经可观察
3. 但近目标时的收敛和停止行为仍不稳定

## 3. 当前最主要的已知问题

### 3.1 近目标时仍可能反复转向

当前最主要的问题是：

1. 车辆接近目标后，`localPlanner` 仍可能继续发布新的多点路径
2. `pathFollower` 每次收到新 `/path` 都会重新按当前路径对正
3. 所以即使已经很接近目标，也可能出现反复左右转

### 3.2 为什么“明明进入停止半径了”还会继续转

当前日志已经说明：

1. `pathFollower` 的停转判断是基于“当前跟踪点距离”，不是 RViz 中原始 goal
2. 它没有一个稳定锁存的“已经到点”状态
3. 只要 `localPlanner` 再发布一条新的多点路径，控制器又会重新进入转向流程

这意味着：

1. 停转条件不是完全没生效
2. 但它会被后续的新路径打破

### 3.3 当前还不应下结论的事

目前还不适合直接下这些结论：

1. “所有乱转都来自 `twoWayDrive`”
2. “所有近目标问题都来自 terrain map 误检障碍”
3. “FAR 本身就是主问题”

这些都可能是局部因素，但当前最稳的主结论仍是：

1. `/path` 冲突已经是已修正的旧问题
2. 当前剩余主问题是近目标阶段的 planner/follower 收敛不稳定

## 4. 关于探索模块（TARE）的当前判断

当前仓库里确实已经包含探索模块：

```text
src/exploration_planner/tare_planner/
```

而且从接口上看，它与当前链路是兼容的：

1. 订阅 `/terrain_map`
2. 订阅 `/terrain_map_ext`
3. 订阅 `/state_estimation_at_scan`
4. 订阅 `/registered_scan`
5. 发布 `/way_point`

所以结论是：

1. **可以考虑重新接入**
2. 但不建议直接和当前 `far_planner` 混在同一个入口里试
3. 应该做成与 FAR 互斥的单独探索模式

详细分析见 `docs_ly/tare_integration_plan.md`。

## 5. 当前最建议的文档阅读顺序

1. `docs_ly/run_guide.md`
2. `docs_ly/current_status_20260311.md`
3. `docs_ly/navigation_debug_spin_issue_20260309.md`
4. `docs_ly/tare_integration_plan.md`
5. `docs_ly/project_status_20260228.md`
6. `docs_ly/strategy_overview_20260228.md`

## 6. 旧结论中已经过时的部分

以下说法现在不应再默认当真：

1. “当前系统还没真正跑起来”
2. “`/path` 只有 `localPlanner` 会发布”  
   这件事曾经不成立，后来才修正
3. “TARE 只是以后再说，暂时完全不用看”  
   现在已经可以开始做重新接入评估

## 7. 当前阶段的现实判断

如果只追求“当前系统能不能跑”：

1. 答案是能跑
2. 而且主入口已经比较清晰

如果追求“当前系统能不能稳定地漂亮到点”：

1. 还不能下这个结论
2. 近目标收敛仍是当前最值得继续攻克的问题
