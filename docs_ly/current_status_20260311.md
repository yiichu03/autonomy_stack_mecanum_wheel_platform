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

## 4. 探索模块 TARE 已经接入（2026-03-11）

### 4.1 完成内容

截至 2026-03-11，TARE 探索规划器已经完成接入，可以直接使用：

1. OR-Tools ARM64 库已替换（见 4.2 节）
2. `tare_planner` 已编译成功（仅 warnings，无 errors）
3. 新 launch 文件已创建并安装：`system_scout_hesai_with_tare.launch.py`

### 4.2 OR-Tools ARM64 替换过程

仓库原自带的 `libortools.so.9.8.3296` 是 x86-64 架构，无法在 Jetson AGX Orin（aarch64）上运行。

**解决方案：** 下载 `or-tools_arm64_debian-11_cpp_v9.8.3296.tar.gz`（与仓库自带版本号完全一致，确保 API 兼容），解压后替换 `.so` 文件。

操作记录（已完成，无需再做）：

```bash
# 解压
tar -xzf docs_ly/or-tools_arm64_debian-11_cpp_v9.8.3296.tar.gz -C /tmp/

# 替换 .so 文件（在 autonomy_stack 根目录下）
cp /tmp/or-tools_aarch64_Debian-11_cpp_v9.8.3296/lib/libortools.so.9.8.3296 \
   src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296

# 更新 symlinks
cd src/exploration_planner/tare_planner/or-tools/lib/
ln -sf libortools.so.9.8.3296 libortools.so.9
ln -sf libortools.so.9 libortools.so
```

替换后用 `file` 命令验证架构：

```bash
file src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296
# 期望输出：ELF 64-bit LSB shared object, ARM aarch64, ...
```

备注：两个下载包 `or-tools_arm64_debian-11_cpp_v9.8.3296.tar.gz` 和 `or-tools_arm64_debian-11_cpp_v9.12.4544.tar.gz` 均存放在 `docs_ly/` 目录中。使用 v9.8.3296 版本（与仓库头文件版本完全对应），**不要用 v9.12**（版本不匹配会有 API 不兼容风险）。

### 4.3 tare_planner 编译

OR-Tools 替换完成后，直接编译：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon build --packages-select tare_planner
```

编译耗时约 5 分钟，有若干 sign-compare warnings，无 errors，属正常。

### 4.4 新 launch 文件

已创建：`src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_tare.launch.py`

主要特点：

1. 去掉 `far_planner`，加入 `tare_planner_node`
2. 使用 `indoor_small.yaml` 配置（安装后位于 `install/tare_planner/share/tare_planner/indoor_small.yaml`）
3. `kAutoStart=true`：启动后自动开始探索
4. `/way_point` 接口与 `localPlanner` 完全兼容

与 `far_planner` 模式互斥，通过不同 launch 文件切换。详见 `docs_ly/run_guide.md` 第 4 节方案三。

### 4.5 TARE 数据流

```text
/terrain_map + /terrain_map_ext + /state_estimation_at_scan + /registered_scan
  -> tare_planner_node
  -> /way_point
  -> localPlanner → /path → pathFollower → /cmd_vel
```

详细分析和使用建议见 `docs_ly/tare_integration_plan.md`。

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
