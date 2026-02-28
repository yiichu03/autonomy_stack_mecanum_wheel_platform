# readme_ly（排版整理）
说明：保留原始内容，仅做格式整理（空白、分段、代码块）。

## FAST-LIO2 离线回放（两终端）
终端 1：

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py config_file:=hesai_xt32.yaml use_sim_time:=true rviz:=true
```

终端 2（等终端 1 出现 Successfully start! 后）：

```bash
source /opt/ros/humble/setup.bash
ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
```

## Phase C：离线验证步骤
终端 1 — 启动导航栈

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true
```

终端 2 — 回放 bag（等终端 1 所有节点起来后再播）

```bash
source /opt/ros/humble/setup.bash
ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
```

  ---
  RViz 中应该看到什么（验收标准）

  ┌────────────────────────────┬───────────────────────────────────────────────┐
  │           检查项           │                   正常现象                    │
  ├────────────────────────────┼───────────────────────────────────────────────┤
  │ /state_estimation_at_scan  │ 有数据发布（sensor_scan_generation 正常同步） │
  ├────────────────────────────┼───────────────────────────────────────────────┤
  │ /sensor_scan (PointCloud2) │ 随时间更新的点云                              │
  ├────────────────────────────┼───────────────────────────────────────────────┤
  │ /terrain_map               │ 有彩色地图（可通行 = 绿，障碍 = 红）          │
  ├────────────────────────────┼───────────────────────────────────────────────┤
  │ /free_paths (PointCloud2)  │ 一组向前扩展的候选路径点                      │
  ├────────────────────────────┼───────────────────────────────────────────────┤
  │ 轨迹 /path                 │ FAST-LIO2 轨迹持续延伸                        │
  └────────────────────────────┴───────────────────────────────────────────────┘

  ---
  已知限制（Phase C 可接受，Phase D 需修复）

  1. vehicleLength/Width = 0.5m（local_planner.launch 硬编码），Scout Mini 实际 0.93×0.70m。
  离线测试影响不大（避障裕量偏窄），但上车前需要修正。
  2. TwistStamped → Twist relay 缺失：pathFollower 发布 TwistStamped 到 /cmd_vel，Scout Mini ROS驱动接收 Twist。Phase D 上车时需要加一个 relay 节点。

  ---
  如果 RViz 里 /terrain_map 有内容并且 /free_paths 出现了路径候选，说明 Phase C 通过。接下来的关键步骤是修正 vehicleLength/Width 并添加 TwistStamped→Twist
  relay，然后进入 Phase D 实车测试。

## RViz 启动与显示项
visualization_tools.launch 只启动了一个后台数据节点，并不会打开 RViz。RViz 需要单独启动。已经有一个现成的配置文件 vehicle_simulator.rviz，用第三个终端打开它：

终端 3 — 手动启动 RViz

```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash

ros2 run rviz2 rviz2 -d \
~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz
```

  RViz 启动后，在 Global Options 里把 Fixed Frame 改为 map（FAST-LIO2 的世界坐标系），然后手动添加以下 Display（如果配置文件里没有）：

  ┌───────────────────┬─────────────┬──────────────────┐
  │       Topic       │    类型     │       用途       │
  ├───────────────────┼─────────────┼──────────────────┤
  │ /sensor_scan      │ PointCloud2 │ 对齐后的点云     │
  ├───────────────────┼─────────────┼──────────────────┤
  │ /terrain_map      │ PointCloud2 │ 地形可通行性     │
  ├───────────────────┼─────────────┼──────────────────┤
  │ /free_paths       │ PointCloud2 │ 局部规划候选路径 │
  ├───────────────────┼─────────────┼──────────────────┤
  │ /state_estimation │ Odometry    │ 位姿轨迹         │
  └───────────────────┴─────────────┴──────────────────┘

  如果 RViz 打开后什么都没有，先检查终端 1 的输出有没有报错，把报错内容贴给我。

编译成功（symlink install，所以几乎是瞬间完成）。

  ---
  现在重新运行 Phase C，TF 树将变为：

  map ──(identity,static)──▶ camera_init ──(dynamic,FAST-LIO2)──▶ body
                                                                     │
                                                              (identity,static)
                                                                     ▼
                                                                  sensor
                                                                 /      \
                                                    (local_planner)  (local_planner)
                                                            ▼              ▼
                                                         vehicle         camera

## 重新运行 Phase C（修复后）
操作步骤

终端 1 — 重新启动（先 Ctrl+C 停掉旧的）

```bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true
```

终端 2 — 重新播 bag

```bash
ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
```

终端 3 — RViz（Fixed Frame 设为 map）

```bash
ros2 run rviz2 rviz2 -d \
~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz
```

  RViz 里手动把 Fixed Frame 改为 map，然后添加 /free_paths（PointCloud2）。此时 vehicle 帧能通过 body → sensor → vehicle 链路变换到 map，/free_paths 应该可以显示了。

## /free_paths 的表现形式

  在 RViz 里是一把从机器人当前位置向外辐射的"扇形点云"，每条射线代表一个候选行驶方向：

          前
      . . . . . . .
     . . . . . . . .
    . . . . . . . . .
       \   |   /
        \  |  /
         [robot]

  - 点越密、范围越大 → 该方向可以通行
  - 某个方向的点被截断/缺失 → 该方向有障碍物
  - 颜色通常按高度或 intensity 渲染（橙/绿/白都正常，取决于 RViz 配置）

  如果环境里有明显障碍，扇形会在障碍方向上被"切掉"一块。

  ---
  Phase C 在验证什么

  Phase C 是不上车的流水线贯通测试，目的是确认从 LiDAR 数据到规划输出的每个环节都能正常运行：

  bag(lidar + imu)
      │
      ▼
  FAST-LIO2          → /state_estimation (位姿)
                     → /registered_scan  (配准点云)
      │
      ▼
  sensor_scan_generation  → /sensor_scan (时间对齐的点云)
      │
      ▼
  terrain_analysis        → /terrain_map (可通行性地图)
      │
      ▼
  local_planner           → /free_paths  (候选路径扇形)
                          → /cmd_vel     (速度指令，但没有小车所以忽略)

  验收标准：

  ┌───────────────────┬────────────────────────────────────────┐
  │       话题        │                验收条件                │
  ├───────────────────┼────────────────────────────────────────┤
  │ /terrain_map      │ 有彩色地图，地面绿色，障碍红色         │
  ├───────────────────┼────────────────────────────────────────┤
  │ /free_paths       │ 有扇形射线从机器人位置辐射出去         │
  ├───────────────────┼────────────────────────────────────────┤
  │ /state_estimation │ 轨迹随时间延伸，形状合理（不漂移乱跳） │
  └───────────────────┴────────────────────────────────────────┘

  通过 Phase C = 软件栈在逻辑上是通的，可以进入实车阶段。

  ---
  下一步（Phase D 上车前的两个必要准备）

  准备 1：修正车体尺寸

  local_planner.launch 里 vehicleLength/Width 硬编码为 0.5m，但 Scout Mini 是 0.93×0.70m，碰撞检测裕量会偏窄。需要把 localPlanner 和 pathFollower 从
  IncludeLaunchDescription 改成直接以 Node 方式启动，这样可以传入正确尺寸。

  准备 2：TwistStamped → Twist relay

  pathFollower 发布的 /cmd_vel 是 TwistStamped，但 Scout Mini 的 ROS 驱动接收 Twist。需要写一个小的 relay 节点做类型转换。这是上车运动的最后一块拼图。

  完成这两步后就可以进行 Phase D 实车低速验证。

  当前先把 Phase C 跑通（能看到 /free_paths），告诉我结果。

## 坐标系问题分析（对话记录）
那我觉得现在可能坐标系之类的有有些问题，目前rviz里面一个坐标系在走，应该是代表小车，蓝色指向小车前方，红色指向小车右方，绿色指向小车下方。黄色的有时候扇形有时
  候半圆，间接性出现，不是一直在的很多线应该是你说的 free path，它是分布在红色绿色的2维平面里的，如果按照你说的意义，它应该在蓝红组成的二维平面才对吧。

● 分析你看到的内容

  黄色扇形/半圆 = free_paths，说明规划器在运行，这是好消息。但它出现在"红绿平面"（右-下平面）而不是"蓝红平面"（前-右水平面），这揭示了一个坐标系问题。

  ---
  坐标系问题：D455 IMU 帧与 ROS 标准帧不兼容

  你描述的移动坐标系：
  蓝(Z) = 前方    → D455 深度摄像头的光轴方向
  红(X) = 右方    → D455 的 X 轴
  绿(Y) = 下方    → D455 的 Y 轴（光学惯例，Y 朝下）

  FAST-LIO2 的 body 帧 = D455 IMU 的物理帧（光学惯例，Z=前）
  autonomy_stack 期望的车体帧 = ROS 标准（X=前，Y=左，Z=上）

  两者差了一个 90° 旋转。localPlanner 从里程计提取 yaw 时，以为 body.X（右方）是机器人"前进方向"，所以规划出来的路径旋转了
  90°，落在了"右-下"垂直面上，而不是水平面上。

  ---
  Phase C 验收结论

  ┌──────────────────────────────────────────────────────┬──────┬──────────────────────────────────┐
  │                         项目                         │ 状态 │               说明               │
  ├──────────────────────────────────────────────────────┼──────┼──────────────────────────────────┤
  │ 数据从 LiDAR → FAST-LIO2 → sensor_scan → terrain_map │ ✅   │ terrain_map 有显示，流水线贯通   │
  ├──────────────────────────────────────────────────────┼──────┼──────────────────────────────────┤
  │ free_paths 有数据产生                                │ ✅   │ 黄色扇形存在，规划器在运行       │
  ├──────────────────────────────────────────────────────┼──────┼──────────────────────────────────┤
  │ free_paths 方向正确                                  │ ❌   │ 坐标系不对齐，在垂直面而非水平面 │
  ├──────────────────────────────────────────────────────┼──────┼──────────────────────────────────┤
  │ 位姿估计（轨迹）正确                                 │ ✅   │ 轨迹在走                         │
  └──────────────────────────────────────────────────────┴──────┴──────────────────────────────────┘

  Phase C 结论：流水线连通性验证通过。 坐标系问题属于已知缺陷，需要在 Phase D 上车前修复。

  ---
  下一步：修复坐标系对齐

  需要做两件事：

  1. 修正 body → sensor 静态 TF（让 RViz 显示正确）
  当前是 identity，实际需要加一个旋转，把 D455 帧（Z=前，X=右，Y=下）旋转到 ROS 标准帧（X=前，Y=左，Z=上）：

  body(Z=前,X=右,Y=下) → sensor(X=前,Y=左,Z=上)
  旋转四元数 (qx,qy,qz,qw) = (0.5, -0.5, 0.5, 0.5)

  2. 修正里程计方向（让 localPlanner yaw 正确）
  FAST-LIO2 发布的里程计四元数是 body 帧方向，localPlanner 提取 yaw 时假设 X=前。需要一个小的 relay 节点，在转发 /state_estimation 时把四元数右乘这个旋转修正量。

  ---
  要不要我现在就帮你实现这两个修复？修复后 free_paths 应该出现在水平面（蓝红平面）上，并正确指向机器人前方。

## 修复请求与执行记录
请你帮我修复。

● Read 2 files (ctrl+o to expand)

● 好，计划：
  1. 写 odom_frame_relay.py（里程计方向修正节点）
  2. 更新 CMakeLists.txt（安装 Python 脚本）
  3. 更新 system_scout_hesai.launch.py（修正 TF 旋转 + 接入 relay 节点）

● Bash(mkdir -p /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/scripts)
  ⎿  Done

● Write(src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py)
  ⎿  Wrote 87 lines to src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py
      1 #!/usr/bin/env python3
      2 """
      3 odom_frame_relay.py
      4 ===================
      5 将 FAST-LIO2 输出的里程计（body 帧，D455 光学惯例）转换为 ROS 标准帧，
      6 再发布给 autonomy_stack 使用。
      7
      8 D455 IMU / FAST-LIO2 body 帧：X=右, Y=下, Z=前
      9 ROS 标准车体帧（autonomy_stack 期望）：X=前, Y=左, Z=上
     … +77 lines (ctrl+o to expand)

● Bash(chmod +x /home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/scripts/odom_frame_relay.py)
  ⎿  Done

● Now add the script install to CMakeLists.txt:

● Update(src/base_autonomy/vehicle_simulator/CMakeLists.txt)
  ⎿  File must be read first

● Read 1 file (ctrl+o to expand)

● Update(src/base_autonomy/vehicle_simulator/CMakeLists.txt)
  ⎿  Added 5 lines
      53    sim_image_repub
      54    DESTINATION lib/${PROJECT_NAME})
      55
      56 +install(PROGRAMS
      57 +  scripts/odom_frame_relay.py
      58 +  DESTINATION lib/${PROJECT_NAME}
      59 +)
      60 +
      61  install(
      62    DIRECTORY
      63    launch

● Now update the launch file — three changes: (a) remap FAST-LIO2 to state_estimation_raw, (b) add relay node, (c) fix body→sensor TF quaternion:

● Read 1 file (ctrl+o to expand)

● 需要修改三处：(1) FAST-LIO2 remap 改为 state_estimation_raw，(2) 加入 relay 节点，(3) 修正 body→sensor TF 四元数。

● Update(src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py)
  ⎿  Added 3 lines, removed 2 lines
       4  Scout Mini + Hesai XT32 + RealSense D455 IMU 专用 launch 文件。
       5
       6  架构：
       7 -  FAST-LIO2 (fastlio_ws)  →  remap  →  autonomy_stack navigation modules
       8 -    /Odometry               →  /state_estimation
       7 +  FAST-LIO2 (fastlio_ws)  →  remap  →  odom_frame_relay  →  autonomy_stack
       8 +    /Odometry               →  /state_estimation_raw
       9      /cloud_registered       →  /registered_scan
      10 +  odom_frame_relay：修正里程计方向（D455 body 帧 → ROS 标准帧）→ /state_estimation
      11
      12  使用方式：
      13    # 阶段 C：离线验证（bag 回放，不接底盘）

● Update(src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py)
  ⎿  Added 13 lines, removed 3 lines
      69      #  前提：fastlio_ws 的 install/setup.bash 已 source
      70      #
      71      #  话题重映射：
      72 -    #    /Odometry         → /state_estimation   (nav_msgs/Odometry)
      73 -    #    /cloud_registered → /registered_scan    (sensor_msgs/PointCloud2)
      72 +    #    /Odometry         → /state_estimation_raw  (经 odom_frame_relay 修正后再发 /state_estimation)
      73 +    #    /cloud_registered → /registered_scan        (sensor_msgs/PointCloud2)
      74      # ------------------------------------------------------------------ #
      75      fastlio_config_path = os.path.join(
      76          get_package_share_directory('fast_lio'), 'config')
     ...
       84              {'use_sim_time': use_sim_time},
       85          ],
       86          remappings=[
       87 -            ('/Odometry',         '/state_estimation'),
       87 +            ('/Odometry',         '/state_estimation_raw'),
       88              ('/cloud_registered', '/registered_scan'),
       89          ],
       90          output='screen',
       91      )
       92
       93 +    # odom_frame_relay：修正里程计坐标系方向
       94 +    #   D455 body 帧（Z=前，X=右，Y=下）→ ROS 标准帧（X=前，Y=左，Z=上）
       95 +    #   q_corrected = q_fastlio ⊗ (0.5, -0.5, 0.5, 0.5)
       96 +    start_odom_relay = Node(
       97 +        package='vehicle_simulator',
       98 +        executable='odom_frame_relay.py',
       99 +        name='odom_frame_relay',
      100 +        output='screen',
      101 +    )
      102 +
      103      # ------------------------------------------------------------------ #
      104      #  autonomy_stack 导航模块
      105      # ------------------------------------------------------------------ #

● Update(src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py)
  ⎿  Added 6 lines, removed 5 lines
      169      #  缺失的连接：
      170      #    1. map ← camera_init：FAST-LIO2 用 camera_init 作为世界帧，
      171      #       autonomy_stack 用 map，二者等价，发布 identity TF 桥接
      172 -    #    2. body → sensor：FAST-LIO2 的机体帧 = IMU 帧，
      173 -    #       autonomy_stack 的 sensor 帧 = LiDAR 帧，
      174 -    #       此处用 identity 近似（真实偏移 < 10cm，可视化足够）
      172 +    #    2. body → sensor：将 D455 body 帧（Z=前，X=右，Y=下）旋转到
      173 +    #       autonomy_stack 期望的 sensor 帧（X=前，Y=左，Z=上）
      174 +    #       旋转四元数 (qx,qy,qz,qw) = (0.5, -0.5, 0.5, 0.5)
      175 +    #       验证：body.Z(前)→sensor.X ✓  body.X(右)→sensor.(-Y) ✓  body.Y(下)→sensor.(-Z) ✓
      176      # ------------------------------------------------------------------ #
      177      tf_map_to_camera_init = Node(
      178          package='tf2_ros',
      179          executable='static_transform_publisher',
      180          name='tf_map_to_camera_init',
      180 -        arguments=['0', '0', '0', '0', '0', '0', 'map', 'camera_init'],
      181 +        arguments=['0', '0', '0', '0', '0', '0', '1', 'map', 'camera_init'],
      182      )
      183
      184      tf_body_to_sensor = Node(
      185          package='tf2_ros',
      186          executable='static_transform_publisher',
      187          name='tf_body_to_sensor',
      187 -        arguments=['0', '0', '0', '0', '0', '0', 'body', 'sensor'],
      188 +        arguments=['0', '0', '0', '0.5', '-0.5', '0.5', '0.5', 'body', 'sensor'],
      189      )
      190
      191      # ------------------------------------------------------------------ #

● Now add the relay node to the LaunchDescription:

● Update(src/base_autonomy/vehicle_simulator/launch/system_scout_hesai.launch.py)
  ⎿  Added 1 line
      208      ld.add_action(tf_map_to_camera_init)
      209      ld.add_action(tf_body_to_sensor)
      210      ld.add_action(start_fastlio)
      211 +    ld.add_action(start_odom_relay)
      212      ld.add_action(start_sensor_scan_generation)
      213      ld.add_action(start_terrain_analysis)
      214      ld.add_action(start_terrain_analysis_ext)

● Now build and verify the final launch file:

● Bash(colcon build --symlink-install --packages-select vehicle_simulator 2>&1 | tail -8)
  ⎿  Starting >>> vehicle_simulator
     --- stderr: vehicle_simulator
     ** WARNING ** io features related to pcap will be disabled
     … +5 lines (ctrl+o to expand)

● Read 1 file (ctrl+o to expand)

● 结构正确。编译已成功。现在重新运行 Phase C：

  ---
  运行步骤（三个终端）

  终端 1（先启动）：
```bash
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true
```

  终端 2（等日志里出现 odom_frame_relay started 后播 bag）：
```bash
ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
```

  终端 3（RViz，Fixed Frame 设 map）：
```bash
ros2 run rviz2 rviz2 -d \
~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz
```

  ---
  修复后应该看到什么

  ┌────────────────────────────────────────────────┬─────────────────────────────────────────────────────┐
  │                      之前                      │                       修复后                        │
  ├────────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ 移动坐标系：蓝=前，红=右，绿=下（D455 光学帧） │ 移动坐标系：红=前，绿=左，蓝=上（ROS 标准帧）       │
  ├────────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
  │ free_paths 在红绿垂直面                        │ free_paths 在水平面（红蓝平面），从机器人向前方辐射 │
  └────────────────────────────────────────────────┴─────────────────────────────────────────────────────┘

  如果坐标系方向还是不对，把终端 1 里看到的 odom_frame_relay 那一行日志贴给我，我再判断。

✻ Worked for 3m 31s
