# 当前运行指南（2026-03-11）

> 这份文档是当前代码状态下的主运行指南。  
> 如果与 `project_status_20260228.md`、`strategy_overview_20260228.md` 或更早讨论记录冲突，以本文和代码为准。

## 1. 适用范围

当前主流程已经可以正常启动并运行，最常用的是两种模式：

1. `system_scout_hesai.launch.py`
   只跑 Base Autonomy，适合近距离 waypoint 调试
2. `system_scout_hesai_with_far_planner.launch.py`
   在上面基础上接 `far_planner`，适合较远目标点和全局路径可视化

## 2. 当前代码状态摘要

截至 2026-03-11，当前代码有几个必须知道的事实：

1. FAST-LIO2 已直接接入主 launch
2. FAST-LIO2 输出会先进入 `/state_estimation_raw` 和 `/registered_scan_raw`
3. 然后经 `odom_frame_relay.py` 和 `registeredScanFrameRelay` 统一到 `/state_estimation` 和 `/registered_scan`
4. FAST-LIO2 自己的历史轨迹已隔离到 `/fastlio_path`，不再让 `pathFollower` 误订阅
5. `pathFollower` 当前直接发布 `geometry_msgs/Twist` 到 `/cmd_vel`
6. 主 launch 默认开启调试日志，写到 `runtime_logs/navigation_debug/<时间戳>/`
7. RViz 里可以直接看 `goal / waypoint / free_goal / global path / VGraph / free_paths / terrain_map`

## 3. 运行前先知道的事

### 3.1 干跑时不需要底盘

如果只是验证导航链路和控制输出，跑到观察 `/cmd_vel` 这一步就够了。  
`scout_base`、CAN 和底盘上电都不是干跑前置条件。

### 3.2 主导航终端需要 source 的环境

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```

如果你刚重新编译过当前工作区，最好新开终端再 source 一次，避免仍停留在旧环境。

### 3.3 当前建议先确认 `/path` 的归属

当前运行前，建议先确认 `/path` 只由 `localPlanner` 发布：

```bash
ros2 topic info /path --verbose
ros2 topic info /fastlio_path --verbose
```

正确结果应该是：

1. `/path`：只剩 `localPlanner` 一个 publisher
2. `/fastlio_path`：由 `fastlio_mapping` 发布

如果 `/path` 里仍能看到 `fastlio_mapping`，说明你跑到的不是当前安装版本，需要重新编译并重新 source。

### 3.4 当前最重要的已知问题

当前主链已经能跑，但还有两个现实问题需要带着预期去看：

**问题 1：近目标时仍可能反复转向**

1. `global path` 和大段行进通常已经正常
2. 但接近目标后，`localPlanner` 仍可能重新发布多点路径
3. `pathFollower` 每次收到新 `/path` 都会重新按当前路径转向
4. 所以会出现“明明已经很接近目标，但还在反复转”的现象

这不是启动失败问题，而是当前最主要的控制收敛问题。

**关于探索模块 TARE：已接入，可直接使用**

1. `tare_planner` 已完成 ARM64 编译（OR-Tools 库已从 x86-64 替换为 aarch64）
2. 新增 `system_scout_hesai_with_tare.launch.py` 入口（见第 4 节方案三）
3. 与 `far_planner` 模式互斥，通过不同 launch 文件切换
4. 编译和接入过程详见 `docs_ly/current_status_20260311.md` 第 4 节

对应分析见：

1. `docs_ly/current_status_20260311.md`
2. `docs_ly/navigation_debug_spin_issue_20260309.md`
3. `docs_ly/tare_integration_plan.md`

### 3.5 如果你改了 launch 文件，记得重新编译

Python launch 文件是从 `install/` 目录运行的。  
如果你改了 `src/` 下的 launch 文件，需要重新编译：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build --packages-select vehicle_simulator
source install/setup.bash
```

## 4. 干跑步骤（实时传感器）

### 终端 A：PTP 主钟

```bash
sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
```

### 终端 B：同步系统时钟

```bash
sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m
```

这两步的目的只有一个：尽量让 Hesai、系统时钟和 RealSense IMU 时间戳同源，保证 FAST-LIO2 稳定融合。

### 终端 C：Hesai 驱动

```bash
source ~/Documents/hesai_ws/install/setup.bash
ros2 launch hesai_ros_driver start.py
```

可选检查：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /lidar_points
```

期望约 `10 Hz`。

### 终端 D：RealSense 驱动

```bash
source ~/Documents/isaac_ros_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  unite_imu_method:=1 \
  enable_gyro:=true \
  enable_accel:=true
```

可选检查：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /camera/imu
```

期望约 `200 Hz`。

### 终端 E：主导航栈

#### 方案一：只跑 Base Autonomy

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py
```

#### 方案二：接 far_planner（人工指定目标点）
默认是 outdoor.yaml

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai_with_far_planner.launch.py
```

#### 方案三：接 TARE（自主探索，无需指定目标点）

启动后机器人自动开始探索，无需在 RViz 中点击目标。

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py

ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=indoor_large.yaml
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=outdoor.yaml


```

验证 TARE 是否正常出探索目标点：

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 node list | grep tare
ros2 topic echo /way_point

source /opt/ros/humble/setup.bash
ros2 topic echo /way_point
```

启动后数秒内应看到 `/way_point` 持续更新。若无输出，检查 `tare_planner_node` 终端日志。

> 注意：方案二和方案三互斥，两者都会发布 `/way_point`，不能同时运行。

### 终端 F：观察速度命令

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /cmd_vel
```

没有设置目标点之前，全零是正常的。

## 5. RViz 怎么用

### 5.1 Base Autonomy 模式

请使用 **Waypoint** 工具。  
它直接往 `/way_point` 发目标点，绕过 `far_planner`，适合近距离局部调试。

当前常看的显示项：

1. `/registered_scan`
2. `/terrain_map`
3. `/free_paths`
4. `/path`
5. `/way_point`

### 5.2 with_far_planner 模式

请使用 **Goalpoint** 工具。  
不要再用 Waypoint，因为那会绕过 `far_planner`。

当前 RViz 里常见的含义是：

1. 红球：`original_goal`
2. 紫球：`waypoint`
3. 绿球：`free_goal`
4. 蓝色线：`global path`
5. 红线：`polygon_edge`
6. 蓝绿色线：`freespace_vgraph`

如果只看到红球，看不到绿球，最常见原因是：

1. `free_goal` 和 `original_goal` 重合
2. 或者规划没有成功，`free_goal` 根本没单独偏移出来

## 6. `/cmd_vel` 怎样算大致正常

当前 Scout 入口默认大致范围是：

1. `linear.x: 0.0 ~ 0.5`
2. `linear.y: 0.0`
3. `angular.z: -1.047 ~ 1.047`

判断方式：

1. `cmd_x` 能起来、`cmd_yaw` 逐渐减小：通常是正常靠近目标
2. `cmd_x` 长时间很小、`cmd_yaw` 长时间打满：更像是在不断重对齐局部路径

## 7. 本次运行后的日志在哪里

主 launch 默认把日志写到：

```text
runtime_logs/navigation_debug/<时间戳>/
```

通常包含：

1. `local_planner.csv`
2. `path_follower.csv`

当前最值得看的字段：

1. `goal_rel_x`, `goal_rel_y`
2. `goal_rel_dis`
3. `selected_group_raw`, `selected_rot_deg`
4. `path_points`, `path_published`
5. `target_x`, `target_y`
6. `dir_diff`
7. `cmd_x`, `cmd_yaw`

## 8. 实机联调（可选，不属于干跑前置）

如果干跑阶段已经确认：

1. RViz 和点云显示正常
2. `/cmd_vel` 方向与量级没有明显离谱

再进入实机阶段。

```bash
sudo modprobe gs_usb
candump can0
candump can2

sudo ip link set can2 up type can bitrate 500000
ros2 launch scout_base scout_mini_base.launch.py port_name:=can2

sudo ip link set can2 up type can bitrate 500000
ros2 launch scout_base scout_mini_base.launch.py port_name:=can0

```

## 9. 推荐一起看的文档

建议按这个顺序建立当前上下文：

1. `docs_ly/run_guide.md`
2. `docs_ly/current_status_20260311.md`
3. `docs_ly/navigation_debug_spin_issue_20260309.md`
4. `docs_ly/tare_integration_plan.md`
5. `docs_ly/project_status_20260228.md`
6. `docs_ly/strategy_overview_20260228.md`

前三份是当前事实和当前问题。  
后两份主要保留背景和路线，不应直接当作当前运行事实。
