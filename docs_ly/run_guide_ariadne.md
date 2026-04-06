# ARiADNE 实机运行指南（2026-04-06）

> 这份文档覆盖在 Scout Mini + Hesai XT32 + RealSense D455 上运行 ARiADNE DRL 自主探索的完整流程。
> 如果与更早的讨论记录冲突，以本文和代码为准。

---

## 1. ARiADNE 是什么，和 TARE 有什么区别

| 维度 | TARE | ARiADNE |
|---|---|---|
| 类型 | 基于 viewpoint 覆盖的经典规划 | 深度强化学习（DRL）策略网络 |
| 规划器输入 | `/terrain_map`, `/registered_scan` | `/projected_map`（OccupancyGrid） |
| 规划器输出 | `/way_point` | `/way_point`（相同接口） |
| 地图来源 | 内部维护 GridWorld | octomap_server 产生的 2D 占用格栅 |
| 权重文件 | 无（纯几何） | `checkpoint.pth`（已在代码库中） |
| 下游导航栈 | localPlanner → pathFollower → /cmd_vel | 完全相同 |

两者的 `/way_point` 接口一致，所以下游（localPlanner、pathFollower、底盘）完全不用改。

---

## 2. 代码库和工作区说明

运行 ARiADNE 需要同时 source **三个**工作区：

| 工作区 | 路径 | 包含内容 |
|---|---|---|
| autonomy_stack | `~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/` | FAST-LIO2 relay、terrain_analysis、local_planner、pathFollower、RViz launch |
| ARiADNE | `~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/` | `rl_planner` 节点、权重文件 |
| fastlio_ws | `~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/` | FAST-LIO2 本体 |

TARE 模式不需要 ARiADNE 工作区。ARiADNE 模式需要多 source 一个。

---

## 3. 首次在 AGX Orin 上使用前的准备

### 3.1 拉取最新代码

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
git pull

cd ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner
git pull
```

### 3.2 确认 PyTorch 已安装（aarch64）

ARiADNE 用 PyTorch 做神经网络推理（CPU 模式，不需要 GPU）：

```bash
python3 -c "import torch; print(torch.__version__)"
```

如果没有安装：

```bash
# JetPack 环境优先用 NVIDIA 提供的轮子
pip3 show torch

# 如果没有，装 CPU 版
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

> 注意：如果 JetPack 已经预装了 torch（位于 `/usr/local/lib/python3.x/dist-packages/torch/`），
> 不要重复安装，直接用系统版本。

### 3.3 编译 ARiADNE-ROS-Planner（首次，或代码有更新时）

仓库里的 `build/` 和 `install/` 是在 x86_64 笔记本上生成的，**必须在 Orin 上重新编译**：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner
colcon build
```

编译成功后验证：

```bash
source install/setup.bash
ros2 pkg list | grep rl_planner   # 应该输出 rl_planner
```

### 3.4 编译 autonomy_stack（只需更新 vehicle_simulator 和 tare_planner）

如果是第一次 pull 到新的 corridor YAML 配置：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build --packages-select vehicle_simulator tare_planner
```

---

## 4. 数据流概览

```
Hesai XT32
    └─ /lidar_points
           │
           ▼
    FAST-LIO2 (fastlio_mapping)
           │
           ├─ /state_estimation_raw ─► odom_frame_relay ─► /state_estimation
           │                                                      │
           └─ /registered_scan_raw ─► registeredScanFrameRelay    │
                                                │                 │
                                                ▼                 │
                               sensor_scan_generation             │
                                                │                 │
                                         /sensor_scan             │
                                                │                 │
                                                ▼                 │
                                        octomap_server            │
                                                │                 │
                                       /projected_map             │
                                     (OccupancyGrid 2D)           │
                                                │                 │
                                                ▼                 ▼
                                          rl_planner ◄────────────┘
                                                │
                                          /way_point
                                                │
                                                ▼
                                        localPlanner
                                                │
                                             /path
                                                │
                                                ▼
                                        pathFollower
                                                │
                                           /cmd_vel
                                                │
                                                ▼
                                         Scout Mini 底盘
```

---

## 5. 运行步骤

### 终端 A：PTP 主钟（Hesai 时间戳同步）

```bash
sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
```

### 终端 B：系统时钟同步

```bash
sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m
```

### 终端 C：Hesai XT32 驱动

```bash
source ~/Documents/hesai_ws/install/setup.bash
ros2 launch hesai_ros_driver start.py
```

验证：

```bash
ros2 topic hz /lidar_points   # 期望约 10 Hz
```

### 终端 D：RealSense D455 驱动（IMU）

```bash
source ~/Documents/isaac_ros_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  unite_imu_method:=1 \
  enable_gyro:=true \
  enable_accel:=true
```

验证：

```bash
ros2 topic hz /camera/imu   # 期望约 200 Hz
```

### 终端 E：主导航栈（ARiADNE 模式）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash

ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py
```

启动参数（可选，覆盖默认值）：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneSensorRange:=20.0 \
  ariadneMapResolution:=0.4 \
  ariadneNodeResolution:=2.0 \
  maxSpeed:=0.5
```

---

## 6. 启动后的验证清单

按顺序检查，任何一步失败先排查再往下走。

### 6.1 FAST-LIO2 是否正常建图

```bash
ros2 topic hz /state_estimation      # 期望 ~10 Hz
ros2 topic hz /registered_scan       # 期望 ~10 Hz
```

RViz 里能看到点云积累，说明 SLAM 正常。

### 6.2 sensor_scan 是否产生

```bash
ros2 topic hz /sensor_scan           # 期望 ~10 Hz
ros2 topic echo /sensor_scan --no-arr | grep frame_id
# 期望 frame_id: sensor_at_scan
```

### 6.3 octomap 是否建图（projected_map）

```bash
ros2 topic hz /projected_map         # 期望 ~1-2 Hz（octomap 更新频率）
```

RViz 里订阅 `/projected_map`（Map 类型）：应该能看到机器人周围的 2D 占用格栅在扩展。

如果 `/projected_map` 只显示起始点附近很小一块，说明 TF 有问题，见第 8 节故障排查。

### 6.4 ARiADNE 是否开始规划

```bash
ros2 topic echo /way_point           # 应该持续更新
ros2 node list | grep rl_planner     # 应该输出 /rl_planner
```

终端 E 里应该能看到 `initialize robot location at [x, y]` 的初始化日志。

### 6.5 底盘是否响应

```bash
ros2 topic echo /cmd_vel
```

有 `/way_point` 输入后，`cmd_vel` 应该有非零输出。

---

## 7. 与 TARE 模式的切换

两种模式都发布 `/way_point`，互斥，通过 launch 文件切换：

| 模式 | launch 文件 | 额外 source |
|---|---|---|
| ARiADNE | `system_scout_hesai_with_ariadne.launch.py` | `ARiADNE-ROS-Planner/install/setup.bash` |
| TARE | `system_scout_hesai_with_tare.launch.py` | 不需要 |

TARE 可以通过 `tareConfig` 参数指定走廊配置（v1~v5）：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=corridor_v1.yaml
```

---

## 8. 故障排查

### `/projected_map` 只显示起始点附近一小块

原因：octomap_server 找不到 `sensor_at_scan → map` 的 TF，导致只整合了第一帧点云。

检查 TF：

```bash
ros2 run tf2_ros tf2_echo map sensor_at_scan
```

如果报错或没有输出，说明 TF 链路断了，检查：
1. FAST-LIO2 是否正常（`/state_estimation` 有没有输出）
2. `odom_frame_relay` 节点是否在运行：`ros2 node list | grep relay`

### `rl_planner` 报 `Waiting for map and location data...` 一直等待

说明 `/projected_map` 或 `/state_estimation` 没有数据，先解决上游问题。

### `rl_planner` 启动后立即崩溃（ImportError: torch）

PyTorch 没有安装，见第 3.2 节。

### `rl_planner` 找不到模型文件

```
Model file not found: .../share/rl_planner/model/checkpoint.pth
```

说明 `colcon build` 没有正确把模型文件复制到 `install/`，重新编译：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner
colcon build --packages-select rl_planner
```

然后检查：

```bash
ls install/rl_planner/share/rl_planner/model/
# 应该看到 checkpoint.pth
```

### 机器人收到 `/way_point` 但不动

检查 `localPlanner` 是否订阅到了 `/way_point`：

```bash
ros2 topic info /way_point --verbose
```

应该有 `localPlanner` 作为 subscriber。如果没有，说明 source 顺序有问题，重新开终端完整 source 三个工作区。

---

## 9. ARiADNE 关键参数说明

这些参数在 `system_scout_hesai_with_ariadne.launch.py` 里通过 launch 参数暴露：

| 参数 | 默认值 | 含义 |
|---|---|---|
| `ariadneSensorRange` | 20.0 m | 感知半径，与 Hesai XT32 量程匹配 |
| `ariadneMapResolution` | 0.4 m | OccupancyGrid 每格大小，越小地图越精细但越慢 |
| `ariadneNodeResolution` | 2.0 m | 图节点间距，决定 waypoint 的粗细粒度 |
| `ariadneBaseFrame` | `sensor_at_scan` | octomap 的 base frame，用于 z 方向高度过滤 |
| `ariadnePublishGraph` | false | 是否在 RViz 里可视化规划图（开启会增加 CPU 开销） |

走廊实验建议：

- 窄走廊（<2m）可以把 `ariadneMapResolution` 降到 `0.2`，让地图更精细
- `ariadneNodeResolution` 保持 `2.0`，太小会让 waypoint 过于密集

---

## 10. 推荐一起看的文档

1. `docs_ly/run_guide.md` — 基础导航栈（FAST-LIO2 + localPlanner）运行指南，本文的上游依赖
2. `docs_ly/tare_integration_plan.md` — TARE 接入过程记录
3. `docs_ly/current_status_20260311.md` — 系统当前状态快照
