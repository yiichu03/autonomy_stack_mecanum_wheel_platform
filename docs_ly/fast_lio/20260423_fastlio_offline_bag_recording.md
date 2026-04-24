# FAST-LIO 离线回放：github / bitbucket 与 OctoMap 承接检查

日期：2026-04-23

## 当前目标

这轮离线回放的重点不是做“公平算法对比”，而是做工程链路检查：

- `github` 版本和 `bitbucket` 版本的 FAST-LIO 都已经能正常启动
- 从当前轨迹结果看，两边里程计本身也没有明显问题
- 现在真正想确认的是：**FAST-LIO 的点云和位姿输出，能不能被后面的 relay / `sensor_scan_generation` / OctoMap / ARiADNE 稳定承接**

当前最关心的链路是：

```text
/Odometry
  -> /state_estimation_raw
  -> /state_estimation

/cloud_registered
  -> /registered_scan_raw
  -> /registered_scan
  -> /sensor_scan
  -> dynamic_octomap_server
```

也就是说，离线回放主要用来判断：

- 两个版本在 FAST-LIO 自身输出上是否都正常
- 哪个环节开始出现“有点云但后面没有形成障碍物”

## 原始 bag 约定

原始传感器 bag 统一放在：

```bash
/home/rho/Documents/data/lio_eval/bags/
```

当前只录最小必要输入：

```bash
/lidar_points
/camera/imu
```

不要把 `/Odometry`、`/cloud_registered`、`/path` 混进原始 bag。

当前建议继续使用这几类场景：

- `static_1min`
- `longer_try1`
- `obstacle_approach`

## 当前输入质量的理解

当前这批 bag 更适合做**相对工程对比**，不适合拿来证明系统已经跑在最佳输入条件下。

原因很简单：

- 当前工程里对 Hesai XT32 的参考频率仍然是约 `10 Hz`
- 但现有 bag 里的 `/lidar_points` 实测更接近 `4 Hz`

所以这批数据可以回答：

- `github` 和 `bitbucket` 在**同一份输入**上，谁更容易把后续链路喂通

但不能直接回答：

- 当前整套实车输入链路是不是已经最佳

## 建议的离线工作流

### 1. 优先用“完整链路回放”看 OctoMap 承接

这是当前最推荐的方式。

脚本：

```bash
/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_ariadne_offline_replay.sh
```

它会做的事：

- source 对应 workspace
- 启动当前工程里的 `system_scout_hesai_with_ariadne.launch.py`
- 自动设置 `use_sim_time:=true`
- 自动播放原始 bag
- 让你直接在 RViz 里看 `registered_scan`、`sensor_scan`、OctoMap 和 ARiADNE 的效果
- 保存 `launch.log` 和 `play.log`

### github 版本

```bash
bash /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_ariadne_offline_replay.sh \
  github \
  /home/rho/Documents/data/lio_eval/bags/obstacle_approach
```

### bitbucket 版本

默认会对齐你当前在线实验里常用的配置 `hesai32_nus_carter_realsenseimu.yaml`：

```bash
bash /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_ariadne_offline_replay.sh \
  bitbucket \
  /home/rho/Documents/data/lio_eval/bags/obstacle_approach
```

如果你想显式指定配置文件，也可以传第三个参数：

```bash
bash /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_ariadne_offline_replay.sh \
  bitbucket \
  /home/rho/Documents/data/lio_eval/bags/obstacle_approach \
  hesai32_nus_carter_realsenseimu.yaml
```

结果目录示例：

```bash
/home/rho/Documents/data/lio_eval/results/obstacle_approach/github_ariadne/
/home/rho/Documents/data/lio_eval/results/obstacle_approach/bitbucket_ariadne/
```

这一层回放默认**不额外录 FAST-LIO 输出 bag**，因为当前大多数迭代只是想快速看：

- `/registered_scan` 有没有正常
- `/sensor_scan` 有没有正常
- OctoMap 有没有障碍

### 2. 需要留存 FAST-LIO 输出时，再跑“算法输出录包”

如果你想把 FAST-LIO 自己的输出保存下来，后面做复盘、轨迹图或双版本回放叠加，再用下面这组脚本：

- `run_github_replay.sh`
- `run_bitbucket_replay.sh`
- `run_pair_compare.sh`

它们会录：

```bash
/Odometry
/cloud_registered
/path
```

输出目录改成：

```bash
/home/rho/Documents/data/lio_eval/results/<bag_name>/github/
/home/rho/Documents/data/lio_eval/results/<bag_name>/bitbucket/
```

示例：

```bash
bash /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_github_replay.sh \
  /home/rho/Documents/data/lio_eval/bags/obstacle_approach

bash /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/run_bitbucket_replay.sh \
  /home/rho/Documents/data/lio_eval/bags/obstacle_approach
```

### 3. 只想看轨迹时，用轻量后处理

如果你只想快速导出 odom 轨迹，不想自己翻 bag：

```bash
python3 /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/tools/fast_lio_eval/analyze_odometry_results.py \
  /home/rho/Documents/data/lio_eval/results/obstacle_approach
```

主要输出：

- `github_odom.csv`
- `bitbucket_odom.csv`
- `github_xz.png`
- `bitbucket_xz.png`
- `github_vs_bitbucket_xz.png`
- `github_vs_bitbucket_z_time.png`
- `summary.md`

## 这轮离线回放怎么判断

当前建议先按下面顺序看：

1. `github` 完整链路离线回放
2. `bitbucket` 完整链路离线回放
3. 对比 RViz 里的：
   - `/registered_scan`
   - `/sensor_scan`
   - OctoMap 障碍物
4. 再回头看日志：
   - FAST-LIO 日志
   - relay / `sensor_scan_generation` 日志
   - OctoMap 日志

## 当前最值得盯的故障点

如果 FAST-LIO 轨迹正常，但 OctoMap 不稳定，优先怀疑下面几层，而不是先怀疑 LIO 核心：

- `/registered_scan_raw -> /registered_scan` 的 frame 处理
- `/state_estimation -> /registered_scan` 在 `sensor_scan_generation` 里的同步
- `/sensor_scan` 是否真的稳定发布
- OctoMap 的 `base_frame_id`、高度裁剪和占据更新参数

尤其要注意：

- `sensor_scan_generation` 依赖 `/state_estimation` 和 `/registered_scan` 的近似时间同步
- 它这里如果同步不上，就会出现“上游看起来有点云，但 `/sensor_scan` 没正常出来”
- 这类问题非常像你现在描述的现象

## 结论

当前这份离线回放方案应该收敛成两件事：

- 用 `github / bitbucket` 两套配置，在**同一份原始 bag** 上检查完整链路
- 优先定位“FAST-LIO 输出到 OctoMap 承接”这一段，而不是继续把重点放在轨迹算法本身
