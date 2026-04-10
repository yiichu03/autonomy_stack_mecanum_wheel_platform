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
source ~/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```

> octomap_ws 和 ARiADNE 只有 ARiADNE 模式需要，但多 source 不影响。统一五行省心。
> `autonomy_stack` 必须最后 source。

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
```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```
先 source 五行环境（见 3.2 节），然后选一个 launch：

#### 方案一：只跑 Base Autonomy

```bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py
```

#### 方案二：接 far_planner（人工指定目标点）

默认是 outdoor.yaml

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_far_planner.launch.py
```

#### 方案三：接 TARE（自主探索，无需指定目标点）

启动后机器人自动开始探索，无需在 RViz 中点击目标。

```bash
# 小房间（默认 indoor_small.yaml）
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py

# 窄走廊 <2m
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=corridor_v2.yaml maxSpeed:=0.3

# 中等走廊 2-3m
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=corridor_medium.yaml

# 大房间
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=indoor_large.yaml

# 室外
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py tareConfig:=outdoor.yaml
```

#### 方案四：接 ARiADNE（DRL 自主探索）

启动后机器人自动开始探索，行为偏激进。使用专属 rviz 配置（含 `/projected_map`、`/frontier`、`/node`、`/edge`）。

**场景一：杂乱办公室 / 有窄门（门宽 < 1m）**

默认 resolution=0.4m 时，0.8m 的门只有 2 个 cell，一个噪声点就会堵死通道。必须调小。
```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=10.0 \
  ariadneNodeResolution:=1.0 \
  maxSpeed:=0.3 \
  ariadnePublishGraph:=true
```

- `resolution 0.2` — 门会被分成更多 cell，噪声更难一次性堵死通道
- `sensorRange 10.0` — 办公室小，20m 浪费算力在墙上
- `nodeResolution 1.0` — 小房间需要更密的图节点覆盖
- `maxSpeed 0.3` — 桌椅间安全低速

**场景二：走廊（宽 1.5–3m，长直线段）**

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=15.0 \
  ariadneNodeResolution:=1.5 \
  maxSpeed:=0.5
```

- `resolution 0.2` — 走廊比门宽，0.2 在精度和速度间平衡
- `sensorRange 15.0` — 走廊长但不需要 20m 那么远
- `nodeResolution 1.5` — 走廊不需要特别密的图，但 2.0 可能跳过分支入口

**场景三：长走廊 + 岔路口（走一段就停、没有继续去探岔路）**

先给一组推荐基准组。它对应的是“主走廊能走，但到岔路口前 utility 提前掉光，或者 waypoint 还没真到就被判到达”的情况。

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=10.0 \
  ariadneNodeResolution:=1.0 \
  ariadneUtilityRangeFactor:=0.5 \
  ariadneMinUtility:=2 \
  ariadneWaypointThreshold:=1.0 \
  ariadneOctomapHit:=0.7 \
  ariadneOctomapMiss:=0.4 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

- `ariadneMapResolution 0.2` — 先保证岔路入口在 `/projected_map` 里足够清楚
- `ariadneSensorRange 10.0` — 不让 planner 在长走廊里过早把太远区域一起算进去
- `ariadneNodeResolution 1.0` — 让图节点在岔路口附近更密，不容易“跨过去”
- `ariadneMinUtility 2` — 降低“这个方向没价值了”的门槛，岔路口少量 frontier 也能保留下来
- `ariadneWaypointThreshold 1.0` — 避免离 waypoint 还有一段距离时就被提前判成“到了”
- `ariadneOctomapHit 0.7` + `ariadneOctomapMiss 0.4` — 降低单次噪声把路口边缘直接打成障碍的概率
- `ariadnePublishGraph true` — 方便直接在 RViz 看 `/frontier`、`/node`、`/edge` 到底是哪里先断掉

下面再给 4 组可直接复制的实验参数。建议按 `A -> B -> C -> D` 的顺序试，并把“有没有继续往岔路口走、`/frontier` 有没有提前消失、`/way_point` 有没有提前切换”简单记一下。

**A 组：平衡版**

适合“走廊比较长，但不想一下把 sensor range 拉得太大”。

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=15.0 \
  ariadneNodeResolution:=1.0 \
  ariadneUtilityRangeFactor:=0.45 \
  ariadneMinUtility:=2 \
  ariadneWaypointThreshold:=1.0 \
  ariadneOctomapHit:=0.7 \
  ariadneOctomapMiss:=0.4 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

- 特点：通常是长走廊里最稳妥的第一候选，既不会太近视，也不容易把近处分支淹没

**B 组：长走廊标准版**

适合“走廊已经明显偏长，希望往前看得更远一点，但还是先保持比较稳的 node 密度”。

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=20.0 \
  ariadneNodeResolution:=1.0 \
  ariadneUtilityRangeFactor:=0.4 \
  ariadneMinUtility:=2 \
  ariadneWaypointThreshold:=1.0 \
  ariadneOctomapHit:=0.7 \
  ariadneOctomapMiss:=0.4 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

- 特点：比 A 组更适合长直走廊，但还没有把 sensor range 拉到 25/30 那么激进

**C 组：长走廊远距版**

适合“走廊确实很长，想让 planner 提前看到更远，但又不想让 utility 半径跟着膨胀得太厉害”。

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=25.0 \
  ariadneNodeResolution:=1.2 \
  ariadneUtilityRangeFactor:=0.35 \
  ariadneMinUtility:=2 \
  ariadneWaypointThreshold:=1.0 \
  ariadneOctomapHit:=0.65 \
  ariadneOctomapMiss:=0.4 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

- 特点：给你想试的 `sensorRange 25`，但把 `utilityRangeFactor` 一起压低，避免“看得远了，但 utility 也摊得太开”

**D 组：超长走廊试验版**

适合“走廊非常长，确实想试 `sensorRange 30` 的效果”，但这组更偏实验性质。

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=30.0 \
  ariadneNodeResolution:=1.2 \
  ariadneUtilityRangeFactor:=0.3 \
  ariadneMinUtility:=2 \
  ariadneWaypointThreshold:=1.0 \
  ariadneOctomapHit:=0.65 \
  ariadneOctomapMiss:=0.4 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

- 特点：给你 `sensorRange 30` 的版本，但为了防止太远 frontier 把近处分支淹没，`utilityRangeFactor` 要压得更低

这 4 组里，几个核心变化可以这样理解：

- `ariadneMapResolution 0.2`：先固定住，优先保证岔路入口在 `/projected_map` 里足够清楚
- `ariadneSensorRange 15 / 20 / 25 / 30`：按“看多远”的强度逐步拉高
- `ariadneNodeResolution 1.0 / 1.2`：让图节点在岔路口附近保持足够密，不容易“跨过去”
- `ariadneUtilityRangeFactor 0.45 / 0.4 / 0.35 / 0.3`：sensor range 越大，这个值就越要往下压，否则 utility 会摊得太开
- `ariadneMinUtility 2`：降低“这个方向没价值了”的门槛，岔路口少量 frontier 也能保留下来
- `ariadneWaypointThreshold 1.0`：避免离 waypoint 还有一段距离时就被提前判成“到了”
- `ariadneOctomapHit 0.7 / 0.65` + `ariadneOctomapMiss 0.4`：降低单次噪声把路口边缘直接打成障碍的概率
- `ariadnePublishGraph true`：方便直接在 RViz 看 `/frontier`、`/node`、`/edge` 到底是哪里先断掉

**场景四：开阔大房间 / 仓库**

默认参数即可，可选增大感知范围：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneSensorRange:=25.0 \
  maxSpeed:=0.5
```

**调试模式：开启图可视化**

加 `ariadnePublishGraph:=true` 在 RViz 中显示 `/node`、`/edge`、`/frontier`，方便排查 DRL 决策：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.15 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

ARiADNE 关键参数：

| 参数 | 默认值 | 含义 | 调小效果 | 调大效果 |
|---|---|---|---|---|
| `ariadneMapResolution` | 0.4 m | 同时传给 octomap 和 `rl_planner` 的 `map_resolution`。它决定 `/projected_map` 每个 cell 多大，也决定 frontier 提取、碰撞检查是在多细的栅格上进行。 | 地图更细，门口/岔路边缘更容易被保留下来，但计算量更高，对噪声也更敏感。 | 地图更粗，建图和推理更快，但窄通道、岔路入口更容易被糊掉。 |
| `ariadneSensorRange` | 20.0 m | 同时传给 octomap 的 `sensor_model.max_range` 和 `rl_planner` 的 `sensor_range`。它不只是“看多远”，还会影响 utility 统计半径和局部更新地图范围。 | 更聚焦近处，走廊里不容易把太远的未知区一起算进来。 | 看得更远、更新范围更大，适合开阔场景，但走廊里更容易让 utility 分布变钝。 |
| `ariadneNodeResolution` | 2.0 m | 规划图 node 的采样间距。ARiADNE 不是直接在每个 cell 上决策，而是在这些 graph node 上做 frontier utility 统计和下一步选择。 | 图更密，岔路口附近更容易保留分支选择，但 node 数会明显增加。 | 图更稀，速度更快，但可能“一步跨过”分支入口，或者让可选动作太少。 |
| `ariadneUtilityRangeFactor` | 0.5 | node 的有效 utility 半径比例，实际 `utility_range = factor * sensorRange`。也就是“一个 node 会去统计多大一圈 frontier 作为自己的收益”。 | node 只关心更近的 frontier，局部性更强，适合狭窄环境。 | node 会把更远的 frontier 也算进 utility，开阔场景更稳，但走廊里容易把近处分支淹没。 |
| `ariadneMinUtility` | 3 | node 看到的 frontier 数量低于这个阈值时，utility 会被直接清零。它本质上是在过滤“价值太小的方向”。 | 更容易保留弱 frontier，岔路口少量 frontier 也可能继续被探索。 | 过滤更激进，只有 frontier 很明显的方向才会留下来。 |
| `ariadneWaypointThreshold` | 2.0 m | 当前 waypoint 的到达判定半径。机器人一旦进入这个半径，planner 就会认为“这个 waypoint 已经完成”，转去下一个。 | 必须更靠近 waypoint 才算到达，行为更谨慎，也更利于观察是否真的走进岔路。 | 更早判定“到达”，在走廊里可能出现还没走到 node 就切换目标。 |
| `ariadneOctomapHit` | 1.0 | octomap 障碍命中更新强度。单次观测会把 cell 往“occupied”方向推多狠。 | 更不容易被单帧噪声堵死路口边缘，但障碍收敛更慢。 | 更容易快速形成障碍边界，但岔路口、窄门边缘也更容易被误封。 |
| `ariadneOctomapMiss` | 0.45 | octomap 空闲更新强度。和 `ariadneOctomapHit` 配合，决定 free / occupied 收敛速度平衡。 | 空闲区被确认得更慢，图会更保守。 | 空闲区被清得更快，但如果传感器质量一般，边缘会更跳。 |
| `ariadnePublishGraph` | false | 是否持续发布 `/frontier`、`/node`、`/edge`。它不改变决策逻辑，只影响调试可见性。 | 关闭后更省资源，但你看不到图是哪里断掉的。 | 开启后更方便排查 frontier / node / edge 是否正常扩展。 |
| `maxSpeed` | 0.5 m/s | 下游 `localPlanner / pathFollower` 的速度上限，不直接改变 ARiADNE 的 frontier 选择逻辑。 | 更安全，更容易观察 planner 行为。 | 更快，但在狭窄环境里更容易因为跟踪误差掩盖 planner 本身的问题。 |

如果你是在分析“为什么长走廊里没有继续去探岔路口”，最值得优先关注的通常是这 4 个：

| 参数 | 优先看它的原因 | 常见现象 |
|---|---|---|
| `ariadneNodeResolution` | 直接决定岔路口附近有没有足够密的 graph node | 图太稀，`/node` 在岔路口附近断开或跳过去 |
| `ariadneWaypointThreshold` | 直接决定 waypoint 会不会被过早判定到达 | 车还没真正走到分支前，`/way_point` 就提前切换 |
| `ariadneMinUtility` | 直接决定弱 frontier 会不会被当成“没价值”过滤掉 | `/frontier` 还有一点，但 node utility 已经掉光 |
| `ariadneOctomapHit` | 直接决定岔路口边缘会不会被噪声快速堵死 | `/projected_map` 里分支入口很快长出一堵“假墙” |

> 注意：方案二、三、四互斥，都会发布 `/way_point`，不能同时运行。

### TARE / ARiADNE 参数速查

#### TARE：命令行里最常改的是 `tareConfig` 和 `maxSpeed`

TARE 这条命令真正暴露在 launch 外层的，主要就是场景配置和速度上限：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py \
  tareConfig:=corridor_v2.yaml \
  maxSpeed:=0.3
```

- `tareConfig`：选择一整套探索策略预设。它决定的不是单一阈值，而是一组 frontier、viewpoint、碰撞余量、waypoint 步长参数。
- `maxSpeed`：只影响下游 `localPlanner / pathFollower` 的速度上限，不直接改变 TARE 怎么选 frontier。

当前最常用的几套 TARE 配置，可以先这样理解：

| 配置 | 适用场景 | 直观含义 |
|---|---|---|
| `indoor_small.yaml` | 小房间 | 感知近、viewpoint 密、动作偏细 |
| `corridor_v2.yaml` | 窄走廊 `<2m` | waypoint 更短、碰撞余量更小，更容易在走廊里继续往前 |
| `corridor_medium.yaml` | 中等走廊 `2-3m` | 比 `indoor_small` 看得更远，适合稍宽一些的长走廊 |
| `indoor_large.yaml` | 大房间 | waypoint 步长更长，适合开阔室内 |
| `outdoor.yaml` | 室外 | 栅格更粗、感知更远、探索步子更大 |

如果需要自己微调，真正影响 TARE 行为的通常是下面几类参数，它们都在 `src/exploration_planner/tare_planner/config/*.yaml`：

| 参数 | 作用 | 调小效果 | 调大效果 |
|---|---|---|---|
| `kSensorRange` | TARE 判断“当前能覆盖多远”的范围 | 更关注近处，适合小房间/窄走廊 | 更激进地看远处，适合开阔场景 |
| `viewpoint_manager/resolution_x/y` | 候选 viewpoint 间距 | viewpoint 更密，更容易看清窄通道，但更慢 | viewpoint 更稀，算得更快，但可能漏掉细分支 |
| `rolling_occupancy_grid/resolution_x/y` | TARE 自己局部占据栅格的分辨率 | 更细，障碍形状更准确，但更耗算力 | 更粗，更快，但走廊边缘更容易被糊掉 |
| `kExtendWayPointDistanceBig/Small` | TARE 给出去的 waypoint 步长 | 目标点更近，转弯和路口更保守 | 目标点更远，走得更猛，但更容易跨过岔路口 |
| `kViewPointCollisionMargin` | viewpoint 离障碍物的安全余量 | 更敢贴边走，适合窄走廊 | 更保守，适合开阔环境 |

#### ARiADNE：最常先看的就是这四个 launch 参数

以走廊命令为例：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=15.0 \
  ariadneNodeResolution:=1.5 \
  maxSpeed:=0.5
```

- `ariadneMapResolution:=0.2`
  这是 `/projected_map` 每个格子的边长。`0.2m` 表示 2m 宽走廊会被分成大约 10 个格子，足够看清墙边和门口。
- `ariadneSensorRange:=15.0`
  这个值会同时影响 octomap 的最大射线长度和 `rl_planner` 认为“自己能看到多远”的范围。走廊里设成 `15.0` 往往已经够用了，没必要拉到 `100.0`。
- `ariadneNodeResolution:=1.5`
  这是 ARiADNE 规划图里节点的大致间距。`1.5m` 表示节点不会太稀，也不会像 `1.0m` 那样在长走廊里生成过多节点。
- `maxSpeed:=0.5`
  这是车最终执行时的速度上限，属于控制层参数，不影响 frontier 是怎么被找出来的。

另外一个很重要但只在调试时建议开的参数是：

- `ariadnePublishGraph:=true`
  打开后才会持续发布 `/frontier`、`/node`、`/edge`，方便在 RViz 里直接看 DRL 当前的探索图结构。

如果症状是“走廊里先走一小段，然后停住，不继续往岔路口去”，再加看这 4 个补充参数：

- `ariadneUtilityRangeFactor`
  它决定 node 看多大一圈 frontier 才算自己的 utility。当前建议先保持 `0.5`，不要盲目拉大。
- `ariadneMinUtility`
  它决定“frontier 少到什么程度就当没价值”。走廊岔路口建议先从 `2` 开始试。
- `ariadneWaypointThreshold`
  它决定离 waypoint 多近就算“到达”。当前默认 `2.0` 偏大，走廊里建议先试 `1.0`。
- `ariadneOctomapHit`
  它决定 octomap 单次命中有多激进。当前默认 `1.0` 很容易把边缘噪声直接记成障碍，走廊岔路口建议先试 `0.7`。

### 验证 TARE 是否正常工作

```bash
ros2 node list | grep tare           # 应输出 tare_planner_node
ros2 topic echo /way_point           # 启动后数秒内应持续更新
```

若无输出，检查 `tare_planner_node` 终端日志。

### 验证 ARiADNE 是否正常工作

按顺序检查，任何一步失败先排查再往下：

```bash
# 1. 上游数据是否到位
ros2 topic hz /state_estimation      # 期望 ~10 Hz（FAST-LIO2）
ros2 topic hz /sensor_scan           # 期望 ~10 Hz（sensor_scan_generation）
ros2 topic hz /projected_map         # 期望 ~1-2 Hz（octomap_server）

# 2. rl_planner 是否初始化（终端 E 应显示 "initialize robot location at [x, y]"）
ros2 node list | grep rl_planner     # 应输出 /rl_planner

# 3. 是否在产生 waypoint
ros2 topic echo /way_point           # 应持续更新

# 4. 探索图是否在扩展（需 ariadnePublishGraph:=true）
ros2 topic echo /frontier --no-arr | head -5    # frontier = 未探索边界
ros2 topic echo /node --no-arr | head -5        # 图节点

# 5. 推理速度
ros2 topic echo /runtime             # 每步应 < 0.5s

# 6. 探索是否完成
ros2 topic echo /exploration_finish   # data: false = 还在探索, true = 完成

# 7. 下游是否响应
ros2 topic echo /cmd_vel             # 有 way_point 后应有非零输出
```

**常见问题：**

- `/projected_map` 没数据 → 检查 `/sensor_scan` 有无输出，再检查 TF：`ros2 run tf2_ros tf2_echo map sensor_at_scan`
- `rl_planner` 一直显示 "Waiting for map and location data..." → `/projected_map` 或 `/state_estimation` 没数据
- `rl_planner` 崩溃 ImportError → `pip3 install scikit-image`；torch 缺失见 `run_guide_ariadne.md` 第 3.2 节

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

### 5.3 ARiADNE 模式

ARiADNE launch 使用专属 rviz 配置 `vehicle_simulator_ariadne.rviz`，自动加载。

RViz 里会看到两个 Group：

**Navigation 组**（和其他模式共用）：

1. `/registered_scan` — 白色累积点云
2. `/terrain_map` — 地形分类（由 `terrain_analysis` 节点发布）
3. `/path` — 绿色路径线（localPlanner）
4. `/free_paths` — 蓝色可通行路径
5. `/way_point` — 紫色球（当前目标点）

**ARiADNE 组**（DRL 特有）：

1. `/projected_map` — 2D 占用格栅（灰色底图，由 octomap_server 发布）
2. `/frontier` — 红色方块，未探索边界
3. `/node` — 彩色球体，规划图节点（需 `ariadnePublishGraph:=true`）
4. `/edge` — 图节点间的边（需 `ariadnePublishGraph:=true`）
5. `/occupied_cells_vis_array` — 3D octomap 体素（默认关闭，开启较耗资源）

**怎么判断 ARiADNE 在正常工作：**

- `/projected_map` 底图持续扩大 → octomap 正常建图
- `/frontier` 红块在地图边缘出现又消失 → 正在探索新区域
- `/way_point` 紫球不断跳到新位置 → DRL 在选择下一个探索目标
- 所有 frontier 消失 + `/exploration_finish` 为 true → 探索完成

### 5.4 车停在走廊里时，RViz 重点看什么

如果你想靠 RViz 排查“为什么停住了”，ARiADNE 模式建议直接这样启动：

```bash
ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.2 \
  ariadneSensorRange:=15.0 \
  ariadneNodeResolution:=1.5 \
  ariadnePublishGraph:=true \
  maxSpeed:=0.3
```

然后在左侧 Displays 里，优先确认这些显示项是打开的：

1. `ProjectedMap`
2. `Frontier`
3. `Node`
4. `Edge`
5. `Waypoint`
6. `Path`
7. `FreePaths`

常见现象可以这样判断：

- `ProjectedMap` 只在起点附近有一小块，或者几乎不扩展 → 先查上游 `/sensor_scan`、`/projected_map` 和 TF，不要先怀疑 DRL。
- `Frontier` 明明还很多，但 `Node / Edge` 很稀或者断开 → 通常是 `ariadneNodeResolution` 偏大，图跨不过走廊分支或门口。
- `Frontier` 很少甚至提前消失，但前面明明还没探索完 → 可能是 `ariadneSensorRange` 偏大，或者 `ariadneMapResolution` 偏粗，把未知区域过早“吃掉”了。
- `Waypoint` 在跳，但 `Path / FreePaths` 不跟着更新 → 更像是下游 `localPlanner` 没接住，不是 ARiADNE 没找到 frontier。
- `Waypoint` 长时间不动，同时 `/runtime` 很高 → 当前图太细、计算太慢，可以先适当调大 `ariadneMapResolution`，或者调试完后关掉 `ariadnePublishGraph`。
- `OctomapVoxels` 默认是关的；只有当你怀疑 3D 障碍体素把通道堵死时，再手动打开它看。

#### TARE 想看得更深时怎么办

当前 `system_scout_hesai_with_tare.launch.py` 自动打开的是通用 `vehicle_simulator.rviz`，它已经足够看 `/terrain_map`、`/free_paths`、`/path`、`/way_point`。

如果你想继续看 TARE 自己的 frontier / viewpoint / 局部规划范围，建议额外开一个 RViz：

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
source install/setup.bash
ros2 run rviz2 rviz2 -d src/exploration_planner/tare_planner/rviz/tare_planner_ground.rviz
```

这个专用 RViz 里最值得看的几项是：

1. `FrontierSurfacesToCover`：还没覆盖到的 frontier，红色点云
2. `SelectedViewPoints`：当前被 TARE 选中的 viewpoint
3. `GlobalPath`：TARE 输出的全局探索路径
4. `LocalPlanningHorizon`：当前局部规划窗口
5. `Waypoint`、`FreePaths`、`Path`：和下游导航链路是否接住目标点直接相关

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



sudo ip link set can2 up type can bitrate 500000
candump can2
ros2 launch scout_base scout_mini_base.launch.py port_name:=can2


sudo ip link set can0 up type can bitrate 500000
candump can0
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


# RVIZ
2. 红色小方块 /frontier

红块表示“已知自由区”和“未知区”的边界，也就是探索候选边界。
哪儿红块多，说明那边还有未探索空间。
如果岔路口附近红块一直存在，但车不去，问题更像 planner/utility/graph。
如果岔路口附近根本没有红块，问题更像地图层已经把那里看成探索完或堵住了。rl_planner.py (line 405) rviz.rviz (line 186)

3. 彩色球 /node

这些球是 ARiADNE 稀疏规划图里的 key nodes。
每个球的位置是一个关键图节点的位置。
每个球的颜色来自该节点的 utility，发布时塞进 PointCloud2 的 intensity 字段，RViz 再按 Intensity 模式映射成彩虹色。rl_planner.py (line 390) rviz.rviz (line 133)
怎么理解颜色：

暖色/亮色球：utility 高，这个节点附近还能看到比较多 frontier，探索价值高。
冷色/暗色球：utility 低，说明这个点附近可带来的新探索收益少。
如果一大片节点颜色都偏冷，而且岔路口附近也没有亮色球，planner 很容易停，因为它会觉得“没什么值得去的了”。
代码里如果节点能看到的 frontier 数量小于等于 min_utility，这个节点 utility 会直接被清零。node_manager.py (line 593)
你图里那个现象其实很关键：

右上那片球颜色更偏黄绿橙，说明那边在当前时刻“还有探索收益”。
左下和中下很多球偏蓝紫，说明那些区域大多已经探索过，收益低。
如果你的岔路口附近只有蓝紫球，没有新的黄橙球，通常不是策略“没学会”，而是它当前图上确实没看到足够 frontier。
