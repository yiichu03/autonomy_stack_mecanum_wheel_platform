终端 1：  source /opt/ros/humble/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
  ros2 launch fast_lio mapping.launch.py config_file:=hesai_xt32.yaml use_sim_time:=true rviz:=true
                                                                                                                                                                     
  终端 2（等终端 1 出现 Successfully start! 后）：
  source /opt/ros/humble/setup.bash
  ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock
  
  
  
  
# Phase C：离线验证步骤
  终端 1 — 启动导航栈
                                                                                                                                                                     
source /opt/ros/humble/setup.bash
source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash  source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true
 
 
 终端 2 — 回放 bag（等终端 1 所有节点起来后再播）

  source /opt/ros/humble/setup.bash
  ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock

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
  
  
visualization_tools.launch 只启动了一个后台数据节点，并不会打开 RViz。RViz 需要单独启动。已经有一个现成的配置文件 vehicle_simulator.rviz，用第三个终端打开它：     
                                                            
  终端 3 — 手动启动 RViz                                                                                                                                             
                                                                                                                                                                     
  source /opt/ros/humble/setup.bash                                                                                                                                  
  source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash                                                             
                                                            
  ros2 run rviz2 rviz2 -d
  ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz

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

  操作步骤

  终端 1 — 重新启动（先 Ctrl+C 停掉旧的）
  ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true

  终端 2 — 重新播 bag
  ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock

  终端 3 — RViz（Fixed Frame 设为 map）
  ros2 run rviz2 rviz2 -d
  ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz

  RViz 里手动把 Fixed Frame 改为 map，然后添加 /free_paths（PointCloud2）。此时 vehicle 帧能通过 body → sensor → vehicle 链路变换到 map，/free_paths 应该可以显示了。







































  
