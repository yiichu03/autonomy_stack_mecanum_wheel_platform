# LiDAR–IMU 外参推算记录

> **目的**：为 FAST-LIO2（`fast_lio/`，老师的 `JzHuai0108/fast_lio`，`migrate_ros2` 分支）生成
> `extrinsic_T` / `extrinsic_R` 参数，用于 Hesai XT32 + RealSense D455（BMI055 IMU）的配置文件。
>
> **原始标定文件**：`/home/liuyi/projects/thermal_nav/calibration.txt`  
> 本文档提取其中的关键数值，独立成文档，便于计算和存档。

---

## 1. 坐标系约定（来自 calibration.txt）

| 传感器 | X | Y | Z |
|--------|---|---|---|
| Hesai XT32 LiDAR | 左 | 后 | 上 |
| RealSense D455 Color/RGB | 右 | 下 | 前 |
| RealSense D455 Depth | 右 | 下 | 前 |
| 机器人底盘 base_link | 前 | 左 | 上 |

---

## 2. 已知外参（来源：calibration.txt）

### 2.1 LiDAR ← RGB Camera：`lidar_T_camera`

使用 [direct_visual_lidar_calibration](https://github.com/koide3/direct_visual_lidar_calibration) 标定。

格式：`[x, y, z, qx, qy, qz, qw]`，含义：`p_lidar = R * p_camera + t`

```
translation (t_lc):
  x: -0.02671709287258754
  y: -0.07986985425426218
  z: -0.07194136971184459

quaternion [qx, qy, qz, qw]:
  qx: -0.0025930314846405633
  qy:  0.7233645800633655
  qz: -0.6904201829671065
  qw: -0.007545293177736468
```

### 2.2 RGB Camera ← IMU（加速度计）：`color_T_accel`

来源：RealSense D455，通过 librealsense 在运行时导出。

含义：`p_color = R_ca * p_accel + t_ca`

```
rotation matrix R_ca（行主序，3×3）:
  [0.9999979734, -0.0019087758, -0.0005975506]
  [0.0019081110,  0.9999975562, -0.0011112079]
  [0.0005996702,  0.0011100655,  0.9999992251]

translation t_ca:
  x: -0.0289905090
  y: -0.0074758902
  z: -0.0158451088
```

> **注**：calibration.txt 中 `color_T_gyro` 有两条，第一条与 `color_T_accel` 相同（librealsense 导出值），
> 第二条为出厂标称值（rotation=Identity，t=[0.0302, -0.0074, -0.0160]）。
> 推算时使用第一条（实测值）。

---

## 3. 推算目标：LiDAR ← IMU（`lidar_T_accel`）

链式相乘：`T_lidar_accel = T_lidar_camera ∘ T_camera_accel`

即：
```
R_la = R_lc * R_ca
t_la = R_lc * t_ca + t_lc
```

其中：
- `R_lc`、`t_lc`：从 2.1 的四元数转成旋转矩阵
- `R_ca`、`t_ca`：直接取 2.2 的值

---

## 4. Python 计算代码

在另一台设备上运行以下代码即可得到结果：

```python
import numpy as np
from scipy.spatial.transform import Rotation

# ── lidar_T_camera（2.1）──────────────────────────────────
t_lc = np.array([-0.02671709287258754,
                 -0.07986985425426218,
                 -0.07194136971184459])

# [qx, qy, qz, qw]
q_lc = np.array([-0.0025930314846405633,
                  0.7233645800633655,
                 -0.6904201829671065,
                 -0.007545293177736468])
R_lc = Rotation.from_quat(q_lc).as_matrix()  # scipy 约定 [x,y,z,w]

# ── color_T_accel（2.2）──────────────────────────────────
R_ca = np.array([[ 0.9999979734, -0.0019087758, -0.0005975506],
                 [ 0.0019081110,  0.9999975562, -0.0011112079],
                 [ 0.0005996702,  0.0011100655,  0.9999992251]])

t_ca = np.array([-0.0289905090, -0.0074758902, -0.0158451088])

# ── 链式相乘：lidar_T_accel ──────────────────────────────
R_la = R_lc @ R_ca
t_la = R_lc @ t_ca + t_lc

print("=== lidar_T_accel (LiDAR ← IMU/accel) ===")
print(f"translation:\n  {t_la}")
print(f"rotation matrix R_la:\n{R_la}")

# ── FAST-LIO2 配置格式 ────────────────────────────────────
# FAST-LIO2 (JzHuai0108/fast_lio) extrinsic 约定：
# extrinsic_T: LiDAR origin 在 IMU 坐标系下的位置
# extrinsic_R: 从 LiDAR 坐标系到 IMU 坐标系的旋转
# 即需要 T_imu_lidar = inv(T_lidar_imu) = inv(T_lidar_accel)
R_il = R_la.T
t_il = -R_la.T @ t_la

print("\n=== For FAST-LIO2 config (IMU ← LiDAR, i.e. lidar in IMU frame) ===")
print(f"extrinsic_T: {t_il.tolist()}")
print(f"extrinsic_R (row by row): {R_il.flatten().tolist()}")
```

---

## 5. FAST-LIO2 配置文件写法（待填入计算结果）

配置文件将命名为 `hesai_xt32_scout.yaml`，放入 `fast_lio/common/config/`。

```yaml
common:
    lid_topic:  "/lidar_points"      # Hesai XT32 ROS2 driver 话题
    imu_topic:  "/camera/imu"        # RealSense D455 BMI055
    time_sync_en: false
    time_offset_lidar_to_imu: 0.0

pointcloud_fields:
    x: "x"
    y: "y"
    z: "z"
    intensity: "intensity"
    time: "timestamp"
    time_unit: "sec"
    time_is_absolute: true
    intensity_scale: 1.0

preprocess:
    lidar_type: 4                    # 4 = Hesai
    scan_line: 32                    # XT32 = 32线
    blind: 2.0

mapping:
    offline_lio_type: forward
    fwd_bwd_umeyama: true
    acc_cov: 0.01
    gyr_cov: 0.002
    b_acc_cov: 0.001
    b_gyr_cov: 0.001
    fov_degree:    360.0
    det_range:     120.0
    icp_dist_thresh: 0.9
    est_plane_thresh: 0.1
    extrinsic_est_en: false

    # 由 calibration.txt 链式推算（lidar_T_camera ∘ color_T_accel 取逆）
    extrinsic_T: [0.00369531, -0.06111665, -0.06741366]   # IMU ← LiDAR，单位 m
    extrinsic_R: [-0.9999021,  0.00615738,  0.01256278,   # 3×3 行主序
                  -0.01226984, 0.04550482, -0.99888876,
                  -0.00672221,-0.99894516, -0.04542482]

    gravity_m_s2: 9.80665
    init_pos_noise: 0.0
    init_rot_noise: 0.0
    tls_dist_thresh: 8.0

publish:
    scan_publish_en:  true
    dense_publish_en: false
    scan_bodyframe_pub_en: true
    publish_cloud_in_imu_frame: false
    output_ref_frame: lidar
    show_submap: false

pcd_save:
    pcd_save_en: false
    interval: -1
```

---

## 6. 历史沿革

| 时间 | 事件 |
|------|------|
| 2026-02-28 | 队友使用 direct_visual_lidar_calibration 完成 lidar←camera 标定，结果存入 `calibration.txt` |
| 2026-02-28 | 计算了 LiDAR-IMU 外参并写入当时的 `fastlio_ws/src/FAST_LIO/config/hesai_xt32.yaml` |
| 2026-02-28 | `calibration.txt` 路径：`/home/liuyi/projects/thermal_nav/calibration.txt` |
| 2026-03 | 切换到老师的 `JzHuai0108/fast_lio`，原 `fastlio_ws/` 删除，`hesai_xt32.yaml` 随之丢失 |
| 2026-04-10 | 本文档建立，重新整理外参推算流程 |
