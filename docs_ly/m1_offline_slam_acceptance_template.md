# 里程碑 M1：FAST-LIO 离线验收清单（可直接提交）

适用目标：验证 `LiDAR + IMU` 数据链路可稳定产出 `/Odometry` 与 `/cloud_registered`，作为后续导航对接前提。  
项目：`autonomy_stack_mecanum_wheel_platform` on Scout Mini + Hesai XT32 + D455 IMU

---

## 1. 基本信息（先填写）

1. 测试日期：`____`
2. 测试人：`____`
3. 机器：`AGX Orin / Ubuntu 22.04 / ROS2 Humble`
4. FAST-LIO 配置文件：`~/Documents/liuyi/projects/thermal_nav/fastlio_ws/src/FAST_LIO/config/hesai_xt32.yaml`
5. 测试 bag：`/home/rho/Documents/data/<run_name>/rosbag`

---

## 2. 预检查（证据 1）

执行并保存输出：

```bash
ros2 bag info /home/rho/Documents/data/<run_name>/rosbag | tee m1_bag_info.txt
```

通过标准：

1. 包含话题 `/lidar_points`、`/camera/imu`
2. 两个话题 `Count > 0`
3. 录制时长满足预期（建议 >= 60s）

结论：`通过 / 不通过`

---

## 3. 复现步骤（命令留档）

### 终端 A：启动 FAST-LIO（先启动）

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py \
  config_file:=hesai_xt32.yaml \
  use_sim_time:=true \
  rviz:=true 2>&1 | tee m1_fastlio.log
```

### 终端 B：回放 bag

```bash
source /opt/ros/humble/setup.bash
ros2 bag play /home/rho/Documents/data/<run_name>/rosbag --clock
```

### 终端 C：话题频率检查

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /Odometry | tee m1_hz_odometry.txt
ros2 topic hz /cloud_registered | tee m1_hz_cloud_registered.txt
```

提示：每条 `hz` 建议观察至少 30 秒再 `Ctrl+C`。

---

## 4. RViz 截图要求（证据 2）

`Fixed Frame` 建议设为：`camera_init`（与 FAST-LIO 输出一致）。  
建议至少提交 4 张图：

1. `S1-Start`：刚开始 5~10 秒的全局视图（轨迹 + 点云）
2. `S2-Mid`：中段（转弯/运动变化位置）视图
3. `S3-End`：回放结束时全局视图
4. `S4-Zoom`：局部放大图（看轨迹是否连续、有无跳变）

截图命名建议：

1. `m1_s1_start.png`
2. `m1_s2_mid.png`
3. `m1_s3_end.png`
4. `m1_s4_zoom.png`

---

## 5. 日志检查（证据 3）

检查是否存在持续同步报错：

```bash
grep -n "IMU and LiDAR not Synced" m1_fastlio.log | tee m1_sync_warn.txt
```

判定规则：

1. 若仅启动初期偶发 1~2 次，可记为“可接受但需关注”
2. 若贯穿运行持续出现，判为“不通过”

---

## 6. 验收判定表（必须填写）

1. `/Odometry` 是否持续发布且无中断：`是 / 否`
2. `/cloud_registered` 是否持续发布且无中断：`是 / 否`
3. 轨迹是否连续、无明显瞬时跳变：`是 / 否`
4. 是否无持续性 `IMU and LiDAR not Synced`：`是 / 否`

最终结论：

1. `M1 通过`（四项均“是”）
2. `M1 不通过`（任一项“否”）

---

## 7. 失败定位建议（不通过时）

1. 若 `/Odometry` 或 `/cloud_registered` 频率异常：
   先查 `hesai_xt32.yaml` 的 `common.lid_topic`、`common.imu_topic` 与实际话题是否一致。
2. 若出现持续同步告警：
   检查采集时钟链路（PTP/phc2sys）和 IMU/LiDAR 时间基准是否一致。
3. 若轨迹跳变：
   优先检查外参 `mapping.extrinsic_T/R`，再检查 IMU 噪声参数。

---

## 8. 提交材料清单（给老师/其他 AI）

1. `m1_bag_info.txt`
2. `m1_hz_odometry.txt`
3. `m1_hz_cloud_registered.txt`
4. `m1_fastlio.log`
5. `m1_sync_warn.txt`
6. 4 张 RViz 截图（S1~S4）
7. 本清单填写后的版本（含“通过/不通过”结论）

