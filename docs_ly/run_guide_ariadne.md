# ARiADNE + TARE 运行指南（2026-04-06）

> 这份文档覆盖在 Scout Mini + Hesai XT32 + RealSense D455 上运行 **ARiADNE** 或 **TARE** 自主探索的完整流程。
> 两种规划器输出相同的 `/way_point` 接口，下游导航完全一致，通过不同 launch 文件切换。
> 如果与更早讨论记录冲突，以本文和代码为准。

---

## 1. ARiADNE vs TARE 快速对比

| 维度 | TARE | ARiADNE |
|---|---|---|
| 类型 | 基于 viewpoint 覆盖的经典规划 | 深度强化学习（DRL）策略网络 |
| 规划器输入 | `/terrain_map`, `/registered_scan` | `/projected_map`（OccupancyGrid） |
| 规划器输出 | `/way_point` | `/way_point`（相同接口） |
| 地图来源 | 内部维护 GridWorld | octomap_server 产生的 2D 占用格栅 |
| 权重文件 | 无（纯几何） | `checkpoint.pth`（已在代码库中） |
| 额外依赖 | 无 | `octomap_server` + `rl_planner` |
| 下游导航栈 | localPlanner -> pathFollower -> /cmd_vel | 完全相同 |

---

## 2. 环境 source（所有终端共用）

运行任何探索模式前，主导航终端都需要 source **五个**工作区：

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```

> **注意**：`autonomy_stack` 必须最后 source，它的 install/ 会覆盖上游同名包。
> TARE 模式不需要 ARiADNE 和 octomap_ws，但多 source 不影响。统一五行省心。

---

## 3. 传感器启动（所有模式通用）

### 终端 A：PTP 主钟

```bash
sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
```

### 终端 B：同步系统时钟

```bash
sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m
```

### 终端 C：Hesai XT32

```bash
source ~/Documents/hesai_ws/install/setup.bash
ros2 launch hesai_ros_driver start.py
```

检查：`ros2 topic hz /lidar_points` -> 约 10 Hz

### 终端 D：RealSense D455（IMU）

```bash
source ~/Documents/isaac_ros_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  unite_imu_method:=1 \
  enable_gyro:=true \
  enable_accel:=true
```

检查：`ros2 topic hz /camera/imu` -> 约 200 Hz

---

## 4. 终端 E：选择探索模式

先 source 五行环境（见第 2 节），然后根据场景选一个 launch。

### 方案一：ARiADNE（DRL 探索）

适合快速探索，行为偏激进，走廊和房间都可以。

```bash
# 默认参数，适合大多数场景
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py

# 窄走廊（<2m）：降低地图分辨率让网格更精细
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  maxSpeed:=0.3

# 开阔房间：默认参数即可，可适当提速
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  maxSpeed:=0.5
```

ARiADNE 关键参数：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `ariadneSensorRange` | 20.0 m | 感知半径，与 Hesai XT32 量程匹配 |
| `ariadneMapResolution` | 0.4 m | OccupancyGrid 每格大小，越小越精细但越慢 |
| `ariadneNodeResolution` | 2.0 m | 图节点间距，决定 waypoint 粗细粒度 |
| `ariadneBaseFrame` | `sensor_at_scan` | octomap 的 base frame |
| `ariadnePublishGraph` | false | 是否在 RViz 可视化规划图（会增加 CPU 开销） |

### 方案二：TARE（经典几何探索）

行为更保守、更可预测，有多种配置适配不同场景。

```bash
# 小房间（默认）
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py

# 窄走廊（<2m）：用 corridor_v2 或 corridor_v5（最短 waypoint 距离）
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=corridor_v2.yaml maxSpeed:=0.3

# 中等走廊（2-3m）
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=corridor_medium.yaml

# 宽走廊 + 偶尔有开阔区域
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=corridor_v4.yaml

# 大房间 / 开阔空间
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=indoor_large.yaml

# 室外
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=outdoor.yaml
```

TARE 配置选择指南：

| 配置 | 适用场景 | 传感器范围 | waypoint 距离 | 碰撞余量 |
|---|---|---|---|---|
| `indoor_small.yaml` | 小房间（默认） | 3.0 m | 4.0 / 1.5 m | 0.35 m |
| `corridor_v2.yaml` | 窄走廊 <2m | 3.0 m | 2.5 / 1.0 m | 0.25 m |
| `corridor_v5.yaml` | 窄走廊 <2m（同 v2） | 3.0 m | 2.5 / 1.0 m | 0.25 m |
| `corridor_v3.yaml` | 窄走廊，更灵敏转弯检测 | 3.0 m | 4.0 / 1.5 m | 0.35 m |
| `corridor_medium.yaml` | 中等走廊 2-3m | 4.0 m | 5.0 / 2.0 m | 0.35 m |
| `corridor_v4.yaml` | 宽走廊 + 开阔区 | 4.0 m | 4.0 / 1.5 m | 0.35 m |
| `indoor_large.yaml` | 大房间 >4m | 3.5 m | 8.0 / 3.5 m | 0.60 m |
| `outdoor.yaml` | 室外 | — | — | — |

> `corridor_v1.yaml` 与 `indoor_small.yaml` 基本相同，作为基线对照。

---

## 5. 启动后验证

### 5.1 通用检查（两种模式都要做）

```bash
ros2 topic hz /state_estimation      # 期望 ~10 Hz
ros2 topic hz /registered_scan       # 期望 ~10 Hz
ros2 topic echo /way_point           # 应该持续更新
ros2 topic echo /cmd_vel             # 有 way_point 后应有非零输出
```

### 5.2 ARiADNE 额外检查

```bash
ros2 topic hz /projected_map         # 期望 ~1-2 Hz（octomap 更新频率）
ros2 node list | grep rl_planner     # 应输出 /rl_planner
ros2 topic hz /sensor_scan           # 期望 ~10 Hz
```

RViz 里订阅 `/projected_map`（Map 类型）能看到 2D 占用格栅扩展。

### 5.3 TARE 额外检查

```bash
ros2 node list | grep tare           # 应输出 tare_planner_node
```

---

## 6. 实机联调

确认干跑正常后（RViz 点云正常、`/cmd_vel` 方向量级合理），再启动底盘：

```bash
# 终端 F：底盘驱动
sudo ip link set can2 up type can bitrate 500000
ros2 launch scout_base scout_mini_base.launch.py port_name:=can2
```

如果 can2 不行试 can0：

```bash
sudo ip link set can0 up type can bitrate 500000
ros2 launch scout_base scout_mini_base.launch.py port_name:=can0
```

---

## 7. 故障排查

### `/projected_map` 只显示起始点附近一小块（ARiADNE 模式）

octomap_server 找不到 `sensor_at_scan -> map` 的 TF。

```bash
ros2 run tf2_ros tf2_echo map sensor_at_scan
```

没有输出则检查 FAST-LIO2 和 `odom_frame_relay` 是否正常。

### `rl_planner` 报 `Waiting for map and location data...`

上游 `/projected_map` 或 `/state_estimation` 没数据，先排查传感器和 FAST-LIO2。

### `rl_planner` ImportError: torch / No module named 'skimage'

```bash
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip3 install scikit-image
```

> JetPack 如果已预装 torch 就不用重装。

### `rl_planner` 找不到 checkpoint.pth

```bash
cd ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner
colcon build --packages-select rl_planner
ls install/rl_planner/share/rl_planner/model/   # 应有 checkpoint.pth
```

### TARE `/way_point` 没有输出

检查 `tare_planner_node` 终端日志。常见原因是 OR-Tools 库架构不匹配：

```bash
file src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296
# 必须是 ARM aarch64
```

### 机器人收到 `/way_point` 但不动

```bash
ros2 topic info /way_point --verbose
```

应有 `localPlanner` 作为 subscriber。没有则 source 顺序有问题，重开终端。

---

## 8. 数据流概览

### ARiADNE 模式

```
Hesai XT32 (/lidar_points)
    |
    v
FAST-LIO2
    |
    +-- /state_estimation_raw --> odom_frame_relay --> /state_estimation
    |                                                       |
    +-- /registered_scan_raw --> registeredScanFrameRelay   |
                                         |                  |
                                    /sensor_scan            |
                                         |                  |
                                    octomap_server          |
                                         |                  |
                                   /projected_map           |
                                         |                  |
                                         v                  v
                                    rl_planner <------------+
                                         |
                                    /way_point
                                         |
                                    localPlanner --> /path --> pathFollower --> /cmd_vel
```

### TARE 模式

```
Hesai XT32 (/lidar_points)
    |
    v
FAST-LIO2
    |
    +-- /state_estimation --> tare_planner --> /way_point
    |                              ^
    +-- /registered_scan ----------+
                                   |
                              localPlanner --> /path --> pathFollower --> /cmd_vel
```

---

## 9. 编译备忘

改了代码后需要重新编译对应的包：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform

# 改了 launch 文件
colcon build --packages-select vehicle_simulator

# 改了 TARE 配置或代码
colcon build --packages-select tare_planner

# 改了 ARiADNE
cd ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner
colcon build --packages-select rl_planner
```

编译后记得重新 source：`source install/setup.bash`

---

## 10. 推荐文档

1. `docs_ly/run_guide.md` — 基础导航栈运行指南（Base Autonomy / far_planner 模式）
2. `docs_ly/tare_integration_plan.md` — TARE 接入过程记录
3. `docs_ly/simulation_guide.md` — x86 仿真指南
