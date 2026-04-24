# 2026-04-25 调试总结：FAST-LIO / OctoMap / ARIADNE / local planner

## 1. 这轮调试的背景

这轮工作的目标不是做 `github` 和 `bitbucket` 两版 FAST-LIO 的公平算法对比，而是解决工程链路里的几个真实问题：

- 两版 FAST-LIO 都能正常启动，轨迹也基本正常
- 但 `bitbucket` 版本在接 OctoMap 时，偶尔会出现“点云看得到，但障碍没有稳定落到图上”的感觉
- ARIADNE 在室内探索时，有时会出现 graph / node / waypoint 与 `/projected_map` 不一致，甚至 waypoint 卡在障碍后面
- local planner 有时转向贴障碍，或者在几个相近选择之间左右、前后来回犹豫

所以这轮重点是：

1. 理清 FAST-LIO 到 OctoMap 的数据承接链路
2. 找到 ARIADNE graph / waypoint 与占据图不同步时更可能的原因
3. 找到一组当前室内探索更稳的参数
4. 对 local planner 的“转向贴障碍”和“路径切换过勤”做一轮工程调参

## 2. 主要遇到的问题

### 2.1 FAST-LIO 输出正常，但 OctoMap / ARIADNE 后段偶尔表现异常

前面已经确认：

- `github` 和 `bitbucket` 两版 FAST-LIO 都能成功运行
- 里程计轨迹本身没有明显问题
- 问题更多出现在 FAST-LIO 之后的 relay / `sensor_scan_generation` / OctoMap / ARIADNE 承接阶段

最典型的现象是：

- RViz 里能看到 `sensor_scan`
- 但对应位置不一定总能稳定变成 OctoMap 障碍
- 或者 `/projected_map` 已经有障碍了，但 graph / node / waypoint 还沿着旧结构走

### 2.2 `bitbucket` 的 `sensor_scan` 看起来比 `github` 更稀

后面确认这不是 `sensor_scan_generation` 自己做了额外下采样，而是上游 FAST-LIO 发布的 `/registered_scan` 本来就可能更稀。

结论是：

- `dense_publish_en=true` 时，更偏向发稠密的去畸变点云
- `dense_publish_en=false` 时，更偏向发已经降采样后的点云
- `sensor_scan_generation` 只是逐点做坐标变换，不再主动降采样

这解释了为什么 `bitbucket` 的 `sensor_scan` 视觉上可能更稀。

### 2.3 ARIADNE graph / waypoint 可能比 `/projected_map` 慢很多，甚至像“没更新”

这轮一个重要发现是：

- `/projected_map` 已经显示新障碍
- local planner 也知道当前方向不好走
- 但高层 `waypoint` 仍然不换
- 小车因此出现左右摇摆、前后犹豫，或者在两个 waypoint 之间来回纠结

这个现象不是单纯“OctoMap 慢”，而更像：

- 高层 graph 更新本来就不是 occupancy map 的直接镜像
- 它有很多局部更新、条件更新、保留旧结构的逻辑
- 同时 local planner 没有一条“当前 waypoint 不可达”的反馈链路回到 ARIADNE

### 2.4 `sensor_range=20` 在室内对 ARIADNE 来说偏激进

现场现象很明确：

- `ariadneSensorRange=20` 时，更容易出现 graph / node 压在 occupied 区上的情况
- 改回 `10` 之后，这个问题明显缓解

这说明当下的瓶颈不只是“看得不够远”，而是：

- graph 更新范围变大
- utility 统计范围变大
- 旧结构更容易残留
- waypoint 更容易显得“想法太多”

### 2.5 local planner 主要问题是“转向贴障碍”，不是简单的平移 clearance 不够

进一步梳理代码后发现：

- 当前并没有传统意义上的在线 occupancy inflation 层
- 平移避障更像是用离线生成的路径-障碍对应关系做二值阻挡判断
- `vehicleLength` / `vehicleWidth` 主要在转向碰撞检查里起作用

所以“转向贴障碍”这件事，更应该优先从：

- `checkRotObstacle`
- `pointPerPathThre`
- 路径组迟滞参数

这些方向看，而不是只靠单纯放大车体尺寸。

## 3. 这轮做过的主要探索

### 3.1 FAST-LIO 命名和离线工具整理

已经把之前容易歧义的 `official` 命名，统一往 `github` 方向收敛。  
离线文档和脚本现在更强调“工程链路检查”，而不是“公平算法对比”。

相关文件：

- `docs_ly/fast_lio/20260423_fastlio_offline_bag_recording.md`
- `tools/fast_lio_eval/run_ariadne_offline_replay.sh`
- `tools/fast_lio_eval/run_github_replay.sh`
- `tools/fast_lio_eval/run_bitbucket_replay.sh`

### 3.2 OctoMap 动态清理参数收敛到更保守但仍能清动态人的方向

当前 YAML 里采用的是一组偏保守但仍希望能处理行人快速经过的组合：

- `hit: 1.0`
- `max: 1.0`
- `min: 0.2`
- `free_observation_threshold: 6`
- `stale_time: 3.0`
- `stable_hit_threshold: 3`
- `stable_free_observation_threshold: 10`

当前理解是：

- 不希望真实静态障碍被轻易清掉
- 但也不希望快速走过的行人残留太久

### 3.3 ARIADNE 参数探索

这轮主要围绕以下参数反复实验：

- `ariadneSensorRange`
- `ariadneUtilityRangeFactor`
- `ariadneMinUtility`
- `ariadneNodeResolution`
- `ariadneWaypointThreshold`

几条当前比较明确的结论：

- `ariadneSensorRange=20` 在当前室内场景偏激进，`10` 更稳
- `node_resolution` 太小会更贴地图，但也会更重、更容易卡顿
- `waypoint_threshold` 太小虽然更严格，但也可能让高层切点显得太“拧巴”
- `1.5` 左右的 `node_resolution` 是当前一个比较实用的折中点

### 3.4 local planner 参数探索

这轮落地了三项比较关键的调整：

- `checkRotObstacle: true`
- `pointPerPathThre: 1`
- `pathGroupHoldTime: 0.8`

当前理解是：

- `checkRotObstacle=true` 之后，`vehicleLength` / `vehicleWidth` 才真正进入转向碰撞判断
- `pointPerPathThre=1` 会更保守地筛掉擦边路径
- `pathGroupHoldTime=0.8` 是为了让局部路径组别稍微更“黏”一点，减少左右来回切换

## 4. 当前较可用的室内探索参数

### 4.1 github 版本

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash

ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.3 \
  ariadneSensorRange:=10.0 \
  ariadneUtilityRangeFactor:=0.35 \
  ariadneMinUtility:=3 \
  ariadneNodeResolution:=1.5 \
  ariadneWaypointThreshold:=1.0 \
  maxSpeed:=0.50 \
  ariadnePublishGraph:=true \
  vehicleLength:=0.9 vehicleWidth:=0.8
```

### 4.2 bitbucket 版本

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install_bitbucket/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/octomap_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/ARiADNE-ROS-Planner/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash

ros2 launch vehicle_simulator system_scout_hesai_with_ariadne.launch.py \
  ariadneMapResolution:=0.3 \
  ariadneSensorRange:=10.0 \
  ariadneUtilityRangeFactor:=0.35 \
  ariadneMinUtility:=3 \
  ariadneNodeResolution:=1.5 \
  ariadneWaypointThreshold:=1.0 \
  maxSpeed:=0.50 \
  fastlioVariant:=bitbucket \
  fastlioConfig:=hesai32_nus_carter_realsenseimu.yaml \
  ariadnePublishGraph:=true \
  vehicleLength:=0.9 vehicleWidth:=0.8
```

说明：

- 这两组命令的意义是做工程效果对照，所以除了 FAST-LIO 版本和配置外，尽量保持其余参数一致
- `ariadnePublishGraph:=true` 适合排障阶段；后续如果只是演示或日常跑，可考虑关掉

## 5. 这轮最值得记住的几条代码逻辑

### 5.1 `sensor_scan` 不是原始雷达点云，它是 FAST-LIO 之后再整理出来的

关键链路是：

```text
/cloud_registered
  -> /registered_scan_raw
  -> /registered_scan
  -> /sensor_scan
  -> octomap
```

值得注意的是：

- `sensor_scan_generation` 不是做重建图，它只是把 `/registered_scan` 和 `/state_estimation` 配成一帧 `sensor_at_scan`
- 它本身不再主动做下采样
- 所以 `sensor_scan` 稀不稀，很大程度上取决于 FAST-LIO 上游发出来的 `/registered_scan`

建议重点看：

- `src/base_autonomy/sensor_scan_generation/src/sensorScanGeneration.cpp`
- `src/base_autonomy/vehicle_simulator/src/registeredScanFrameRelay.cpp`

### 5.2 `dense_publish_en` 会直接影响给 OctoMap 的点云观感

当前理解是：

- `dense_publish_en=true` 更偏向发布稠密去畸变点云
- `dense_publish_en=false` 更偏向发布降采样后的点云

这会一路影响到：

- `/registered_scan`
- `/sensor_scan`
- OctoMap 里障碍物的“厚实程度”和连续性

建议重点看：

- `fastlio_ws/src/FAST_LIO/src/laserMapping.cpp`
- `fastlio_ws/src/fast_lio_bitbucket/common/src/laserMapping.cpp`

### 5.3 ARIADNE 更新 graph 时，用的锚点不一定是真实机器人位置

这条是本轮最重要的代码理解之一。

当前流程里：

- `robot_location` 是真实里程计位置
- 但更新 graph 前，会先吸附到“最近的 graph node”
- 后面的 graph 更新、稀疏图提取、waypoint 选择，会以这个 graph node 为参考

这意味着：

- 真实机器人可能已经停在障碍前
- 但 graph 还认为自己“站在旧 node 上”
- 高层 waypoint 于是继续沿着旧结构走

建议重点看：

- `ARiADNE-ROS-Planner/src/rl_planner/rl_planner/rl_planner.py`
- `ARiADNE-ROS-Planner/src/rl_planner/rl_planner/agent.py`
- `ARiADNE-ROS-Planner/src/rl_planner/rl_planner/node_manager.py`

### 5.4 当前没有 local planner 不可达反馈回 ARIADNE 的链路

也就是说：

- local planner 可以知道当前 waypoint 不好走
- 但高层 ARIADNE 不一定因此立刻换 waypoint

这也是“waypoint 卡在障碍后面，小车左右摇摆”的关键原因之一。

### 5.5 local planner 不是标准的在线 obstacle inflation

当前更像：

- 用离线生成的候选路径集合
- 再用预生成的路径-障碍对应关系去判断哪些路径被挡住

所以：

- 平移 clearance 的核心旋钮，不完全等价于 `vehicleLength` / `vehicleWidth`
- 转向 clearance 才更直接受 `checkRotObstacle` 和车体尺寸影响

建议重点看：

- `src/base_autonomy/local_planner/src/localPlanner.cpp`
- `src/base_autonomy/local_planner/paths/path_generator.m`

### 5.6 local planner 已经有“防频繁切换”的迟滞机制

这轮新注意到 local planner 里已经有一套很值得看的机制：

- 路径组迟滞
- 路径重发抑制

也就是说，如果后面还想继续减少“左右犹豫 / 前后犹豫”，不一定要先动更高层的 ARIADNE；local planner 自己也有几颗很关键的旋钮。

当前最值得继续关注的几个参数：

- `pathGroupHoldTime`
- `pathGroupScoreRatioThre`
- `pathRepublishMinInterval`
- `pathRepublishEndpointDiffThre`

## 6. 当前结论

到今天为止，可以比较有把握地说：

1. 两版 FAST-LIO 本体都已经能稳定运行，问题重点不在“里程计彻底坏掉”
2. 当前更值得关注的是 FAST-LIO 之后到 OctoMap、ARIADNE、local planner 的工程承接
3. `ariadneSensorRange` 在室内不能盲目开大，`10` 左右更像当前合理工作点
4. ARIADNE 的 graph / waypoint 更新逻辑，本身就比 occupancy map 更抽象、更局部，不应期待它与 `/projected_map` 完全同步
5. local planner 的转向 clearance 和路径切换迟滞，是接下来进一步改善“观感”和“稳定性”的主要抓手

## 7. 后续值得继续做的事

如果后面还要继续推进，我觉得最值得的方向有四个：

1. 把 `enable_save_mode`、`next_waypoint_threshold` 等高层参数暴露到 launch
2. 给 ARIADNE 增加“当前 waypoint 不可达 / 卡住”的反馈触发
3. 继续小步调 local planner 的迟滞参数，减少演示时的左右与前后犹豫
4. 视情况把 OctoMap 的感知范围和 ARIADNE 的规划视野解耦，不再共用同一个 `sensor_range`
