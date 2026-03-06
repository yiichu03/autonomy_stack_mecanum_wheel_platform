# 干跑操作指南（实时传感器 + 观察 /cmd_vel）

> 适用场景：小车不开底盘，传感器实时采集，验证导航栈控制命令方向和量级是否合理。
>
> 日期：2026-03-03

---

## 前置条件

| 设备 | 接口 | 确认方法 |
|------|------|---------|
| Hesai XT32 | eno1（192.168.188.201） | `ping 192.168.188.201` |
| RealSense D455 | USB | `lsusb \| grep Intel` |
| Scout Mini 底盘 | **不连接**（干跑不需要） | — |

---

## 启动顺序

### 终端 A — PTP 主钟（保持运行）

```bash
sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
```

等待 `rms` 值稳定在几百纳秒量级后继续。

---

### 终端 B — 系统时钟同步（保持运行）

```bash
sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m
```

等待 `offset` 收敛到几微秒后继续。

> **为什么需要这两步：**
> `ptp4l` 把 Hesai 的硬件时钟同步到 Orin 的 PTP 网卡时钟（ptp0）；
> `phc2sys` 再把系统 CLOCK_REALTIME 对齐到 ptp0。
> 结果：Hesai 时间戳 ≈ CLOCK_REALTIME ≈ RealSense IMU 时间戳，三者同源，FAST-LIO2 可正常融合。

---

### 终端 C — Hesai 驱动（保持运行）

```bash
source ~/Documents/hesai_ws/install/setup.bash
ros2 launch hesai_ros_driver start.py
```

验证（新建一个小窗口）：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /lidar_points
# 期望：~10 Hz
```

---

### 终端 D — RealSense 驱动（保持运行）

```bash
source ~/Documents/isaac_ros_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  unite_imu_method:=1 \
  enable_gyro:=true \
  enable_accel:=true
```

> **注意：** 必须加 `unite_imu_method:=1`，否则驱动不发布 `/camera/imu`，FAST-LIO2 无法获取 IMU 数据。
> 不要加 `global_time_enabled:=true`，那会改用相机内部时钟，破坏与 Hesai 的时间同步。

验证：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /camera/imu
# 期望：~200 Hz
```

---

### 终端 E — 主导航栈

#### 方案一：只跑 Base Autonomy（近距离 Waypoint 导航）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py
```

#### 方案二：加入 far_planner（全局路径规划）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai_with_far_planner.launch.py
```

等待 FAST-LIO2 初始化完成（终端出现建图信息，RViz 显示点云）。

---

### 终端 F — 观察控制命令

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /cmd_vel
```

没有 waypoint 时输出全为零，这是正常的。

---

## RViz 操作

### 方案一（Base Autonomy）

source /opt/ros/humble/setup.bash
  ros2 run tf2_tools view_frames

1. 工具栏选择 **Waypoint** 工具（快捷键 `w`）
2. 在已建出的点云地图上点击一个目标点
3. 观察 `/cmd_vel` 输出

### 方案二（far_planner）

1. 工具栏选择 **Goalpoint** 工具（快捷键 `w`，与 Waypoint 不同的插件）
2. 点击地图上一个较远的目标点
3. 同时观察两个 topic：

```bash
# 窗口 1：far_planner 发出的中间目标点
ros2 topic echo /way_point

# 窗口 2：最终控制命令
ros2 topic echo /cmd_vel
```

sudo modprobe gs_usb
sudo ip link set can2 up type can bitrate 500000
candump can2
ros2 launch scout_base scout_mini_base.launch.py port_name:=can2

ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.00}, angular: {z: 0.0}}"
# 车应该轻微前移，立刻停止
---

## /cmd_vel 判断标准

正常输出示例（Twist 格式）：

```
linear:
  x: 0.3~0.5    # 前进速度，不超过 maxSpeed=0.5 m/s
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: ±0.x       # 转向角速度，朝向目标点时接近 0
```

| 观察点 | 正常 | 可能原因 |
|--------|------|---------|
| 放置 waypoint 后有输出 | `linear.x ≠ 0` | 若为零：FAST-LIO2 未初始化，或 waypoint 工具未触发 |
| 速度上限 | `\|linear.x\| ≤ 0.5` | maxSpeed 参数生效 |
| 到达附近后停止 | 三个值趋近于零 | goalClearRange=0.35m 内视为到达 |
| 朝向目标时转向小 | `\|angular.z\|` 接近 0 | 转向控制正常 |

---

## 数据流（当前配置）

```
Hesai XT32  →  /lidar_points  ─────────────────────────────────┐
                                                                 │
RealSense D455  →  /camera/imu  ──────────────────────────────┐ │
                                                               ↓ ↓
                                                        fastlio_mapping
                                                               │
                        /Odometry → [remap] → /state_estimation_raw
                        /cloud_registered → [remap] → /registered_scan
                                │                        │
                         odom_frame_relay                │
                                │                        │
                        /state_estimation                │
                                │                        │
                        sensor_scan_generation ←─────────┘
                                │
                          /sensor_scan
                                │
                     terrain_analysis[_ext]
                                │
                          /terrain_map
                                │
              localPlanner  ←── /way_point（RViz 工具 或 far_planner）
                                │
                         /path
                                │
                         pathFollower
                                │
                    /cmd_vel (Twist)  ← echo 观察此处
```

---

## 关键参数（当前配置）

| 参数 | 值 | 依据 |
|------|----|------|
| vehicleLength | 0.70 m | Scout Mini 612 mm → 向上取整 |
| vehicleWidth | 0.60 m | Scout Mini 580 mm → 向上取整 |
| sensorOffsetX | 0.0 m | `B_p_L=[0,0,0]`，雷达原点=车体坐标系原点 |
| sensorOffsetY | 0.0 m | 同上 |
| maxSpeed | 0.5 m/s | 保守初始值，Scout Mini 上限约 1.5 m/s |
| vehicleHeight | 1.5 m | **待修正**，实测雷达离地高度后更新 |

---

## 待办（干跑后）

- [ ] 量 Hesai XT32 激光扫描平面离地高度，更新 `vehicleHeight`（在 `terrain_analysis.launch` 和 `terrain_analysis_ext.launch` 中修改）
- [ ] 确认 /cmd_vel 方向和量级合理后，连接底盘进行 Phase D 实车测试
- [ ] 实车测试前确认 CAN 接口：`sudo ip link set can0 up type can bitrate 500000`
