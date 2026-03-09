# 项目整体思路与推进路线（2026-02-28）

> 这份文档是 2026-02-28 的路线和背景记录，不应直接当作当前运行事实。  
> 如果你要先建立当前上下文，请优先阅读：
> 1. `docs_ly/run_guide.md`
> 2. `docs_ly/current_status_20260309.md`
> 3. `docs_ly/navigation_debug_spin_issue_20260309.md`

> 本文档是对当前项目状态的完整梳理，适合在每次新 session 开始前阅读，以快速建立上下文。

---

## 一、目标

在 **Agilex Scout Mini + Hesai XT32 + RealSense D455 + Jetson AGX Orin** 上，跑通
`autonomy_stack_mecanum_wheel_platform` 的导航基线，实现：

1. **最小闭环**：SLAM 定位 + 局部避障 + 底盘执行（waypoint 导航）
2. **增强能力**：接入 FAR 全局规划
3. **可选扩展**：TARE 探索规划

---

## 二、原始系统 vs 我们的硬件差异

| 组件 | 原始平台（README） | 我们的平台 | 适配状态 |
|---|---|---|---|
| 底盘 | Mecanum 轮 T-Bot（全向轮） | Agilex Scout Mini（差速） | ⚠️ config=standard 已设，vehicleLength/Width 未修正 |
| LiDAR | Livox Mid-360 | Hesai XT32 | ✅ FAST-LIO2 Hesai handler 已实现 |
| IMU | Livox Mid-360 内置 | RealSense D455（BMI055，/camera/imu） | ✅ 验证可用，~193Hz |
| SLAM | arise_slam_mid360 | FAST-LIO2（独立 workspace） | ✅ 离线验证通过 |
| 主算力 | Intel NUC i7（x86） | Jetson AGX Orin（aarch64） | ✅ 已处理架构差异 |
| 电机接口 | 串口 /dev/ttyACM0（pathFollower 直写） | scout_base（订阅 geometry_msgs/Twist） | ✅ 已改为直接发布 `/cmd_vel (Twist)` |
| 坐标系约定 | Mid-360 body ≈ ROS 标准（X=前） | D455 body（Z=前，X=右，Y=下） | ✅ odom_frame_relay.py 已修正 |
| 车体尺寸 | 0.5m × 0.5m（默认值） | 0.93m × 0.70m（Scout Mini 官方数据） | ❌ local_planner 未修正 |

---

## 三、系统架构：数据如何流动

```
传感器（实车）或 bag 回放
  /lidar_points  (Hesai XT32, 10 Hz)
  /camera/imu    (RealSense D455, ~193 Hz)
         │
         ▼
  FAST-LIO2 (fastlio_ws)          LiDAR-Inertial 里程计 + 建图
         │
         ├─ /state_estimation_raw → odom_frame_relay.py → /state_estimation
         │                         （修正坐标系：Z=前 → X=前）
         └─ /registered_scan      （配准点云，world frame）
         │
         ▼
  sensor_scan_generation           时间同步 state + scan
         │ /sensor_scan + /state_estimation_at_scan
         ▼
  terrain_analysis                 地形可通行性（绿=可走 红=障碍）
         │ /terrain_map
         ▼
  local_planner (localPlanner)     局部路径规划
         │ /free_paths（候选路径扇形，水平面）
         ▼
  pathFollower                     路径跟踪
         │ /cmd_vel          (Twist, 实车)
         │ /cmd_vel_stamped  (TwistStamped, 仿真/调试)
         ▼
  scout_base                       底盘驱动
```

**TF 树（当前）**：
```
map ─(identity,static)─▶ camera_init ─(FAST-LIO2,动态)─▶ body
                                                            │
                                             (static, 旋转修正)
                                                            ▼
                                                         sensor
                                                        /       \
                                             sensor→vehicle  sensor→camera
                                             (local_planner 自动发布)
```

---

## 四、工程结构

```
thermal_nav/
├── fastlio_ws/                          FAST-LIO2 colcon workspace
│   └── src/
│       ├── FAST_LIO/                    含我们的 Hesai 修改
│       │   ├── config/hesai_xt32.yaml   新建的配置文件
│       │   └── src/preprocess.{h,cpp}  添加了 hesai_handler
│       └── livox_ros_driver2/           消息接口 stub（无硬件依赖）
│
└── autonomy_stack_mecanum_wheel_platform/   主导航栈 colcon workspace
    ├── docs_ly/                         我们的文档（本文件在此）
    └── src/base_autonomy/
        ├── sensor_scan_generation/
        ├── terrain_analysis/
        ├── terrain_analysis_ext/
        ├── local_planner/
        └── vehicle_simulator/
            ├── launch/system_scout_hesai.launch.py  主 launch 文件
            └── scripts/odom_frame_relay.py           坐标系修正节点
```

---

## 五、当前进度

| 里程碑 | 状态 |
|---|---|
| FAST-LIO2 工作空间搭建（Hesai handler、hesai_xt32.yaml） | ✅ 完成 |
| Phase B：FAST-LIO2 离线验证（轨迹质量好，无大漂移） | ✅ 完成 |
| Phase C：全流水线离线贯通（terrain_map、free_paths 正常） | ✅ 完成 |
| 坐标系修正（odom_frame_relay + body→sensor TF） | ✅ 完成 |
| TF 树搭建（map↔camera_init↔body↔sensor↔vehicle） | ✅ 完成 |
| **底盘控制接口改为 `/cmd_vel (Twist)`** | ✅ 已完成 |
| **vehicleLength/Width 修正**（0.5m→0.93×0.70m） | ❌ 未做 |
| Phase D：实车低速验证 | ❌ 未做 |
| FAR 全局规划接入 | ❌ 未做 |
| TARE 探索规划接入 | ❌ 未做 |

---

## 六、距离上车（Phase D）还差一件主要事情

### 缺口 1：底盘直连实车验证

- **现状**：pathFollower 已直接发布 `geometry_msgs/Twist` 到 `/cmd_vel`，
  scout_base 可以直接订阅；`/cmd_vel_stamped` 仅保留给仿真和调试链路。
- **剩余工作**：在实车上验证驱动链路、速度方向、限速与急停逻辑是否正常。

### 缺口 2：vehicleLength/Width 修正（安全项）

- **原因**：local_planner.launch 硬编码 vehicleLength=0.5, vehicleWidth=0.5，
  Scout Mini 实际 0.93×0.70m，避障裕量偏小约 40%~87%。
- **方案**：在 system_scout_hesai.launch.py 中把 localPlanner 和 pathFollower 改为直接以
  `Node` 方式启动（参考 FAST-LIO2 的做法），传入正确尺寸。

---

## 七、上车验证策略（Phase D 分三步）

上车时建议由易到难、每步确认再推进：

```
步骤 1：manual 模式（纯遥控，不开避障）
  目的：验证"底盘通信链路"——scout_base 能收到 `/cmd_vel (Twist)`，机器人能动
  方法：用手柄操控，观察 /cmd_vel (Twist) 话题有数据，机器人响应

步骤 2：smart joystick 模式（手柄控制 + 避障）
  目的：验证"避障模块"——terrain_map 能影响路径，机器人主动绕过障碍
  方法：开导航栈，用手柄推向障碍物，观察是否被阻挡

步骤 3：waypoint 模式（RViz 点击目标点，自主导航）
  目的：验证"完整导航闭环"——这是最终目标
  方法：在 RViz 点击 Waypoint，机器人自动规划并行走到目标点
```

---

## 八、关于 TARE 探索规划（ARM64 已支持）

README 原文（2025 年后更新）写道：

> A **recent upgrade** to the library made it compatible with both AMD64 and **ARM computers**.
> On ARM computers, please download the corresponding binary release, e.g.
> `or-tools_arm64_debian-11_cpp_v9.8.3296.tar.gz`, extract it, and replace
> the `include` and `lib` folders under `src/exploration_planner/tare_planner/or-tools`.

之前我们认为 TARE 在 ARM64 上不可用，这个判断已经**过时**。
接入探索规划的步骤是：
1. 从 [GitHub OR-Tools releases](https://github.com/google/or-tools/releases) 下载 ARM64 版本
2. 替换 `src/exploration_planner/tare_planner/or-tools` 下的 `include` 和 `lib`
3. 重新编译 tare_planner

---

## 九、建议推进顺序

```
当前（Phase C 完成）
    │
    ▼
【立即】Phase D 准备
    └─ 修正 vehicleLength/Width 到 0.93×0.70m，并完成底盘低速验证
    │
    ▼
【Phase D】实车验证（步骤 1→2→3，见第七节）
    │
    ▼
【Phase E】FAR 全局规划接入
    └─ 新建 system_scout_hesai_with_route_planner.launch.py
    │
    ▼
【可选】TARE 探索规划
    └─ 下载 ARM64 OR-Tools → 重编 tare_planner
    │
    ▼
【质量提升，可穿插】
    ├─ IMU Allan 方差标定（改善 FAST-LIO2 精度）
    └─ LI-Init 外参精标定（改善 SLAM 长距漂移）
```

---

## 十、关键文件速查

| 文件 | 作用 |
|---|---|
| `docs_ly/project_status_20260228.md` | 详细项目状态、FAST-LIO2 修改记录、编译命令（第 12 节） |
| `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py` | 系统主入口 launch 文件 |
| `src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py` | 坐标系修正节点 |
| `../fastlio_ws/src/FAST_LIO/config/hesai_xt32.yaml` | FAST-LIO2 Hesai 配置（含外参） |
| `docs_ly/data_calibration.txt` | 原始标定数据（外参推算来源） |
| `docs_ly/m1_result/` | Phase B（FAST-LIO2 离线）验收记录 |
