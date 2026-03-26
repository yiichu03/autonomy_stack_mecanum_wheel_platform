# Unity 仿真运行与参数调整指南

**平台**：Ubuntu 22.04 / ROS2 Humble / x86_64 笔记本（RTX 4060 Laptop 8GB）
**环境配置详见**：[setup_x86_simulation.md](setup_x86_simulation.md)

---

## 一、启动方式

### 三种仿真模式

| 模式 | 启动脚本 | 功能 | 交互方式 |
|------|---------|------|---------|
| 基础自主导航 | `./system_simulation.sh` | 避障 + waypoint 跟随 | RViz 点 `Waypoint` 按钮 |
| 路径规划 | `./system_simulation_with_route_planner.sh` | far_planner 全局路径 | RViz 点 `Goalpoint` 按钮 |
| 自主探索 | `./system_simulation_with_exploration_planner.sh` | TARE 自主覆盖探索 | RViz 点 `Resume Navigation to Goal` |

> **Goalpoint 按钮只在路径规划模式下有效**，基础模式里按无反应（far_planner 没启动）。

### 每次启动前

```bash
cd ~/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
export PATH=/usr/bin:/usr/local/bin:$PATH   # 防止 miniforge 干扰
source install/setup.bash
```

> Unity 首次启动需要 20-30 秒加载。如果 RViz 没有数据，关掉重启一次（已知偶发问题）。

### 探索模式小车不动？

`Resume Navigation to Goal` 按钮在 RViz 右侧 TeleopPanel 里，面板太窄时按钮被截掉。把分隔线往左拖宽即可。

或命令行触发（另开终端）：

```bash
source install/setup.bash
ros2 topic pub --once /joy sensor_msgs/msg/Joy \
  "{header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, \
    axes: [0.0, 0.0, -1.0, 0.0, 1.0, 1.0, 0.0, 0.0], \
    buttons: [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]}"
```

---

## 二、Unity 场景管理

### 当前场景

`office_building_2`（L 形多房间办公楼），解压在 `src/base_autonomy/vehicle_simulator/mesh/unity/environment/`。

### 可用场景（`env/unity_env_models/` 下）

| 文件名 | 布局 | 适合 |
|--------|------|------|
| `office_building_2.zip` | L 形多房间 ← **当前** | 室内走廊探索 |
| `office_building_1.zip` | 开放式大型办公大厅 | 大空间导航 |
| `home_building_1/2.zip` | 住宅楼 | 中等复杂度 |
| `office_1/2.zip`、各种 room | 单间 | 太小 |

### 换场景

```bash
UNITY_DIR=src/base_autonomy/vehicle_simulator/mesh/unity

# 1. 清掉当前场景
rm -rf $UNITY_DIR/environment $UNITY_DIR/map.ply $UNITY_DIR/map.jpg \
       $UNITY_DIR/render.jpg $UNITY_DIR/traversable_area.ply $UNITY_DIR/object_list.txt

# 2. 解压新场景（以 office_building_1 为例）
unzip -o env/unity_env_models/office_building_1.zip -d $UNITY_DIR/
cp -r $UNITY_DIR/office_building_1/* $UNITY_DIR/
rm -rf $UNITY_DIR/office_building_1

# 3. 给执行权限
chmod +x $UNITY_DIR/environment/Model.x86_64
```

zip 文件一直在 `env/` 里，随时可重新解压，不需要备份。

---

## 三、TARE 探索配置

### 配置文件

```
src/exploration_planner/tare_planner/config/
├── indoor_small.yaml         ← 默认，适合走廊
├── indoor_large.yaml         ← 大型室内空间
├── outdoor.yaml              ← 室外开阔地
├── original_indoor_small.yaml  ← 原版备份（不要改）
├── original_indoor_large.yaml
└── original_outdoor.yaml
```

默认配置：`indoor_small`（在 launch 文件中 `default_value='indoor_small'`）。

### 使用自定义配置

**方案 A：改 sh 脚本**

编辑 `system_simulation_with_exploration_planner.sh`，把 launch 行改为：

```bash
ros2 launch vehicle_simulator system_simulation_with_exploration_planner.launch \
  exploration_planner_config:=my_config &
```

**方案 B：手动三步启动**

```bash
# 终端 1
./src/base_autonomy/vehicle_simulator/mesh/unity/environment/Model.x86_64

# 终端 2
source install/setup.bash
ros2 launch vehicle_simulator system_simulation_with_exploration_planner.launch \
  exploration_planner_config:=my_config

# 终端 3
source install/setup.bash
ros2 run rviz2 rviz2 -d src/exploration_planner/tare_planner/rviz/tare_planner_ground.rviz
```

### 新建自定义配置

```bash
# 复制基础配置
cp src/exploration_planner/tare_planner/config/indoor_small.yaml \
   src/exploration_planner/tare_planner/config/my_config.yaml

# 建 symlink 让 ROS 找到（不需要重新编译）
ln -s $(pwd)/src/exploration_planner/tare_planner/config/my_config.yaml \
      install/tare_planner/share/tare_planner/my_config.yaml
```

---

## 四、关键参数速查

### TARE 参数（`config/indoor_small.yaml`）

| 参数 | 当前值 | 含义 | 调整方向 |
|------|--------|------|---------|
| `kSensorRange` | 3.0m | 探索时"能看多远"，决定 frontier 判断 | 走廊保持 3.0m |
| `viewpoint_manager/number_x/y` | 20×20 | viewpoint 网格数量（RViz 中绿色方块） | 调大→更细但更慢 |
| `viewpoint_manager/resolution_x/y` | 0.3m | viewpoint 间距 | 走廊用 0.3m |
| `keypose_graph/kAddNodeMinDist` | 0.3m | 路网节点间距 | 保持 0.3m |
| `kAddEdgeConnectDistThr` | 0.5m | 节点连边距离 | 保持 0.5m |
| `kExtendWayPointDistanceBig/Small` | 4.0/1.5m | waypoint 步长 | 窄走廊可缩小 |

### local_planner 参数（`local_planner/launch/local_planner.launch`）

| 参数 | 当前值 | 含义 | 调整建议 |
|------|--------|------|---------|
| `maxSpeed` | — | 最大速度 | 走廊 0.5-0.75 m/s |
| `autonomySpeed` | — | 自主导航速度 | 同上 |
| `obstacleHeightThre` | 0.05m | 障碍高度阈值 | 仿真 0.15；实机室内 0.015-0.02 |
| `pointPerPathThre` | 2 | 几个障碍点算路堵 | 建议 3 |
| `minPathRange` | 0.8m | 规划视野最小值 | 建议 1.2m |
| `pathRangeStep` | 0.6m | 视野缩小量 | 建议 0.3m |

> 修改 local_planner 参数后需要重新编译：`colcon build --packages-select local_planner --parallel-workers 1`

---

## 五、仿真 vs 实机

### 数据流对比

```
实机：Livox Mid-360 → livox_ros_driver2 → arise_slam(SLAM) → /odometry /lidar/scan
仿真：Unity → ROS-TCP-Endpoint(TCP:10000) → vehicle_simulator → /odometry /lidar/scan
```

仿真中 `vehicle_simulator` 直接从 Unity 获取完美位姿和理想点云，下游规划节点接口一致。

### 仿真能有效调的参数

- TARE 探索策略（`kSensorRange`、viewpoint 网格、keypose 图密度）
- FAR 路径规划（`robot_dim`、`sensor_range`）
- 导航速度（`maxSpeed`、`autonomySpeed`）

### 只能实机调的参数

| 参数 | 原因 |
|------|------|
| `obstacleHeightThre` | 仿真地面完美，无噪声 |
| SLAM 参数（`blindFront/Back/Left/Right`） | 仿真无雷达盲区 |
| 串口设备 `/dev/ttyACM0` | 仿真无电机控制器 |
| 车轮类型 `omniDir`/`standard` | 仿真运动模型固定 |

---

## 六、已知问题与经验

### 配置与场景不匹配

- **outdoor（kSensorRange=6m）在走廊**：起点就覆盖整个截面，TARE 立即 rush home
- **indoor_large（kAddEdgeConnectDistThr=3m）在走廊**：路网几个节点连通全图，只动 2-3m 就回来
- **结论：室内走廊必须用 `indoor_small`**

### 岔路口卡死

原因链：路口边缘被标为障碍 → local_planner path_range 缩到 0.9m → 无法规划 → TARE timeout → rush home。
核心问题是 `obstacleHeightThre` 过敏和 `minPathRange` 过低，不是 TARE 逻辑问题。

---

## 七、bag 文件回放

```
env/
├── cic_building_indoor.db3   （855MB，CMU CIC 楼室内走廊）
└── nsh_building_outdoor.db3  （566MB，CMU NSH 楼室外）
```

```bash
# 终端 1
./system_bagfile.sh

# 终端 2
source install/setup.bash
ros2 bag play env/cic_building_indoor.db3
```

---

## 八、编译注意事项

仿真编译跳过 SLAM 和雷达驱动：

```bash
export PATH=/usr/bin:/usr/local/bin:$PATH
source /opt/ros/humble/setup.bash
MAKEFLAGS="-j1" colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3 \
    --packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2 \
    --parallel-workers 1
```

- `--parallel-workers 1` + `MAKEFLAGS="-j1"`：防止编译时内存耗尽系统卡死
- `-DPython3_EXECUTABLE=/usr/bin/python3`：避免 miniforge Python 污染编译
- 详细踩坑记录见 [setup_x86_simulation.md](setup_x86_simulation.md)
