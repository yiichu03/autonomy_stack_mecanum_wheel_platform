# 项目状态汇总（供老师/其他 AI 审阅）

更新时间：2026-02-28  
项目目录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform`

## 1. 项目内容与目标

本项目希望在自有硬件平台上复现并跑通 `autonomy_stack_mecanum_wheel_platform` 的导航基线能力。  
目标硬件不是原仓库默认平台，而是：

1. 底盘：Agilex Scout Mini
2. 雷达：Hesai XT32
3. 算力平台：Jetson AGX Orin（Ubuntu 22.04）
4. 辅助 IMU 来源：RealSense D455（ROS 话题 `/camera/imu`）

目标能力分层：

1. 最小闭环：SLAM 输出 + 局部避障/局部导航 + 底盘执行
2. 增强能力：接入 FAR 全局规划
3. 后续能力：探索规划（TARE）

## 2. 当前已确认的关键事实

### 2.1 环境与依赖

1. 系统架构：`aarch64`
2. 系统版本：Ubuntu `22.04.5`
3. 已安装 ROS 包：`hesai_ros_driver`、`scout_base`、`scout_msgs`、`realsense2_camera`

### 2.2 传感器/底盘接口

1. Hesai 配置中开启了 IMU 发布（`send_imu_ros: true`），话题配置为 `/lidar_imu`
2. 实测结论：`/lidar_imu` 当前无有效数据，不能作为 LIO 输入
3. RealSense IMU 实测可用：
   ` /camera/imu` 约 `199.6 Hz`
   ` /camera/gyro/sample` 约 `199.6 Hz`
   ` /camera/accel/sample` 约 `100.8 Hz`
4. Scout 底盘驱动 `scout_base` 订阅 `geometry_msgs/Twist` 的 `/cmd_vel`

### 2.3 仓库架构约束

1. `pathFollower` 发布 `TwistStamped` 到 `/cmd_vel`
2. `realRobot=true` 时会走串口写入（原平台电机协议）
3. 实车 launch 默认启动 `livox_ros_driver2 + arise_slam_mid360`
4. `arise_slam_mid360` 编译期强依赖 `livox_ros_driver2`
5. `arise_slam_mid360` 的非 LIVOX 路径存在风险（IMU 初始化逻辑）
6. `tare_planner` 直接链接仓库内 `or-tools/lib/libortools.so`
7. 当前 `libortools.so` 是 `x86-64`，与 AGX Orin `aarch64` 不兼容

## 3. 当前进度

### 3.1 已完成

1. 代码与架构审计已完成，关键阻塞点已定位
2. 文档重构已完成：
   `jilu.md`（精简执行版）
   `jilu_raw_20260228.md`（原始记录备份）
3. 导航主体编译（跳过明显阻塞包）已完成  
   命令：`colcon build --packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2 tare_planner --symlink-install`  
   结果：`19 packages finished`，无阻塞错误
4. 新采集脚本已新增且不改原脚本：
   ` /home/rho/Documents/liuyi/run_collect3.sh`
   默认录制：`/lidar_points + /camera/imu`

### 3.2 未完成

1. **[前置] LiDAR-IMU 外参标定**：已从 `data_calibration.txt` 推算并填入 `hesai_xt32.yaml`；建议后续用 LI-Init 精标定验证
2. **[前置] IMU 噪声参数标定**：当前使用 BMI055 保守初始值；需录静止 bag 做 Allan 方差分析后替换
3. **[前置 ✓] FAST-LIO2 ROS2 工作空间**：已编译完成
4. **[前置 ✓] LiDAR+IMU 数据包**：`run_20260228_194305`（61s，LiDAR 10Hz / IMU 193Hz，数据完整）
5. **[当前] FAST-LIO2 离线 SLAM 验证**：在新 bag 上跑 FAST-LIO2，确认轨迹质量（见第 10 节命令速查）
6. **[前置] TF 树搭建**：写静态 TF launch，发布 `base_link → lidar_link → camera_link`；用 `view_frames` 确认完整
7. FAST-LIO2 话题 remap 到本栈接口（`/Odometry` → `/state_estimation`，`/cloud_registered` → `/registered_scan`）
8. base_autonomy 模块集成验证（不接底盘）
9. TwistStamped → Twist relay + 底盘接入
10. 上车联调与参数收敛

## 4. 当前处境（客观判断）

整体可行，且技术路径清晰，但仍处于“系统拼装前的关键准备阶段”。  
当前不适合直接上车跑全链路，原因：

1. SLAM 数据链路尚未闭环验证（新 bag 还没录完并离线跑通）
2. 控制链路类型不匹配（`TwistStamped` vs `Twist`）尚未桥接
3. 探索规划在 ARM 上有依赖阻塞（OR-Tools 架构不匹配）

## 5. 技术分析（核心决策）

### 5.1 SLAM路线

建议优先路线：先用 FAST-LIO2（或等效可用 LIO）作为外部 SLAM，输出对接本栈。  
不建议当前阶段硬改 `arise_slam_mid360`，因为其 Livox 耦合和非 LIVOX 风险会增加调试成本。

### 5.2 控制路线

本栈输出 `TwistStamped`，Scout 接收 `Twist`。  
建议先加轻量 relay（`TwistStamped -> Twist`），尽量不动原算法核心。

### 5.3 FAST-LIO2 接入的四个前置条件

在进入阶段 B 之前，以下四项必须完成，缺任何一项都会导致 SLAM 无法正常运行：

| 前置条件 | 风险说明 | 推荐做法 |
|---|---|---|
| LiDAR-IMU 外参 | 外参错误 → 定位漂移/崩溃，不会报错难以定位根因 | 先手工卷尺测量作初始值；精度要求高时用 LI-Init 自动标定 |
| IMU 噪声参数 | 参数偏差 → 建图漂移，难以与外参问题区分 | 录静止 bag 做 Allan 方差分析，得 D455 实测值 |
| FAST-LIO2 ROS2 版本 | ROS1 版本无法在 Humble 下编译 | 选用有 ROS2 branch 的 fork；确认 PointCloud2 字段兼容 |
| TF 树 | TF 缺失 → terrain_analysis/sensor_scan_generation 静默失败 | 写静态 TF launch，`view_frames` 确认后再集成 |

### 5.4 规划路线

1. 第一优先：局部导航闭环跑通
2. 第二优先：接入 FAR 全局规划
3. 探索规划（TARE）：延后，待 ARM64 OR-Tools 处理后再推进

## 6. 总计划（主线）

### 阶段 A：数据准备（立即）

1. 使用 `run_collect3.sh` 录制 `LiDAR + IMU` 新 bag
2. 用 `ros2 bag info` 确认消息数、持续时间、话题完整性
3. 产出一组可复现实验数据作为后续基准

### 阶段 A'：SLAM 前置条件（阶段 A 后立即做，阶段 B 的硬前提）

1. **外参测量**：用卷尺测量 D455 加速度计中心相对 XT32 坐标原点的 XYZ 偏移，旋转按安装角估算，记录到 FAST-LIO2 config
2. **IMU 噪声标定**：录一段 5 分钟以上完全静止的 bag（只含 `/camera/imu`），用 `imu_utils` 或 `allan_variance_ros` 分析，得到四个噪声参数
3. **FAST-LIO2 ROS2 版本选型**：拉取带 ROS2 支持的仓库 branch，完成 aarch64 编译，确认 Hesai `/lidar_points` 的 PointCloud2 字段（x/y/z/intensity）可被正常解析
4. **TF 树搭建**：写 `static_tf.launch.py`，发布 `base_link → lidar_link`、`base_link → camera_link（imu_link）`；用 `view_frames` 确认无断链

### 阶段 B：离线 SLAM 验证（当前阶段）

数据包就绪：`/home/rho/Documents/data/run_20260228_194305/rosbag`（见第 10 节运行命令）

1. 基于 bag 回放（`--clock`）运行 FAST-LIO2
2. 在 RViz 中确认：轨迹连续无跳变、点云注册稳定、无明显漂移
3. 检查输出话题 frame_id（应为 `camera_init`）
4. 固化首版参数截图作为基准

### 阶段 C：接口对接（不接底盘）

1. 将 FAST-LIO2 输出 remap 到：
   `/Odometry` → `/state_estimation`（注意 frame_id 需为 `map` 或与本栈一致）
   `/cloud_registered` → `/registered_scan`
2. 确认 TF 树完整（阶段 A' 产出）后再启动 base autonomy 子模块
3. 确保 `local_planner` 使用 `config=standard`、`realRobot=false`
4. 验证 `sensor_scan_generation`、`terrain_analysis`、`local_planner` 输出正常（RViz 观察）

### 阶段 D：接入底盘（低速安全）

1. 新增 `TwistStamped -> Twist` relay
2. 低速参数下进行实车闭环验证
3. 分模式验证（手动/半自动/waypoint）

### 阶段 E：增强功能

1. 接入 FAR 全局规划并验证
2. TARE 仅在 ARM 依赖修复后再推进

## 7. 最近执行计划（建议按此顺序）

### 第 1 步（立即）：FAST-LIO2 离线验证

运行命令见第 10 节 B 节。验收标准：
- RViz 里点云注册连续，轨迹无跳变
- `/Odometry` 和 `/cloud_registered` 以约 10Hz 正常发布
- 运行 61 秒后地图无大面积漂移

### 第 2 步（B 通过后）：TF 树 + 话题对接

1. 写 `static_tf.launch.py`（base_link → lidar_link/camera_link）
2. 写 FAST-LIO2 → autonomy_stack 的 remap launch（见第 10 节 C 节）
3. 启动 base_autonomy 模块（不接底盘），在 RViz 中确认 `terrain_analysis` 和 `local_planner` 输出

### 第 3 步（之后 2-4 天）：底盘接入

1. 写 TwistStamped → Twist relay 节点（5 行代码）
2. 低速实车闭环验证（先走直线，再走圆弧）
3. 第一次 waypoint 导航验证

## 8. 请老师/其他 AI 重点帮看

1. D455 IMU 作为主 IMU 的长期可行性与风险
2. LiDAR 与 RealSense IMU 的时间同步方案是否足够稳健
3. 当前外参和噪声参数是否合理，优先改哪些参数
4. `TwistStamped -> Twist` 桥接是否足够，还是建议直接改 `pathFollower`
5. FAR 接入时最容易踩的坐标系和话题 remap 错误点

## 9. 附：当前关键文件

1. 项目精简记录：`thermal_nav/autonomy_stack_mecanum_wheel_platform/jilu.md`
2. 本文档：`thermal_nav/autonomy_stack_mecanum_wheel_platform/project_status_20260228.md`
3. 采集脚本（LiDAR+IMU）：`~/Documents/liuyi/run_collect3.sh`
4. FAST-LIO2 工作空间：`thermal_nav/fastlio_ws/`
5. FAST-LIO2 Hesai 配置：`thermal_nav/fastlio_ws/src/FAST_LIO/config/hesai_xt32.yaml`
6. 基准数据包（LiDAR+IMU）：`~/Documents/data/run_20260228_194305/rosbag`
7. 外参标定原始数据：`thermal_nav/autonomy_stack_mecanum_wheel_platform/data_calibration.txt`
8. 阶段 0 编译日志：`thermal_nav/autonomy_stack_mecanum_wheel_platform/build_stage0.log`

---

## 10. 运行命令速查

> 以下所有命令均在 AGX Orin 上执行。每个"终端"需独立开启，不共享 shell 状态。

### A. 环境 source（每个终端都要先执行）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
```

---

### B. 阶段 B：FAST-LIO2 离线验证

**终端 1 — 启动 FAST-LIO2（含 RViz）：**
```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py \
  config_file:=hesai_xt32.yaml \
  use_sim_time:=true \
  rviz:=true
```

**终端 2 — 回放数据包：**
```bash
source /opt/ros/humble/setup.bash
ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
```

**终端 3 — 验证输出话题（运行时检查）：**
```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
# 检查输出频率（应约 10Hz）
ros2 topic hz /Odometry
ros2 topic hz /cloud_registered
# 检查坐标系（frame_id 应为 camera_init）
ros2 topic echo /Odometry --once | grep -E "frame_id|child_frame"
```

**FAST-LIO2 输出话题对照表：**

| FAST-LIO2 发布话题 | 消息类型 | 对接目标（autonomy_stack） |
|---|---|---|
| `/Odometry` | `nav_msgs/Odometry` | `/state_estimation` |
| `/cloud_registered` | `sensor_msgs/PointCloud2` | `/registered_scan` |
| `/path` | `nav_msgs/Path` | （仅 RViz 可视化，无需 remap） |

---

### C. 阶段 C：接口对接（不接底盘）

> 前提：阶段 B 验证通过，且 TF 树已搭建完毕

**话题 remap 方法（ros2 run 临时 remap）：**
```bash
# 将 FAST-LIO2 输出 remap 到 autonomy_stack 期望话题
ros2 run topic_tools relay /Odometry /state_estimation
ros2 run topic_tools relay /cloud_registered /registered_scan
```

**启动 autonomy_stack 核心模块（不接底盘，realRobot=false）：**
```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
# TODO: 新建 scout_hesai.launch（参考 system_real_robot.launch）
# 关键参数: realRobot:=false, vehicleType:=standard
```

---

### D. 阶段 D：底盘接入

**TwistStamped → Twist relay（临时方案）：**
```bash
# pathFollower 发布 /cmd_vel (TwistStamped)，scout_base 需要 Twist
# 用 topic_tools 做类型转换（需要自定义节点，topic_tools relay 无法做类型转换）
# TODO: 写 5 行 Python relay 节点
```

**IMU 噪声标定（待做，改善 SLAM 质量）：**
```bash
# 录 5 分钟静止 bag（只录 IMU）
ros2 bag record /camera/imu -o ~/Documents/data/imu_static_calib

# 之后用 imu_utils 或 allan_variance_ros 分析（需单独安装）
```

---

## 11. FAST-LIO2 源码修改记录

> 本节记录对 `hku-mars/FAST_LIO`（ROS2 branch）所做的全部修改，方便排查问题或回滚。
> 工作空间根目录：`~/Documents/liuyi/projects/thermal_nav/fastlio_ws/`

---

### 11.1 `livox_ros_driver2/CMakeLists.txt` — 替换为最小 stub

**文件路径**：`src/livox_ros_driver2/CMakeLists.txt`

**原因**：原版 `CMakeLists.txt` 需要 `liblivox_lidar_sdk_shared.so`（Livox 硬件 SDK），在本机不存在。
FAST-LIO2 只在编译期需要 `livox_ros_driver2::msg::CustomMsg` 的消息头文件，运行时（Hesai 路径）完全不调用 Livox 代码。

**做了什么**：把原 CMakeLists.txt（支持 ROS1/ROS2 双路径、含硬件 SDK 依赖）整体替换为只生成消息接口的最小版本，同时把 `package_ROS2.xml` 复制为 `package.xml`。

**关键内容**：
```cmake
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/CustomPoint.msg"
  "msg/CustomMsg.msg"
  DEPENDENCIES builtin_interfaces std_msgs
)
```

**如何验证**：`ros2 interface list | grep livox` 能看到 `livox_ros_driver2/msg/CustomMsg` 和 `CustomPoint`。

**如何回滚**：`cd src/livox_ros_driver2 && git checkout CMakeLists.txt`

---

### 11.2 `src/FAST_LIO/config/hesai_xt32.yaml` — 新增 Hesai XT32 配置文件

**文件路径**：`src/FAST_LIO/config/hesai_xt32.yaml`（新建，不影响原有 yaml）

**原因**：原仓库没有 Hesai 配置，需要新建。

**关键参数说明**：

| 参数 | 值 | 说明 |
|---|---|---|
| `lid_topic` | `/lidar_points` | Hesai 驱动默认话题 |
| `imu_topic` | `/camera/imu` | RealSense D455 IMU |
| `lidar_type` | `5` | Hesai 专用 handler（见 11.3） |
| `scan_line` | `32` | XT32 线数 |
| `scan_rate` | `10` | 10 Hz |
| `blind` | `0.5` | 最小有效距离（m） |
| `extrinsic_T` | `[0.003695, -0.061117, -0.067414]` | LiDAR 原点在 IMU 坐标系中的位置（m） |
| `extrinsic_R` | 见文件 | LiDAR→IMU 旋转矩阵（行优先） |
| `extrinsic_est_en` | `false` | 使用标定值，不做在线估计 |
| `acc_cov / gyr_cov` | `0.1 / 0.1` | BMI055 初始保守值，待 Allan 方差替换 |

**外参推算链路**：
```
data_calibration.txt
  lidar_T_camera  [x,y,z,qx,qy,qz,qw]   (direct_visual_lidar_calibration 工具)
+ color_T_accel   [R 3x3 | t 3x1]        (RealSense SDK 导出)
  ↓ lidar_T_imu = lidar_T_camera * color_T_accel
  ↓ 转换为 FAST-LIO2 约定 (p_imu = R * p_lidar + T)
  → extrinsic_R = R_li^T,  extrinsic_T = -R_li^T * t_li
```

---

### 11.3 `src/FAST_LIO/src/preprocess.h` — 添加 Hesai point struct 和 enum

**文件路径**：`src/FAST_LIO/src/preprocess.h`

**修改 1 — `LID_TYPE` 枚举新增 HESAI**

```cpp
// 修改前
enum LID_TYPE { AVIA = 1, VELO16, OUST64, MID360 };

// 修改后
enum LID_TYPE { AVIA = 1, VELO16, OUST64, MID360, HESAI };  // HESAI = 5
```

**修改 2 — 新增 `hesai_ros::Point` struct 及 PCL 注册**

在 `ouster_ros` 块之后、`livox_ros` 块之前插入：

```cpp
namespace hesai_ros
{
struct EIGEN_ALIGN16 Point
{
  PCL_ADD_POINT4D;
  float    intensity;
  uint16_t ring;
  double   timestamp;   // 绝对时间戳，单位：秒
  EIGEN_MAKE_ALIGNED_OPERATOR_NEW
};
}
POINT_CLOUD_REGISTER_POINT_STRUCT(hesai_ros::Point,
    (float,    x,         x)
    (float,    y,         y)
    (float,    z,         z)
    (float,    intensity, intensity)
    (uint16_t, ring,      ring)
    (double,   timestamp, timestamp))
```

**修改 3 — 在 `Preprocess` 类 private 区声明 `hesai_handler`**

```cpp
void hesai_handler(const sensor_msgs::msg::PointCloud2::UniquePtr &msg);
```

---

### 11.4 `src/FAST_LIO/src/preprocess.cpp` — 添加 hesai_handler 实现和 switch case

**修改 1 — `process()` 函数的 switch 新增 case**

```cpp
case HESAI:
    hesai_handler(msg);
    break;
```

**修改 2 — 新增 `hesai_handler` 函数实现**（插入在 `default_handler` 之前）

核心逻辑：
- 用 `hesai_ros::Point` 反序列化，PCL 直接匹配 `timestamp`（float64）和 `ring`（uint16）字段，无类型警告
- `given_offset_time = true`：以第一个点的绝对时间戳为基准，计算帧内相对时间
- `curvature = (timestamp - t0) * 1000.0`（ms，与其他 handler 单位一致）
- 过滤条件：`range < blind`、`ring >= N_SCANS`、`i % point_filter_num != 0`

**为什么这样做**：
原 `velodyne_handler` 期望字段名为 `time`（float32），而 Hesai XT32 发布的是 `timestamp`（float64，绝对秒）。PCL 找不到 `time` 字段时打印 `Failed to find match for field 'time'` 警告，并把 `time` 留 0，导致 `given_offset_time = false`，改由扫描频率估算相对时间，精度较低。新的 `hesai_handler` 直接读 `timestamp`，消除警告，同时获得真实的逐点时间戳，去畸变精度更高。

**如何验证**：运行后终端不再出现 `Failed to find match for field 'time'` 输出。

**如何回滚**：
```bash
cd ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/src/FAST_LIO
git diff src/preprocess.h src/preprocess.cpp   # 查看改动
git checkout src/preprocess.h src/preprocess.cpp  # 回滚
# 同时把 hesai_xt32.yaml 里的 lidar_type 改回 2
```

---

## 12. 项目结构与编译指南

### 12.1 目录结构

```
~/Documents/liuyi/projects/thermal_nav/
│
├── fastlio_ws/                          ← FAST-LIO2 独立 colcon 工作空间
│   ├── src/
│   │   ├── FAST_LIO/                   ← FAST-LIO2 主体（含我们的 Hesai 修改）
│   │   │   ├── config/hesai_xt32.yaml  ← 我们新建的 Hesai 配置文件
│   │   │   └── src/preprocess.{h,cpp}  ← 我们添加了 hesai_handler
│   │   └── livox_ros_driver2/          ← 消息接口 stub（无 Livox 硬件依赖）
│   └── install/                        ← 编译产物（需 source）
│
└── autonomy_stack_mecanum_wheel_platform/   ← 主导航栈 colcon 工作空间
    ├── src/base_autonomy/               ← 核心导航模块
    │   ├── sensor_scan_generation/     ← 时间同步：state+scan → /sensor_scan
    │   ├── terrain_analysis/           ← 地形分析 → /terrain_map
    │   ├── terrain_analysis_ext/       ← 扩展地形分析（障碍物连通性检查）
    │   ├── local_planner/              ← 局部规划 + pathFollower → /cmd_vel
    │   ├── vehicle_simulator/          ← 系统集成入口（launch 文件在此）
    │   │   ├── launch/system_scout_hesai.launch.py  ← 我们的主 launch 文件
    │   │   └── scripts/odom_frame_relay.py           ← 我们写的坐标系修正节点
    │   └── visualization_tools/        ← 可视化辅助节点
    ├── src/slam/arise_slam_mid360/     ← 跳过编译（Livox 硬依赖，不适用）
    ├── src/exploration_planner/tare_planner/  ← 跳过编译（OR-Tools x86，ARM 不兼容）
    └── install/                        ← 编译产物（需 source）
```

---

### 12.2 系统架构与数据流

```
传感器（实车）或 bag 回放
  /lidar_points  (Hesai XT32, 10 Hz)
  /camera/imu    (RealSense D455 IMU, ~193 Hz)
         │
         ▼
  ┌─────────────────────────────┐
  │  FAST-LIO2  (fastlio_ws)    │  LiDAR-Inertial 里程计 + 建图
  └─────────────────────────────┘
         │ remap /Odometry         → /state_estimation_raw
         │ remap /cloud_registered → /registered_scan
         ▼
  odom_frame_relay.py           ← 坐标系修正（D455 光学帧 → ROS 标准帧）
         │ 发布 /state_estimation  (Odometry, X=前 Y=左 Z=上)
         ▼
  sensor_scan_generation        ← 时间同步（state + scan → 同一时刻配对）
         │ 发布 /sensor_scan + /state_estimation_at_scan
         ▼
  terrain_analysis              ← 地形可通行性分析
         │ 发布 /terrain_map       (绿=可通行 红=障碍)
         ▼
  local_planner                 ← 局部路径规划
         │ 发布 /free_paths        (候选路径扇形，水平面)
         ▼
  pathFollower                  ← 路径跟踪
         │ 发布 /cmd_vel           (TwistStamped)
         ▼
  [待做] TwistStamped→Twist relay
         ▼
  scout_base                    ← 底盘驱动（接收 Twist）
```

**TF 树（当前配置）**：
```
map ──(identity,static)──▶ camera_init ──(FAST-LIO2,动态)──▶ body
                                                                │
                                                  (static,旋转修正 qxyzw=0.5,-0.5,0.5,0.5)
                                                                ▼
                                                             sensor
                                                            /       \
                                                 sensor→vehicle   sensor→camera
                                                 (local_planner)  (local_planner)
```

---

### 12.3 编译命令

> 所有编译均在对应工作空间根目录下执行。

#### FAST-LIO2 工作空间

```bash
cd ~/Documents/liuyi/projects/thermal_nav/fastlio_ws
colcon build --symlink-install
```

> `--symlink-install`：Python 脚本和 launch 文件以软链接安装，改完源文件无需重新编译。

#### 主导航栈（首次或全量编译）

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build \
  --packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2 tare_planner \
  --symlink-install
```

> 跳过原因：
> - `arise_slam_mid360` / `arise_slam_mid360_msgs`：强依赖 Livox 驱动，本项目不用
> - `livox_ros_driver2`：已在 fastlio_ws 中用 stub 替代
> - `tare_planner`：依赖 x86 专用 OR-Tools 二进制，aarch64 不兼容

#### 单包快速重编（最常用）

```bash
cd ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
colcon build --symlink-install --packages-select <包名>
```

| 修改了什么 | `--packages-select` 填什么 |
|---|---|
| `system_scout_hesai.launch.py` 或 `odom_frame_relay.py` | `vehicle_simulator` |
| `localPlanner.cpp` 或 `pathFollower.cpp` | `local_planner` |
| `terrainAnalysis.cpp` | `terrain_analysis` |
| `preprocess.cpp` 或 `preprocess.h` | 见下方 FAST-LIO2 命令 |

#### 重新编译 FAST-LIO2

```bash
cd ~/Documents/liuyi/projects/thermal_nav/fastlio_ws
colcon build --symlink-install --packages-select fast_lio
```

---

### 12.4 环境 source 顺序（每个终端都需要）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
```

> 顺序很重要：先 ROS2，再 fastlio_ws（提供 fast_lio 包），再 autonomy_stack（提供导航模块）。













