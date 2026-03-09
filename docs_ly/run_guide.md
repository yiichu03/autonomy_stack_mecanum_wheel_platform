# 当前运行指南（2026-03-09）

> 这份文档是当前代码状态下的主运行指南。  
> 如果与 `project_status_20260228.md` 或 `strategy_overview_20260228.md` 有冲突，以本文和代码为准。

## 1. 适用范围

当前这份指南覆盖两种最常用场景：

1. 干跑：传感器实时采集，不接底盘，只观察 RViz 和 `/cmd_vel`
2. 实机联调：在干跑确认无明显问题后，再接 Scout Mini 底盘

当前主入口有两个：

1. `system_scout_hesai.launch.py`
   只跑 Base Autonomy，适合近距离 waypoint 调试
2. `system_scout_hesai_with_far_planner.launch.py`
   在上面基础上再接 `far_planner`，适合较远目标点和全局路径可视化

## 2. 当前代码状态摘要

当前代码和文档最重要的事实是：

1. FAST-LIO2 已经直接集成到主 launch 中
2. FAST-LIO2 的输出先进入
   `/state_estimation_raw` 和 `/registered_scan_raw`
3. 然后经
   `odom_frame_relay.py` 和 `registeredScanFrameRelay`
   统一到导航栈使用的 `/state_estimation` 和 `/registered_scan`
4. `pathFollower` 现在直接发布 `geometry_msgs/Twist` 到 `/cmd_vel`
5. 仍保留 `/cmd_vel_stamped`，但主要供仿真/调试链路使用
6. 主 launch 默认开启调试日志，按运行时间写到
   `runtime_logs/navigation_debug/<时间戳>/`
7. RViz 里已经能直接看 far planner 的
   `goal / waypoint / global path / VGraph`

## 3. 运行前先知道的事

### 3.1 干跑时不需要底盘

如果只是验证导航和控制输出是否合理，跑到观察 `/cmd_vel` 这一步就够了。  
`scout_base` 和 CAN 并不是干跑前置条件。

### 3.2 实机前先 source 的工作区

主导航终端通常至少需要：

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```

如果你刚重新编译过当前工作区，最好重新开一个终端再 source 一次，避免仍停留在旧环境。

### 3.3 当前已知问题

当前虽然主流程已经跑通，但仍有一个重要已知问题正在定位中：

1. 在 `twoWayDrive=false` 的 Scout 模式下，`localPlanner` 偶尔会产出后向局部路径
2. 外在表现是小车会左右旋转，或者长时间原地调头
3. 对应分析见
   `docs_ly/navigation_debug_spin_issue_20260309.md`

这不影响干跑流程本身，但会影响“能否稳定到达目标点”的体验。

## 4. 干跑步骤（实时传感器）

### 终端 A：PTP 主钟

```bash
sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
```

等 `rms` 稳定后再继续。

### 终端 B：同步系统时钟

```bash
sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m
```

等 `offset` 收敛后再继续。

这两步的目的只有一个：让 Hesai 时间戳、系统时钟和 RealSense IMU 时间戳尽量同源，保证 FAST-LIO2 能稳定融合。

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

期望大约 `10 Hz`。

### 终端 D：RealSense 驱动

```bash
source ~/Documents/isaac_ros_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  unite_imu_method:=1 \
  enable_gyro:=true \
  enable_accel:=true
```

注意：

1. `unite_imu_method:=1` 是必须的，否则不会稳定发布 `/camera/imu`
2. 不建议额外打开 `global_time_enabled:=true`，以免破坏当前时间同步链路

可选检查：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /camera/imu
```

期望大约 `200 Hz`。

### 终端 E：主导航栈

#### 方案一：只跑 Base Autonomy

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py
```

#### 方案二：接 far_planner

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai_with_far_planner.launch.py
```

当前默认会同时启动 RViz，并在终端打印本次调试日志目录。

### 终端 F：观察速度命令

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /cmd_vel
```

没有设置目标点之前，全零是正常的。

## 5. RViz 怎么用

### 5.1 Base Autonomy 模式

请使用 **Waypoint** 工具。  
它会直接往 `/way_point` 发目标点，绕过 `far_planner`，更适合近距离局部调试。

当前你能看到的主要东西：

1. `/registered_scan`
2. `/terrain_map`
3. `/free_paths`
4. `/path`
5. `/way_point`

### 5.2 with_far_planner 模式

请使用 **Goalpoint** 工具。  
不要再用 Waypoint，因为那会绕过 `far_planner`。

当前你能在 RViz 里直接看到：

1. 红球：`original_goal`
2. 紫球：`waypoint`
3. 绿球：`free_goal`
4. 蓝色线：`global path`
5. `VGraph`

当前 `VGraph` 里最常见的两类线：

1. 红线：`polygon_edge`
   障碍物轮廓边
2. 蓝绿色线：`freespace_vgraph`
   far planner 内部的自由空间图连接边

它们是调试可视化，不是底盘直接跟踪的轨迹。

## 6. `/cmd_vel` 怎么判断是否大致正常

当前 Scout 入口默认：

1. `maxSpeed = 0.5 m/s`
2. `cmd_y = 0`
3. `maxYawRate = 60 deg/s ≈ 1.047 rad/s`

所以常见合理范围是：

```text
linear.x:   0.0 ~ 0.5
linear.y:   0.0
angular.z: -1.047 ~ 1.047
```

如果你看到：

1. `cmd_x` 能稳定起来，而 `cmd_yaw` 逐渐变小
   说明局部路径和控制器基本一致
2. `cmd_x` 长时间为 `0`，`cmd_yaw` 长时间打满
   更像是 planner 给了一条后向或强侧向的局部路径

这时应优先去看日志，而不是先怀疑底盘。

## 7. 本次运行后的日志在哪里

当前主 launch 默认会把日志写到：

```text
runtime_logs/navigation_debug/<时间戳>/
```

通常包含两个文件：

1. `local_planner.csv`
2. `path_follower.csv`

用途分别是：

1. `local_planner.csv`
   看目标相对方向、选中的路径组、`selected_rot_deg`、左右障碍统计
2. `path_follower.csv`
   看跟踪目标点、`dir_diff`、速度命令、路径更新模式

更详细的调试思路见：

1. `docs_ly/navigation_debug_spin_issue_20260309.md`
2. `docs_ly/current_status_20260309.md`

## 8. 干跑后该看什么

### 8.1 如果只是确认“系统通了没”

重点看：

1. FAST-LIO2 是否正常出图
2. `/terrain_map` 是否有数据
3. `/free_paths` 是否出现
4. 点击目标点后 `/cmd_vel` 是否有合理变化

### 8.2 如果是确认“为什么它在乱转”

重点看：

1. `runtime_logs/navigation_debug/<时间戳>/local_planner.csv`
2. `runtime_logs/navigation_debug/<时间戳>/path_follower.csv`

尤其关注这些字段：

1. `selected_rot_deg`
2. `freeze_status`
3. `goal_rel_x`, `goal_rel_y`
4. `target_x`, `target_y`
5. `dir_diff`
6. `cmd_x`, `cmd_yaw`

## 9. 实机联调（可选，不属于干跑前置）

如果干跑阶段已经确认：

1. RViz 与点云显示正常
2. `/cmd_vel` 的方向和量级没有明显离谱

再进入实机阶段。

### CAN 与 Scout 驱动

```bash
sudo modprobe gs_usb
sudo ip link set can2 up type can bitrate 500000
ros2 launch scout_base scout_mini_base.launch.py port_name:=can2
```

这一步不是干跑的一部分，而是“准备真正让底盘动”时才需要。

## 10. 推荐一起看的文档

如果你后面准备系统读代码，推荐顺序：

1. `docs_ly/current_status_20260309.md`
2. `docs_ly/navigation_debug_spin_issue_20260309.md`
3. `docs_ly/project_status_20260228.md`
4. `docs_ly/strategy_overview_20260228.md`

其中：

1. 前两份是当前状态和当前问题
2. 后两份更像 2 月底阶段性记录，保留了很多背景，但已有部分内容过时
