# 项目代码阅读导图与相对原始基线 `75f60cf8f4f3f4cde6e2b08f50577546d7f08dd7` 的差异说明

## 1. 文档目的

本文档用于回答三个问题：

1. 当前工作区代码，相对原始基线 `75f60cf8f4f3f4cde6e2b08f50577546d7f08dd7`，到底改了哪些地方。
2. 这些改动里，哪些只是文档/辅助改动，哪些真正可能改变导航行为，因而有可能引入实机问题。
3. 如果你现在要开始读这个项目代码，应该先理解哪些包、哪些文件、哪些话题链路。

本文档适合在一起看代码前先快速建立共同上下文，也适合看代码时当作“导图 + 对比底稿”。

## 2. 对比范围

- 基线提交：`75f60cf8f4f3f4cde6e2b08f50577546d7f08dd7`
- 当前参考对象：当前工作树（`HEAD = 3d75c2a239ecf3c900425cc6ac37600dea89d3c7`）
- 对比命令语义：本文档基于 `git diff 75f60cf8f4f3f4cde6e2b08f50577546d7f08dd7`，并结合当前工作树中的手工调整做文字说明
- 统计口径说明：下文的“24 个文件”不包含本文档 `docs_ly/codebase_guide_and_compare_vs_75f60cf8.md` 自身

## 3. 总体差异概览

### 3.1 文件级统计

- 总共变更 24 个文件
- 其中新增 11 个文件
- 修改 13 个文件
- 总体统计：`2707 insertions(+), 36 deletions(-)`

### 3.2 高层总结

从高层看，当前代码和原始基线的差异主要集中在 5 个方向：

1. 新增了面向 Scout Mini + Hesai XT32 + RealSense D455 的系统集成入口
2. 在 FAST-LIO 输出和 autonomy_stack 输入之间增加了坐标系/点云 frame 修正层
3. 重写了局部规划与跟踪链路的一部分接口和调参方式
4. 增加了大量调试可观测性，包括 CSV 日志、RViz 可视化、运行文档
5. 调整了 RViz goal 发布行为和地形参数，使其更贴近当前硬件

如果从“哪些改动最可能引入实机行为变化”来看，最值得优先怀疑的是：

1. `odom_frame_relay.py` 和相关 TF 旋转
2. `registeredScanFrameRelay.cpp` 与 `sensorScanGeneration.cpp` 的 frame 处理
3. `standard.yaml` 中 yaw gain / maxYawRate / dirDiffThre 的改动
4. `system_scout_hesai*.launch.py` 中对 `twoWayDrive`、车体尺寸、TF、话题 remap 的新设定

## 4. 项目阅读导图

这一节不是“对比基线”，而是帮助你快速建立对当前项目结构的直觉。建议先读这一节，再往下看相对基线的差异。

### 4.1 先抓当前运行主链路

如果你现在跑的是 `system_scout_hesai.launch.py` 或 `system_scout_hesai_with_far_planner.launch.py`，可以先把运行链路记成下面这样：

```text
FAST-LIO
  /Odometry
    -> /state_estimation_raw
    -> odom_frame_relay.py
    -> /state_estimation

  /cloud_registered
    -> /registered_scan_raw
    -> registeredScanFrameRelay
    -> /registered_scan

/state_estimation + /registered_scan
  -> sensor_scan_generation
     -> /state_estimation_at_scan
     -> /sensor_scan

/state_estimation + /registered_scan
  -> terrain_analysis
     -> /terrain_map

/terrain_map + /registered_scan + /state_estimation
  -> terrain_analysis_ext
     -> /terrain_map_ext

/goal_point
  -> far_planner
  -> /way_point

/way_point + /state_estimation + /registered_scan + /terrain_map
  -> localPlanner
  -> /path + /slow_down

/path + /state_estimation + /slow_down
  -> pathFollower
  -> /cmd_vel
```

最重要的理解是：

1. SLAM 和后续导航的交接点，不是在 `localPlanner.cpp`，而是在 `/state_estimation_raw`、`/registered_scan_raw` 经过 relay 之后形成的 `/state_estimation`、`/registered_scan`
2. `localPlanner` 是“规划器”，负责生成 `/path`
3. `pathFollower` 是“控制器”，负责把 `/path` 变成 `/cmd_vel`
4. `far_planner` 不是必选链路，只有你用 Goalpoint 做更远距离到点规划时才会插进来

补充一个容易误解的点：

- `sensor_scan_generation` 虽然在主 launch 里会启动，但当前 `localPlanner` / `pathFollower` 主链路并不直接消费它输出的 `/state_estimation_at_scan` 和 `/sensor_scan`
- `terrain_analysis_ext` 对 FAR 这条链更重要；`localPlanner` 当前直接订阅的是 `/terrain_map`

### 4.2 `src` 目录应该怎么理解

当前仓库的 `src` 可以先按 5 个大类来理解：

- `src/base_autonomy`
  这是最靠近“底盘局部导航”的一层，当前实机 debug 最值得优先看。
- `src/route_planner`
  这是更高层的路径/路线规划层，当前最相关的是 `far_planner`。
- `src/exploration_planner`
  这是探索式规划，不是你现在“点一个 Goalpoint 到那里去”这条主链路的核心。
- `src/slam`
  这是仓库自带的 SLAM 相关代码和依赖，但你当前主入口实际接的是 `fast_lio`，所以这层不是第一优先级。
- `src/utilities`
  这是各种工具包，例如 RViz 插件、手柄遥控、驱动、串口、domain bridge。

### 4.3 `base_autonomy` 下面这些包分别是干什么的

- `vehicle_simulator`
  名字容易误导。它不只是“仿真器”，当前更重要的作用是承载主 launch、RViz 配置、relay 节点、TF 桥接，以及一个可选的模拟底盘节点。
- `sensor_scan_generation`
  把 `/state_estimation` 和 `/registered_scan` 做时间同步，生成“扫描时刻的位姿”和“传感器坐标系下的扫描”。它更像数据整理层，不是最终控制逻辑本身。
- `terrain_analysis`
  把当前点云整理成局部地形/可通行性表示，输出 `/terrain_map`。
- `terrain_analysis_ext`
  在 `/terrain_map` 基础上做更大范围或连通性检查，输出 `/terrain_map_ext`。这层主要给更高层规划器，尤其是 FAR，用得更多。
- `local_planner`
  当前最核心的包。里面其实有两个节点：
  - `localPlanner`：根据目标点、障碍和地形选一条局部路径，输出 `/path`
  - `pathFollower`：根据 `/path` 和当前位姿生成 `/cmd_vel`
- `visualization_tools`
  主要是可视化和运行数据辅助，不是控制主逻辑。
- `waypoint_example`
  示例节点，可以先不看。

如果你的目标是 debug “为什么会转圈 / 为什么 Goalpoint 不接管”，`base_autonomy` 里优先级最高的是：

1. `vehicle_simulator`
2. `local_planner`
3. `terrain_analysis` / `terrain_analysis_ext`
4. `sensor_scan_generation`

### 4.4 哪些包现在可以先不深挖

为了把阅读范围压到两小时内，下面这些可以先知道名字，但不必现在深读：

- `src/exploration_planner/tare_planner`
  这是探索规划，不是当前点到点导航主链路。
- `src/route_planner/boundary_handler`、`src/route_planner/graph_decoder`、`src/route_planner/visibility_graph_msg`
  这些更像 FAR 的配套组件，不是你理解 `/cmd_vel` 异常的第一现场。
- `src/slam/arise_slam_mid360`
  当前主 launch 没直接走它。
- `src/utilities/ROS-TCP-Endpoint`、`domain_bridge`、`serial`
  这些属于桥接/外设/集成工具层。
- `src/utilities/teleop_*`
  这些更偏手动控制和 RViz 交互辅助。

### 4.5 SLAM 和后续模块到底在哪里交接

这一点非常关键，因为很多人会自然地以为“SLAM 的输出直接被 planner 用了”，但当前项目中间其实隔了几层适配。

交接点可以按下面 4 步理解：

1. `fast_lio` 原始输出
   - `/Odometry`
   - `/cloud_registered`
2. 进入当前项目后的第一层适配
   - `/Odometry -> /state_estimation_raw -> odom_frame_relay.py -> /state_estimation`
   - `/cloud_registered -> /registered_scan_raw -> registeredScanFrameRelay -> /registered_scan`
3. 进入地形与扫描整理层
   - `/registered_scan -> terrain_analysis -> /terrain_map`
   - `/terrain_map -> terrain_analysis_ext -> /terrain_map_ext`
   - `/state_estimation + /registered_scan -> sensor_scan_generation`
4. 进入规划与控制层
   - `/way_point -> localPlanner -> /path`
   - `/path -> pathFollower -> /cmd_vel`

所以如果你怀疑“SLAM 明明定位正常，但车为什么行为不对”，真正要检查的是这几个交接点：

- frame 是否被转对了
- `/state_estimation` 的 yaw 是否符合控制器预期
- `/registered_scan` 在 planner 看来障碍是不是落到了正确位置
- `/terrain_map` 是否把可通行区域表达正确

### 4.6 Plan 和 Control 在这个项目里是怎么拆开的

`local_planner` 这个包虽然名字叫一个包，但内部其实分成两段逻辑：

- `localPlanner.cpp`
  更接近“局部规划器”。它吃进目标点、障碍、地形和车体状态，选择一条合适的局部路径，发布 `/path`。
- `pathFollower.cpp`
  更接近“控制器”。它吃进 `/path` 和当前车体状态，算出车速和角速度，发布 `/cmd_vel`。

可以把它们记成：

- `localPlanner` 决定“往哪走”
- `pathFollower` 决定“怎么打轮、怎么给速度”

当前这两个文件分别是：

- `src/base_autonomy/local_planner/src/localPlanner.cpp`
- `src/base_autonomy/local_planner/src/pathFollower.cpp`

### 4.7 参数应该去哪里看

这个项目的参数分散在几层，不同层负责的事情不一样：

- `system_scout_hesai.launch.py` / `system_scout_hesai_with_far_planner.launch.py`
  这里看系统集成参数：启哪些节点、话题 remap、TF、`twoWayDrive`、车体尺寸、debug log、是否带 FAR。
- `src/base_autonomy/local_planner/launch/local_planner.launch`
  这里看 `localPlanner` 和 `pathFollower` 的接线方式，以及一批直接注入 node 的运行参数。
- `src/base_autonomy/local_planner/config/standard.yaml`
  这里看控制风格参数，尤其是 `yawRateGain`、`stopYawRateGain`、`maxYawRate`、`dirDiffThre`。
- `src/base_autonomy/local_planner/src/localPlanner.cpp`
  这里看规划参数实际怎么被使用，例如 `vehicleLength`、`vehicleWidth`、`pathScale`、`goalBehindRange`、`freezeAng`。
- `src/base_autonomy/local_planner/src/pathFollower.cpp`
  这里看控制参数实际怎么被使用，例如 `lookAheadDis`、`yawRateGain`、`dirDiffThre`、`maxAccel`。
- `src/base_autonomy/terrain_analysis/launch/terrain_analysis.launch`
  这里看地形判断参数，比如 `vehicleHeight`。
- `src/base_autonomy/terrain_analysis_ext/launch/terrain_analysis_ext.launch`
  这里看扩展地形与连通性参数。
- `src/route_planner/far_planner/config/*.yaml`
  这里看 Goalpoint/FAR 的全局规划参数。

### 4.8 你现在最该读的核心代码文件

这一节建议不要“平均用力”。  
对你当前最相关的两个现象:

1. 小车容易左右转圈
2. Goalpoint 看起来可达，但车没有正确规划/接管

真正最该优先读的是：`1 -> 3 -> 4 -> 8 -> 9 -> 10`，如果问题和 Goalpoint 强相关，再补 `2 -> 11 -> 12`。

下面每个文件都按“它负责什么、进去先看什么、它能帮你回答什么问题”来说明。

1. `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py`
   作用：这是当前实机主入口，决定整套系统真正启动了哪些节点、话题怎么 remap、TF 怎么桥接、车体尺寸和 `twoWayDrive` 怎么注入。
   进去先看：`fast_lio` 的 remap、`odom_frame_relay.py` / `registeredScanFrameRelay` 的启动、`local_planner.launch` 的参数注入、静态 TF 两段补偿。
   它主要回答的问题：你现在看到的 `/state_estimation`、`/registered_scan`、`/cmd_vel` 到底是不是这条链路产生的；实机跑的到底是不是你以为的那套配置。

2. `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py`
   作用：这是带 Goalpoint/FAR 的主入口，比上一份 launch 多了 `/goal_point -> far_planner -> /way_point` 这条链。
   进去先看：`far_planner.launch` 的 include、`route_planner_config`、以及它依赖的 `/state_estimation`、`/terrain_map[_ext]`、`/registered_scan`。
   它主要回答的问题：你点击 Goalpoint 时，系统到底有没有把 FAR 真正接进来；当前 Goalpoint 异常是不是 launch 层没有接通。

3. `src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py`
   作用：把 FAST-LIO 的里程计轴系转换成 autonomy_stack 期望的 ROS 标准轴系，产出 `/state_estimation`。
   进去先看：文件开头的轴系说明、`Q_MAP_CAMERA_INIT`、`Q_BODY_SENSOR`、`quat_multiply()`、`rotate_vector()`、以及 `callback()` 里 pose 和 twist 是怎么一起旋转的。
   它主要回答的问题：`vehicleYaw`、线速度、角速度的方向有没有被转对；“喜欢左右转圈”是不是朝向定义从这里开始就偏了。

4. `src/base_autonomy/vehicle_simulator/src/registeredScanFrameRelay.cpp`
   作用：把 FAST-LIO 输出的配准点云从 `camera_init` 轴系转换成 autonomy_stack 使用的 `map` 轴系，产出 `/registered_scan`。
   进去先看：点坐标变换那 3 行 `dst.x / dst.y / dst.z`，以及输出 `frame_id = "map"`。
   它主要回答的问题：障碍在 planner 看来是不是落到了正确的位置和正确侧边；“看起来可达但 planner 认为不通”是不是点云旋转错了。

5. `src/base_autonomy/sensor_scan_generation/src/sensorScanGeneration.cpp`
   作用：把 `/state_estimation` 和 `/registered_scan` 做时间同步，生成扫描时刻的位姿和传感器系点云。
   进去先看：订阅 `/state_estimation` 和 `/registered_scan` 的同步方式、TF buffer/listener、输出 `/state_estimation_at_scan` 和 `/sensor_scan` 的地方。
   它主要回答的问题：当前系统有没有在 scan 时刻位姿和点云之间做对齐；如果某些上层模块依赖 scan 时刻位姿，那里用的是哪份数据。
   补一句：它不是你当前 `/cmd_vel` 主链路最核心的文件，但它能帮你看懂“点云和位姿是怎么对齐后再给别的模块用的”。

6. `src/base_autonomy/terrain_analysis/src/terrainAnalysis.cpp`
   作用：把当前点云整理成局部地形和可通行性表示，输出 `/terrain_map`。
   进去先看：参数读取区，尤其是 `obstacleHeightThre`、`vehicleHeight`、`minRelZ/maxRelZ`；再看订阅 `/state_estimation`、`/registered_scan` 和发布 `/terrain_map` 的地方。
   它主要回答的问题：系统是如何把“点云”变成“可通行/不可通行地形”的；高度阈值是不是把本来能过的地方判成了障碍。

7. `src/base_autonomy/terrain_analysis_ext/src/terrainAnalysisExt.cpp`
   作用：在局部地形基础上做更大范围的扩展和连通性检查，输出 `/terrain_map_ext`。
   进去先看：`checkTerrainConn`、`terrainConnThre`、`localTerrainMapRadius` 等参数，以及订阅 `/terrain_map`、发布 `/terrain_map_ext` 的部分。
   它主要回答的问题：如果用 FAR，更大范围的地形连通性是怎么来的；Goalpoint 规划时，FAR 是不是因为扩展地形判断而不愿意给出 `/way_point`。
   补一句：对当前只看 `/cmd_vel` 的问题，它不是第一优先级；但对 Goalpoint 链路，它比 `sensor_scan_generation` 更值得后补。

8. `src/base_autonomy/local_planner/src/localPlanner.cpp`
   作用：这是局部规划核心。它根据目标点、当前姿态、障碍、地形和车体尺寸，从预生成路径集合里选出当前最合适的一条，发布 `/path`。
   进去先看：参数读取区；然后重点看 `goalHandler()` 附近、主循环里 `relativeGoalX/Y`、`joyDir`、`freezeStatus`、`pathFound`、`selectedPathGroup` 这些变量；再看障碍点如何对路径组打分。
   它主要回答的问题：为什么某个 goal 在你看来可达，但系统最后没有给出 path；是不是被 `twoWayDrive=false`、`goalBehindRange`、`freezeAng`、车体尺寸、障碍打分或地形阈值卡住了。
   对你当前问题最重要的几个观察点：
   `relativeGoalX/relativeGoalY` 表示目标在车体系里到底落在哪个方向；
   `joyDir` 表示规划器认为应该朝哪个方向走；
   `pathFound` 表示局部规划到底有没有找到可行路；
   `selectedPathGroup` 表示最后选中了哪组候选路径。

9. `src/base_autonomy/local_planner/src/pathFollower.cpp`
   作用：这是控制核心。它把 `/path` 和当前 `/state_estimation` 转成最终 `/cmd_vel`。
   进去先看：参数读取区；然后看 `pathHandler()` 如何接管新路径；再看主循环里 `dirDiff`、`vehicleYawRate`、`vehicleSpeed` 的计算，以及最后 `cmd_vel` 怎么组出来。
   它主要回答的问题：车为什么会原地转、转得太慢、转不正、或者明明有 path 却不往前走。
   对你当前问题最重要的几个观察点：
   `dirDiff` 是“车头方向”和“路径方向”的偏差；
   `yawRateGain / stopYawRateGain / maxYawRate` 决定怎么把这个偏差变成转向命令；
   `dirDiffThre` 决定车在朝向误差多小时才愿意明显往前加速；
   `cmd_vel.linear.x` 和 `cmd_vel.angular.z` 是最后真正送到底盘的东西。

10. `src/base_autonomy/local_planner/config/standard.yaml`
    作用：这是 `pathFollower` 控制风格最集中的配置文件。
    进去先看：`yawRateGain`、`stopYawRateGain`、`maxYawRate`、`dirDiffThre`、`stopDisThre`。
    它主要回答的问题：当前控制器到底是激进还是保守；“为什么它老是只转不走 / 走得很犹豫”是不是这里的阈值和增益造成的。
    阅读方法上，最好和 `pathFollower.cpp` 对着看，因为 yaml 只告诉你数值，真正怎么用还得回到代码。

11. `src/utilities/goalpoint_rviz_plugin/src/goalpoint_tool.cpp`
    作用：这是 RViz 里 Goalpoint 工具的消息出口。你点击地图时，实际就是它在发 `/goal_point`。
    进去先看：`onPoseSet()` 里 `/goal_point` 的 `frame_id`、`x/y/z` 如何填写，以及同时发了什么 `/joy` 消息。
    它主要回答的问题：你点击 Goalpoint 后，系统到底收到了什么样的消息；goal 是不是固定在 `map` 系、是不是被强制压成了地面 `z=0`。

12. `src/route_planner/far_planner/src/far_planner.cpp`
    作用：这是 Goalpoint 到 `/way_point` 的主规划器。如果 Goalpoint 功能不正常，这个文件通常是最终要看的地方。
    进去先看：初始化时订阅/发布了哪些话题；`WaypointCallBack()` 在收到 `/goal_point` 后做了什么；以及它对 graph 初始化、frame 转换和目标更新的前置条件。
    它主要回答的问题：为什么点击了 Goalpoint 却没有持续产生 `/way_point`；是不是 graph 还没初始化、frame 不对、或者 FAR 内部根本没接受这个目标。

如果只给你两小时，建议阅读节奏是：

1. 先用 15-20 分钟读 `system_scout_hesai.launch.py`
2. 再用 15 分钟读 `odom_frame_relay.py` 和 `registeredScanFrameRelay.cpp`
3. 然后把 40-50 分钟压给 `localPlanner.cpp` 和 `pathFollower.cpp`
4. 再用 10 分钟对照 `standard.yaml`
5. 最后如果 Goalpoint 是重点，再读 `system_scout_hesai_with_far_planner.launch.py`、`goalpoint_tool.cpp`、`far_planner.cpp`

### 4.9 读代码时最值得先回答的 5 个问题

1. `/state_estimation` 的 frame、yaw、twist 方向到底是不是控制器假设的那套？
2. `/registered_scan` 在 planner 看来，障碍是不是落在正确侧边和正确高度？
3. `localPlanner` 是否真的找到了 path，还是目标在它看来被障碍/尺寸/后向约束挡住了？
4. `pathFollower` 算出来的 `dirDiff`、`vehicleYawRate`、`vehicleSpeed` 是否符合你的直觉？
5. 如果使用 Goalpoint，`/goal_point` 是否真的稳定地变成了 `/way_point`？

## 5. 模块级差异

### 5.1 系统集成层：从“原仓库通用入口”变为“当前硬件定制入口”

这是本次对比里最关键的变化。

原始基线里没有下面这两个 launch 入口：

- `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py`
- `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py`

这意味着当前代码不是在原项目默认入口上只做小修小补，而是新增了一套“面向当前硬件平台”的系统集成层。

这两个新入口做了几件大事：

1. 不再假设原项目自带 SLAM，而是直接在 launch 中启动 `fast_lio/fastlio_mapping`
2. 把 FAST-LIO 话题重映射为：
   - `/Odometry -> /state_estimation_raw`
   - `/cloud_registered -> /registered_scan_raw`
3. 在 remap 后插入两个 relay：
   - `odom_frame_relay.py`
   - `registeredScanFrameRelay`
4. 把 `local_planner.launch` 作为子模块接入，并注入当前平台专用参数：
   - `config=standard`
     直观理解：使用“普通轮式/差速风格”的控制配置，而不是原项目给麦克纳姆全向轮准备的配置。
   - `realRobot=false`
     直观理解：不走原项目里“串口直接写电机协议”的那条老链路，而是走 ROS 话题控制。
   - `twoWayDrive=false`
     直观理解：不允许规划器把“倒车”当成正常策略，目标跑到车后方时更倾向于先转头再走。
   - `vehicleLength=0.70`
     直观理解：把车前后方向按 0.70 m 算，数值越大，规划器越容易觉得“前后空间不够”，会更保守。
   - `vehicleWidth=0.60`
     直观理解：把车左右宽度按 0.60 m 算，数值越大，规划器越容易觉得“侧向间隙不够”，会更保守。
5. 显式发布若干静态 TF，把 FAST-LIO 的 `camera_init/body` 轴系转换为 autonomy_stack 所期望的 `map/sensor/vehicle`
6. 在带 FAR 的版本中，把 `far_planner.launch` 一并接入，并配好 `/goal_point -> /way_point` 的完整链路

结论：

- 原始基线更像“通用导航仓库”
- 当前代码已经演化为“当前硬件适配后的系统版本”
- 因此后续 debug 时，不能只盯 `local_planner`，必须同时检查这一层的 relay、TF 和 remap

### 5.2 车体坐标系和点云坐标系修正层

这是当前代码相对原始基线最核心的新功能层。

#### 新增文件

- `src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py`
- `src/base_autonomy/vehicle_simulator/src/registeredScanFrameRelay.cpp`

#### 目的

当前硬件下，FAST-LIO 的 `camera_init/body` 轴系与 autonomy_stack 期望的 ROS 车体轴系不一致。当前代码显式加入了两层转换：

1. 里程计方向修正：`/state_estimation_raw -> /state_estimation`
2. 配准点云方向修正：`/registered_scan_raw -> /registered_scan`

#### `odom_frame_relay.py` 做了什么

- 订阅 `/state_estimation_raw`
- 使用固定四元数把 FAST-LIO 的姿态、位置、twist 转到 ROS 标准轴系
- 输出 `/state_estimation`
- 统一 `header.frame_id = map`
- 统一 `child_frame_id = sensor`

这部分改动会直接影响：

- `localPlanner.cpp` 里从 odom 解算出的 `vehicleYaw`
- `pathFollower.cpp` 的 `dirDiff`
- RViz 中看到的车体朝向

如果这里有符号错、乘法顺序错、frame 约定错，就很容易出现“车喜欢左右转圈”。

#### `registeredScanFrameRelay.cpp` 做了什么

- 订阅 `/registered_scan_raw`
- 把点云从 FAST-LIO 世界系：
  - `X=right, Y=down, Z=forward`
- 转为 autonomy_stack 使用的 ROS map 轴系：
  - `X=forward, Y=left, Z=up`
- 输出 `/registered_scan`

这部分改动会直接影响：

- `sensor_scan_generation`
- `terrain_analysis`
- `terrain_analysis_ext`
- `localPlanner` 看到的障碍物空间分布

如果这里方向搞错，可能会出现：

- 障碍物落在错误侧边
- `free_paths` 朝向异常
- 看起来 goal 可达，但局部规划认为不可达

### 5.3 `sensor_scan_generation`：从默认 frame 假设改为显式 TF 查询

修改文件：

- `src/base_autonomy/sensor_scan_generation/src/sensorScanGeneration.cpp`

原始逻辑更接近默认假设：

- 假设 odom 在 `map`
- 假设点云和 odom 已经天然共 frame

当前逻辑新增了：

1. `tf2_ros::Buffer`
2. `tf2_ros::TransformListener`
3. 根据 `odometry.header.frame_id` 和 `laserCloud2->header.frame_id` 判断是否需要查 TF
4. 如果 `cloudFrame != odomFrame`，先查 `cloud -> odom` 变换，再转到 `sensor_at_scan`
5. 发布 `state_estimation_at_scan` 和 `sensor_scan` 时不再强写死 `map`，而是沿用 `odomFrame`

这说明当前代码在尝试修复“点云 frame 和里程计 frame 不一致”问题。

这是一个合理方向，但它也引入了新的潜在风险：

- TF 如果没准备好，节点会直接 warning 并 return
- 某次 lookup 失败时，这一帧 scan 不会进入后续管线
- 如果上游 frame 命名和预期不一致，会造成间歇性地图/障碍缺失

### 5.4 局部规划层：`local_planner.launch` 从硬编码改为可注入参数

修改文件：

- `src/base_autonomy/local_planner/launch/local_planner.launch`

主要变化：

1. 新增 launch 参数
   - `vehicleLength`
     直观理解：车前后长度，用在碰撞检测和路径可通行判断里。
   - `vehicleWidth`
     直观理解：车左右宽度，也用在碰撞检测里。
   - `enableDebugLog`
     直观理解：是否把 planner/controller 的运行状态写成 CSV，便于事后复盘；它本身不直接改变控制行为。
   - `debugLogDir`
     直观理解：日志写到哪里。
   - `debugLogDecimation`
     直观理解：日志降采样倍率，数值越大，记录越稀疏。
2. 原来写死的 `vehicleLength=0.5`、`vehicleWidth=0.5` 改成可注入
   直观理解：基线项目默认按一台更小、更通用的车来算；改成可注入之后，launch 可以按 Scout Mini 的真实尺寸覆写，不同平台不必再改源码。
3. 原来写死的 `twoWayDrive=true` 改成可注入
   直观理解：这个参数控制系统是否把“倒车到目标”视为合法策略。基线默认允许双向行驶；现在改成由 launch 决定，方便根据底盘习惯选择“能倒车”还是“只准前进”。
4. `pathFollower` 参数改动：
   - `lookAheadDis: 0.5 -> 1.0`
     直观理解：跟踪器在路径上“往前看”多远来选目标点。值更大，轨迹通常更平滑，但也更容易拐弯抹角或切弯；值更小，反应更灵，但更容易抖。
   - `maxAccel: 2.0 -> 1.0`
     直观理解：允许速度变化的快慢。2.0 更猛，起步/减速更快；1.0 更柔和，但响应会慢一些。
5. 把 planner/controller 的 debug logging 参数一路传入 node

结论：

- 原始基线是“默认小车参数”
- 当前代码试图把它调成更适配 Scout Mini 的系统
- 这会直接影响轨迹裁剪、碰撞检测和速度控制

### 5.5 局部规划算法主体：`localPlanner.cpp`

修改文件：

- `src/base_autonomy/local_planner/src/localPlanner.cpp`

这部分不是算法重写，但新增了大量“可观测性”和“调试辅助状态”。

主要改动可以分成 4 类：

#### A. 新增 planner 调试日志

新增内容：

- 目录创建逻辑
- `local_planner.csv`
- 记录事件类型、goal 相对位置、左右障碍分布、freeze 状态、最终选中的路径组等

这类改动本身不应该改变控制行为，但会改变你观察系统的方式。

#### B. 收 goal 时增加显式日志

`goalHandler()` 现在会：

- 记录 `goalX/goalY`
- 置位 `plannerGoalUpdated = true`
- 输出 `Waypoint received`

这让你可以判断“RViz 点击是否真的进了 local planner”。

#### C. 统计左右障碍和选路细节

当前代码新增了：

- 左右侧点计数
- 障碍左右分布计数
- 选中的 `selectedGroupRaw`
- 选中的旋转角 `selectedRotDeg`
- 最终路径点数 `selectedPathPointCount`
- 惩罚项 `finalPenaltyScore`

这说明当前代码的核心规划思路没被大改，但加入了很多“解释器变量”。

#### D. 增加 throttle 日志输出

当前版本每秒会打印一次类似：

- 目标相对位置
- `joyDir`
- 是否找到路径
- 选了哪个 path group
- 当前慢行级别

这会让你在实机上更容易判断：

- 是没收到 goal
- 还是收到了 goal 但 pathFound=0
- 还是 pathFound=1 但 controller 没跟上

### 5.6 控制器：`pathFollower.cpp`

修改文件：

- `src/base_autonomy/local_planner/src/pathFollower.cpp`

这是相对原始基线变化最大的行为层之一。

主要差异如下。

#### A. `/cmd_vel` 接口语义发生了变化

原始基线：

- `/cmd_vel` 发布类型是 `geometry_msgs::msg::TwistStamped`

当前代码：

- `/cmd_vel` 发布类型改为 `geometry_msgs::msg::Twist`
- 额外新增 `/cmd_vel_stamped`，继续发布 `TwistStamped`

这背后的思路是：

- 实车驱动通常直接吃 `Twist`
- 仿真器原本吃 `TwistStamped`
- 所以现在拆成双通道兼容

这是一个非常重要的接口改动，因为它改变了整个控制输出的终点。

#### B. 仿真器同步适配

`src/base_autonomy/vehicle_simulator/src/vehicleSimulator.cpp` 只改了一行，但含义很关键：

- 原来订阅 `/cmd_vel`
- 现在改成订阅 `/cmd_vel_stamped`

也就是说：

- 实车路径：`pathFollower -> /cmd_vel (Twist)`
- 仿真路径：`pathFollower -> /cmd_vel_stamped (TwistStamped) -> vehicleSimulator`

这是一种“接口双轨兼容”改动。

#### C. 控制参数被明显调保守

`src/base_autonomy/local_planner/config/standard.yaml` 中：

- `yawRateGain: 8.0 -> 4.0`
  直观理解：把“朝向误差”转换成“转向角速度”的放大倍数。同样的偏航误差下，4.0 产生的转向命令大约只有 8.0 的一半，所以车会转得没那么凶。
- `stopYawRateGain: 12.0 -> 6.0`
  直观理解：车速很低或几乎停住时使用的专用转向增益。这个值降低后，原地修正朝向时也会更保守。
- `maxYawRate: 150.0 -> 60.0`
  直观理解：角速度上限，单位可以近似理解为“每秒最多转多少度”。从 150 降到 60，相当于给转向动作加了更严格的限速。
- `dirDiffThre: 0.15 -> 0.30`
  直观理解：只有当车头方向和路径方向“差得不太多”时，才愿意明显加速前进。阈值变大后，系统会在朝向还没完全对正时更早开始往前走。

这是非常明确的控制风格变化：

- 原始基线更激进
- 当前代码更保守

这类改动可能改善抖动，但也可能引入：

- 转向不够果断
- 跟踪滞后
- 到目标附近调整过慢

#### D. 历史上曾新增“路径更新保留/抑制”逻辑，但当前工作树已回退

这里需要特别说明一下：`03bb5e0 (less update path, change dirdiffthre)` 这个提交里，曾经给 `pathFollower.cpp` 加过一段“保留旧路径进度 / 抑制短路径更新”的逻辑，并新增了一组配套参数。

但当前工作树已经把这段逻辑手工回退到更接近 `2fb4167e79f642c32229b4cf0fcbae0509cc0220` 的行为：

- 收到新 path 后，重新覆盖旧 path
- `pathPointID` 直接回到 `0`
- 不再根据“短路径”“匹配阈值”决定是否 suppress 这次更新

所以这部分可以作为“你调试过程中曾经引入过的中间版本历史”保留在讨论里，但它已经不再是当前代码相对基线的有效差异点。

#### E. 新增 path follower CSV 和 throttle 日志

新增文件输出：

- `path_follower.csv`

主要记录：

- path size
- 当前 path point id
- `dirDiff`
- `endDis`
- `vehicleSpeed`
- `vehicleYawRate`
- 实际发出的 `cmd_vel`

这部分不一定引入 bug，但大大提高了 debug 能力。

### 5.7 地形模块：仅做了参数级校准

修改文件：

- `src/base_autonomy/terrain_analysis/launch/terrain_analysis.launch`
- `src/base_autonomy/terrain_analysis_ext/launch/terrain_analysis_ext.launch`

改动很集中：

- `vehicleHeight: 1.5 -> 0.95`
  直观理解：这是地形分析里用来描述“车体/传感器离地参考高度”的参数。它会影响系统怎么区分地面、障碍和车体附近的可通行空间。值太高或太低，都可能让障碍判断失真。

这属于参数标定级改动，不是算法结构改动。

但它会影响：

- 地面/障碍分层
- terrain 连通性判断
- 哪些点被认为是“车体附近可通行高度”

因此它仍然可能影响：

- 局部规划认为能不能过
- FAR 认为 goal 周围是不是 free terrain

### 5.8 RViz 和 Goal/Waypoint 工具

修改文件：

- `src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz`
- `src/utilities/goalpoint_rviz_plugin/src/goalpoint_tool.cpp`
- `src/utilities/waypoint_rviz_plugin/src/waypoint_tool.cpp`

主要变化：

1. Waypoint / Goalpoint 的 `z` 从 `vehicle_z` 改成 `0.0`
2. RViz 中新增：
   - Goalpoint marker
   - FAR global path marker
   - V-Graph marker
   - Goalpoint tool
3. `/way_point` 的显示半径缩小，视觉上更贴近地面点击点

这类改动的含义：

- 更方便调试 FAR planner
- goal 发布统一落在地平面，减少 RViz 视觉歧义

潜在风险：

- 如果上游地图实际高度不是 0 平面，goal z 被强制置零可能造成“看起来点在地面，实际不在正确高度层”

不过从当前系统看，主要导航还是 2D/近平面思路，这一改动更像 UI/操作层修正，而不是核心 bug 源。

### 5.9 CMake / 安装层

修改文件：

- `src/base_autonomy/vehicle_simulator/CMakeLists.txt`

主要变化：

1. 新增编译：
   - `registeredScanFrameRelay`
2. 新增安装脚本：
   - `odom_frame_relay.py`

当前版本已经不再保留 `twist_stamped_to_twist.py` 这种过渡脚本，原因是
`pathFollower` 已直接发布 `/cmd_vel (Twist)`，只额外保留 `/cmd_vel_stamped`
给仿真和调试使用。

### 5.10 文档与运行辅助

新增文件：

- `docs_ly/project_status_20260228.md`
- `docs_ly/readme_ly.md`
- `docs_ly/run_guide.md`
- `docs_ly/strategy_overview_20260228.md`
- `runtime_logs/README.md`
- `frames_2026-03-03_22.23.49.gv`
- `frames_2026-03-03_22.23.49.pdf`

修改文件：

- `.gitignore`

作用：

1. 记录硬件适配过程
2. 记录运行步骤和调试结论
3. 记录 TF 树快照
4. 忽略运行中产生的 `runtime_logs/navigation_debug/*`

这些改动本身不会改变运行行为，但提供了大量先验信息。

## 6. 哪些改动最可能引入实机问题

如果想从“是不是你后续修改引入了错误”这个角度看，我建议优先盯下面 6 项。

### 6.1 `odom_frame_relay.py`

风险点：

- 四元数乘法顺序
- `map/camera_init/body/sensor` 的轴系约定
- pose 和 twist 是否被一致地旋转

可能表现：

- 小车喜欢左右转圈
- RViz 里朝向和真实前进方向不一致

### 6.2 `registeredScanFrameRelay.cpp` + `sensorScanGeneration.cpp`

风险点：

- 点云 frame 旋转方向
- `lookupTransform(odomFrame, cloudFrame, ...)` 的方向是否正确
- 某些时刻 TF lookup 失败导致 scan 丢帧

可能表现：

- 规划器看到的障碍侧别颠倒
- FAR / local planner 偶发性“认为前方不通”

### 6.3 `pathFollower.cpp` 中这段 path update 逻辑的历史背景

补充说明：

- 这段逻辑曾在 `03bb5e0` 引入
- 当前工作树已经手工回退，不再保留相关参数和分支
- 如果你要复盘“是不是我某次改动引入过问题”，这仍然是一个值得讨论的历史点

### 6.4 `standard.yaml` 的控制增益改动

风险点：

- yaw gain 和 max yaw rate 降太多
- 跟踪器转向不够快

可能表现：

- 跟踪保守
- 目标侧向误差较大时反应迟钝

### 6.5 `system_scout_hesai.launch.py` 中对 `twoWayDrive=false` 和车体尺寸的设定

风险点：

- 当前底盘是否真的应完全禁用倒车
- 车体尺寸与实际底盘是否一致

可能表现：

- 目标一旦落在车后方，planner/controller 策略很僵
- 可通行区域被判得过窄或过宽

### 6.6 Goal/Waypoint z 固定为 0

风险点：

- 如果当前地图高度参考不是平地 z=0，goal 可能落在非理想层

可能表现：

- 点了一个看起来可达的位置，planner 内部却不认为 goal 合理

## 7. 文件清单

### 7.1 新增文件

| 状态 | 文件 | 说明 |
|---|---|---|
| A | `docs_ly/project_status_20260228.md` | 项目状态文档 |
| A | `docs_ly/readme_ly.md` | 适配过程与对话记录 |
| A | `docs_ly/run_guide.md` | 当前运行指南 |
| A | `docs_ly/strategy_overview_20260228.md` | 总体策略文档 |
| A | `frames_2026-03-03_22.23.49.gv` | TF 图源文件 |
| A | `frames_2026-03-03_22.23.49.pdf` | TF 图导出文件 |
| A | `runtime_logs/README.md` | planner/controller CSV 日志说明 |
| A | `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py` | 当前硬件主入口 |
| A | `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py` | FAR 集成入口 |
| A | `src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py` | 里程计坐标系修正 |
| A | `src/base_autonomy/vehicle_simulator/src/registeredScanFrameRelay.cpp` | 配准点云 frame 修正 |

### 7.2 修改文件

| 状态 | 文件 | 说明 |
|---|---|---|
| M | `.gitignore` | 忽略 navigation debug 运行日志 |
| M | `src/base_autonomy/local_planner/config/standard.yaml` | 控制器增益调整 |
| M | `src/base_autonomy/local_planner/launch/local_planner.launch` | 车体尺寸、两驱模式、日志参数、控制参数改造 |
| M | `src/base_autonomy/local_planner/src/localPlanner.cpp` | planner 调试日志、goal 日志、选路观测变量 |
| M | `src/base_autonomy/local_planner/src/pathFollower.cpp` | `/cmd_vel` 类型、控制器日志 |
| M | `src/base_autonomy/sensor_scan_generation/src/sensorScanGeneration.cpp` | 引入 TF 查询，增强 frame 兼容性 |
| M | `src/base_autonomy/terrain_analysis/launch/terrain_analysis.launch` | `vehicleHeight` 标定调整 |
| M | `src/base_autonomy/terrain_analysis_ext/launch/terrain_analysis_ext.launch` | `vehicleHeight` 标定调整 |
| M | `src/base_autonomy/vehicle_simulator/CMakeLists.txt` | 安装/编译新增 relay 组件 |
| M | `src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz` | FAR 可视化、Goalpoint 工具、marker 增强 |
| M | `src/base_autonomy/vehicle_simulator/src/vehicleSimulator.cpp` | 改为订阅 `/cmd_vel_stamped` |
| M | `src/utilities/goalpoint_rviz_plugin/src/goalpoint_tool.cpp` | goal z 改为固定 0 |
| M | `src/utilities/waypoint_rviz_plugin/src/waypoint_tool.cpp` | waypoint z 改为固定 0 |

## 8. 建议你怎么用这份文档

建议按下面顺序讨论：

1. 先确认“哪些改动只是文档/辅助”，避免把注意力浪费在非行为层
2. 再确认“当前系统主入口已经不是原始入口，而是一套新 launch + relay + TF 架构”
3. 然后重点过 3 个行为热点：
   - `odom_frame_relay.py`
   - `registeredScanFrameRelay.cpp` / `sensorScanGeneration.cpp`
   - `pathFollower.cpp` 的控制参数与 `/cmd_vel` 行为
4. 最后再看参数层：
   - `standard.yaml`
   - `vehicleLength/vehicleWidth`
   - `vehicleHeight`

如果目标是尽快判断“是否是后续适配改动引入的问题”，最有效的方式不是从头通读，而是优先看这些相对基线新增的行为层。

## 9. 一句话结论

相对原始基线，当前代码的核心变化不是“某个小 bug 修补”，而是新增了一整层面向 Scout Mini + Hesai + D455 + FAST-LIO 的系统适配层。  
因此，实机出现的转圈、Goalpoint 不生效、规划异常，完全有可能来自这些适配改动中的 frame、TF、话题接口、参数设定或地形表达，而不一定是原始仓库本身的问题。
