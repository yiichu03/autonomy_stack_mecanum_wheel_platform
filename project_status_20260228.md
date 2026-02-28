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

1. FAST-LIO2 工作空间搭建与编译
2. 新数据包（含 IMU）采集与离线 SLAM 验证
3. FAST-LIO2 到本栈话题接口对接（`/state_estimation`、`/registered_scan`）
4. TwistStamped 到 Twist 的底盘控制桥接
5. 上车联调与参数收敛

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

### 5.3 规划路线

1. 第一优先：局部导航闭环跑通
2. 第二优先：接入 FAR 全局规划
3. 探索规划（TARE）：延后，待 ARM64 OR-Tools 处理后再推进

## 6. 总计划（主线）

### 阶段 A：数据准备（立即）

1. 使用 `run_collect3.sh` 录制 `LiDAR + IMU` 新 bag
2. 用 `ros2 bag info` 确认消息数、持续时间、话题完整性
3. 产出一组可复现实验数据作为后续基准

### 阶段 B：离线 SLAM 验证

1. 完成 FAST-LIO2 编译
2. 基于新 bag 回放（`--clock`）验证轨迹和点云稳定性
3. 固化首版 `hesai_xt32` 参数配置（话题、外参、噪声）

### 阶段 C：接口对接（不接底盘）

1. 将 FAST-LIO2 输出映射到：
   `/state_estimation`
   `/registered_scan`
2. 启动 base autonomy 子模块验证规划输出
3. 确保 `local_planner` 使用 `config=standard` 且禁串口依赖路径

### 阶段 D：接入底盘（低速安全）

1. 新增 `TwistStamped -> Twist` relay
2. 低速参数下进行实车闭环验证
3. 分模式验证（手动/半自动/waypoint）

### 阶段 E：增强功能

1. 接入 FAR 全局规划并验证
2. TARE 仅在 ARM 依赖修复后再推进

## 7. 最近执行计划（建议按此顺序）

### 本次采集后 24 小时内

1. 用新 bag 做一次 FAST-LIO2 离线跑通
2. 出一版 RViz 截图与轨迹质量结论
3. 确认是否存在明显时间同步偏差

### 之后 2-4 天

1. 完成话题对接与 relay 节点
2. 完成不接底盘的导航链路验证
3. 做第一次低速上车验证

## 8. 请老师/其他 AI 重点帮看

1. D455 IMU 作为主 IMU 的长期可行性与风险
2. LiDAR 与 RealSense IMU 的时间同步方案是否足够稳健
3. 当前外参和噪声参数是否合理，优先改哪些参数
4. `TwistStamped -> Twist` 桥接是否足够，还是建议直接改 `pathFollower`
5. FAR 接入时最容易踩的坐标系和话题 remap 错误点

## 9. 附：当前关键文件

1. 项目精简记录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/jilu.md`
2. 项目原始记录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/jilu_raw_20260228.md`
3. 本文档：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/project_status_20260228.md`
4. 新采集脚本：`/home/rho/Documents/liuyi/run_collect3.sh`
5. 阶段 0 编译日志：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/build_stage0.log`
