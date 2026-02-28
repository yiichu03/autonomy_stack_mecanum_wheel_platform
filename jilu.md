# jilu.md（2026-02-28 整理版）

原始长记录已备份到：`jilu_raw_20260228.md`。

## 1. 目标（当前一致）

目标是：在 **Agilex Scout Mini + Hesai XT32 + AGX Orin** 上，先跑通本仓库的导航基线最小闭环（定位/建图输出 + 局部导航 + 底盘控制），再考虑全局规划和探索规划。

## 2. 已核验的事实（基于本机文件与代码）

### 2.1 这套仓库本身的真实约束

1. 实车 launch 默认会启动 Livox 驱动和 `arise_slam_mid360`，并把 `local_planner` 设为 `realRobot=true`。  
证据：
- `src/base_autonomy/vehicle_simulator/launch/system_real_robot.launch:32`
- `src/base_autonomy/vehicle_simulator/launch/system_real_robot.launch:62`
- `src/base_autonomy/vehicle_simulator/launch/system_real_robot.launch:89`

2. `pathFollower` 对外发布的是 `geometry_msgs/TwistStamped` 到 `/cmd_vel`；`realRobot=true` 时会通过串口发送 3 个 float。  
证据：
- `src/base_autonomy/local_planner/src/pathFollower.cpp:302`
- `src/base_autonomy/local_planner/src/pathFollower.cpp:445`
- `src/base_autonomy/local_planner/src/pathFollower.cpp:455`

3. 默认轮式配置是 `omniDir`（麦克纳姆），不是 `standard`。  
证据：
- `src/base_autonomy/local_planner/launch/local_planner.launch:3`

4. `arise_slam_mid360` 编译期强依赖 `livox_ros_driver2`。  
证据：
- `src/slam/arise_slam_mid360/CMakeLists.txt:52`
- `src/slam/arise_slam_mid360/CMakeLists.txt:114`
- `src/slam/arise_slam_mid360/CMakeLists.txt:135`

5. `featureExtraction` 里 LIVOX 走 `livox_ros_driver2::msg::CustomMsg`；velodyne/ouster 走 `PointCloud2`。  
证据：
- `src/slam/arise_slam_mid360/src/FeatureExtraction/featureExtraction.cpp:69`
- `src/slam/arise_slam_mid360/src/FeatureExtraction/featureExtraction.cpp:74`

6. `imuPreintegration` 里 `imu_init_success` 默认是 `false`，初始化逻辑只在 `sensor == LIVOX` 分支设置为 `true`，否则会在后面 `return`。这意味着“非 LIVOX 直接套用”有明显风险。  
证据：
- `src/slam/arise_slam_mid360/include/arise_slam_mid360/ImuPreintegration/imuPreintegration.h:224`
- `src/slam/arise_slam_mid360/src/ImuPreintegration/imuPreintegration.cpp:872`
- `src/slam/arise_slam_mid360/src/ImuPreintegration/imuPreintegration.cpp:910`

7. `tare_planner` 当前直接链接仓库内 `or-tools/lib/libortools.so`，而本机该 so 是 `x86-64`，对 AGX Orin (`aarch64`) 不能直接用。  
证据：
- `src/exploration_planner/tare_planner/CMakeLists.txt:74`
- `file src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296`

8. README 明确要求仿真先下载 Unity 环境模型；本仓库当前没有该模型目录内容。  
证据：
- `README.md:35`
- `src/base_autonomy/vehicle_simulator/mesh/unity/environment` 当前不存在

### 2.2 你本机环境里可确认的信息

1. 当前系统是 `aarch64 + Ubuntu 22.04.5`。  
证据：`uname -m` 与 `/etc/os-release`

2. ROS2 包里存在：`hesai_ros_driver`、`scout_base`、`scout_msgs`、`realsense2_camera`。  
证据：`ros2 pkg list` 检索结果

3. Hesai 配置文件里设置为发布 `/lidar_points` 和 `/lidar_imu`，并且 `send_imu_ros: true`。  
证据：
- `/home/rho/Documents/hesai_ws/src/HesaiLidar_ROS_2.0/config/config.yaml:71`
- `/home/rho/Documents/hesai_ws/src/HesaiLidar_ROS_2.0/config/config.yaml:72`
- `/home/rho/Documents/hesai_ws/src/HesaiLidar_ROS_2.0/config/config.yaml:80`

4. 你已确认 `/lidar_imu` 实测无数据，因此当前不能依赖 XT32 的 IMU 通道。  
证据：用户实测结论（本轮补充信息）

5. `scout_base` 订阅的是 `geometry_msgs::msg::Twist` 的 `/cmd_vel`。  
证据：
- `/home/rho/Documents/ros_ws/src/scout_ros2/scout_base/include/scout_base/scout_messenger.hpp:52`
- `/home/rho/Documents/ros_ws/src/scout_ros2/scout_base/include/scout_base/scout_messenger.hpp:53`

6. `run_collect.sh` 与 `run_collect2.sh` 的 rosbag 目前都只录 `/lidar_points`。  
证据：
- `/home/rho/Documents/liuyi/run_collect.sh:65`
- `/home/rho/Documents/liuyi/run_collect2.sh:76`
- `/home/rho/Documents/data/run_20260228_152315/rosbag/metadata.yaml:11`

## 3. 原记录里“不一定正确/需要降级为待验证”的内容

1. “XT32 内置 IMU 一定可用，且可直接用于 SLAM”。  
当前判断：**不成立（就当前实测）**。你已确认 `/lidar_imu` 无数据，当前必须切换到其他 IMU 来源（例如 RealSense IMU）。

2. “历史 rosbag 可直接离线验证 FAST-LIO2”。  
当前判断：**大概率不成立（就目前脚本与样本 bag 而言）**。你当前 bag 只有 `/lidar_points`，没有 `/lidar_imu`，而 LIO 需要 IMU。

3. “只改 `realRobot=false` + relay 就能接 Scout”。  
当前判断：**不完整**。因为系统实车入口 launch 默认把 `realRobot` 传成 `true`，你还需要改 launch 链路（或新建 Scout 专用 launch）。

4. “探索规划（tare_planner）之后再说，当前不影响”。  
当前判断：**成立**。在你当前目标里应先跳过，因为 OR-Tools 架构不匹配是硬阻塞。

5. “可直接在当前仓库内按 README 跑仿真验证”。  
当前判断：**当前本地不成立**。Unity 环境模型文件未就绪。

6. “Scout Mini 车体尺寸固定为 0.93 x 0.57”。  
当前判断：**待验证**。这个值在当前仓库和你本机文件里没有权威来源，建议以实测/官方参数为准。

7. “雷达现在没上电/ARP incomplete”等网络连通结论。  
当前判断：**时效性很强，不能写成长期事实**。只能作为当时一次检查结果。

## 4. 我的判断（可行性）

1. 这个基线在你硬件上 **可行**，但不是“直接编译即跑”。
2. 你真正的工程主线应该是：
- 先满足接口契约：`/state_estimation` + `/registered_scan` + 底盘可消费的 `/cmd_vel(Twist)`
- 再决定 SLAM 路线（建议先外置可用 LIO，而不是先修 `arise_slam_mid360`）
3. 第一阶段不该把探索规划（tare）纳入目标。

## 5. 后续计划（我建议按这个执行）

### 阶段 A：先把“可编译 + 可集成骨架”跑通（今天可做）

1. 先编译主体，跳过明显阻塞包：
```bash
cd /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2 tare_planner
```

2. 在本仓库新增一个“Scout + Hesai 集成 launch”（不要改原始 `system_real_robot.launch`）：
- `local_planner` 用 `config=standard`
- `realRobot=false`（先禁串口）
- 接入 Scout 驱动（或由外部已启动）
- 预留 `/state_estimation`、`/registered_scan` 的输入

3. 新增 `TwistStamped -> Twist` relay 节点（用于 `pathFollower` 到 `scout_base`）。

### 阶段 B：基于“XT32 IMU无数据”做接入（上车前最关键）

1. 启动 RealSense IMU 并确认有稳定数据（例如 `/camera/imu` 或你的实际 IMU 话题名）。

2. 重录一段可离线复现实验 bag，至少包含：
- `/lidar_points`
- `RealSense IMU 话题`（如 `/camera/imu`）
- （可选）`/scout_status`、`/odom`

3. 修改采集脚本，把 IMU 话题加入 `ros2 bag record`，避免后续离线 SLAM 反复返工。

### 阶段 C：SLAM 路线决策

1. 推荐路线（低风险）：外接可用 LIO，输出 remap 到：
- `/state_estimation`
- `/registered_scan`

2. 备选路线（高风险）：继续修 `arise_slam_mid360` 的非 LIVOX 路径。

### 阶段 D：联调顺序

1. 只跑 SLAM + RViz（不接底盘）
2. 接 `sensor_scan_generation + terrain_analysis`
3. 接 `local_planner`，只看 `/cmd_vel` 输出
4. 接 relay + Scout 底盘低速实跑
5. 最后再加 `far_planner`

## 6. 你下一步应该先做什么（只做一件事）

**先改采集脚本并录一段“`/lidar_points + RealSense IMU`”的新 bag。**

原因：你已经确认 `/lidar_imu` 无数据；现在最关键是把可用 IMU 数据链路固定下来，尽快具备离线/在线 SLAM 可复现输入。
