"""
system_scout_hesai_with_far_planner.launch.py
=============================================
Scout Mini + Hesai XT32 + RealSense D455 + far_planner 全局路径规划 launch 文件。

在 system_scout_hesai.launch.py 的基础上加入 far_planner（全局到点规划器）。

数据流：
  RViz Goalpoint 工具 ──→ /goal_point
                                ↓
                   far_planner ←── /state_estimation, /terrain_map[_ext], /registered_scan
                                ↓
                          /way_point
                                ↓
                     localPlanner → /path → pathFollower → /cmd_vel_stamped
                                                               ↓
                          twist_stamped_to_twist → /cmd_vel (Twist)

RViz 操作说明：
  - 使用 Goalpoint 工具（RViz 插件 goalpoint_rviz_plugin，快捷键 'w'）
    点击地图上的目标位置 → 发布 /goal_point → far_planner 规划并持续发布 /way_point
  - （不要用 Waypoint 工具，那是绕过 far_planner 直接给 localPlanner 的）

使用方式：
  # 终端 A / B：PTP 时间同步（Hesai 需要）
  sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
  sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m

  # 终端 C：Hesai 驱动
  source ~/Documents/hesai_ws/install/setup.bash
  ros2 launch hesai_ros_driver start.py

  # 终端 D：RealSense 驱动（必须启用 unite_imu_method 才有 /camera/imu）
  source ~/Documents/isaac_ros_ws/install/setup.bash
  ros2 launch realsense2_camera rs_launch.py unite_imu_method:=1 enable_gyro:=true enable_accel:=true

  # 终端 E：主导航栈（在以上驱动稳定后启动）
  source /opt/ros/humble/setup.bash
  source ~/Documents/hesai_ws/install/setup.bash
  source ~/Documents/isaac_ros_ws/install/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
  ros2 launch vehicle_simulator system_scout_hesai_with_far_planner.launch.py

  # 观察：
  ros2 topic echo /way_point    # far_planner 发出的局部目标点
  ros2 topic echo /cmd_vel      # pathFollower → relay 的最终 Twist 控制命令

far_planner config 选项：
  indoor.yaml：适合室内，范围较小
  outdoor.yaml：适合室外，默认（Scout Mini 室外干跑用这个）
  可在命令行覆盖：... launch.py route_planner_config:=indoor

修改历史：
  2026-03-03  基于 system_scout_hesai.launch.py 新增 far_planner 集成
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import FrontendLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetParameter, SetRemap


def generate_launch_description():

    # ------------------------------------------------------------------ #
    #  Launch 参数
    # ------------------------------------------------------------------ #
    use_sim_time      = LaunchConfiguration('use_sim_time')
    sensorOffsetX     = LaunchConfiguration('sensorOffsetX')
    sensorOffsetY     = LaunchConfiguration('sensorOffsetY')
    cameraOffsetZ     = LaunchConfiguration('cameraOffsetZ')
    vehicleX          = LaunchConfiguration('vehicleX')
    vehicleY          = LaunchConfiguration('vehicleY')
    maxSpeed          = LaunchConfiguration('maxSpeed')
    checkTerrainConn  = LaunchConfiguration('checkTerrainConn')
    route_planner_config = LaunchConfiguration('route_planner_config')

    declare_use_sim_time        = DeclareLaunchArgument('use_sim_time',          default_value='false', description='true=bag 回放，false=实车实时')
    declare_sensorOffsetX       = DeclareLaunchArgument('sensorOffsetX',         default_value='0.0',   description='LiDAR 原点 = Body frame 原点（B_p_L=[0,0,0]），前向偏移为 0')
    declare_sensorOffsetY       = DeclareLaunchArgument('sensorOffsetY',         default_value='0.0',   description='LiDAR 相对车体中心的侧向偏移 (m)')
    declare_cameraOffsetZ       = DeclareLaunchArgument('cameraOffsetZ',         default_value='0.2',   description='传感器高度参考偏移 (m)')
    declare_vehicleX            = DeclareLaunchArgument('vehicleX',              default_value='0.0',   description='初始目标点 X')
    declare_vehicleY            = DeclareLaunchArgument('vehicleY',              default_value='0.0',   description='初始目标点 Y')
    declare_maxSpeed            = DeclareLaunchArgument('maxSpeed',              default_value='0.5',   description='最大速度 (m/s)')
    declare_checkTerrainConn    = DeclareLaunchArgument('checkTerrainConn',      default_value='true',  description='')
    declare_route_planner_config = DeclareLaunchArgument('route_planner_config', default_value='outdoor', description='far_planner 配置文件：indoor 或 outdoor')

    # ------------------------------------------------------------------ #
    #  FAST-LIO2
    # ------------------------------------------------------------------ #
    fastlio_config_path = os.path.join(
        get_package_share_directory('fast_lio'), 'config')

    start_fastlio = Node(
        package='fast_lio',
        executable='fastlio_mapping',
        name='fastlio_mapping',
        parameters=[
            os.path.join(fastlio_config_path, 'hesai_xt32.yaml'),
            {'use_sim_time': use_sim_time},
        ],
        remappings=[
            ('/Odometry',         '/state_estimation_raw'),
            ('/cloud_registered', '/registered_scan'),
        ],
        output='screen',
    )

    # odom_frame_relay：D455 body 帧 → ROS 标准帧
    start_odom_relay = Node(
        package='vehicle_simulator',
        executable='odom_frame_relay.py',
        name='odom_frame_relay',
        output='screen',
    )

    # ------------------------------------------------------------------ #
    #  Base Autonomy 导航模块
    # ------------------------------------------------------------------ #
    start_sensor_scan_generation = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('sensor_scan_generation'),
            'launch', 'sensor_scan_generation.launch')),
    )

    start_terrain_analysis = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis'),
            'launch', 'terrain_analysis.launch')),
    )

    start_terrain_analysis_ext = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis_ext'),
            'launch', 'terrain_analysis_ext.launch')),
        launch_arguments={'checkTerrainConn': checkTerrainConn}.items(),
    )

    # local_planner：GroupAction + SetRemap 把 pathFollower 的 /cmd_vel 出口
    # 重定向到 /cmd_vel_stamped，由 twist_stamped_to_twist 中继为 Twist
    #
    # Scout Mini 尺寸（Trossen 规格：612 mm × 580 mm，向上取整留安全余量）：
    #   vehicleLength：0.70 m（前后方向，612 mm → 700 mm）
    #   vehicleWidth ：0.60 m（左右方向，580 mm → 600 mm）
    start_local_planner = GroupAction([
        SetRemap('/cmd_vel', '/cmd_vel_stamped'),
        IncludeLaunchDescription(
            FrontendLaunchDescriptionSource(os.path.join(
                get_package_share_directory('local_planner'),
                'launch', 'local_planner.launch')),
            launch_arguments={
                'config':        'standard',
                'realRobot':     'false',
                'sensorOffsetX': sensorOffsetX,
                'sensorOffsetY': sensorOffsetY,
                'cameraOffsetZ': cameraOffsetZ,
                'goalX':         vehicleX,
                'goalY':         vehicleY,
                'maxSpeed':      maxSpeed,
                'twoWayDrive':   'false',
                'autonomyMode':  'false',
                'vehicleLength': '0.70',
                'vehicleWidth':  '0.60',
            }.items(),
        ),
    ])

    # TwistStamped → Twist 中继（供 Scout Mini 驱动消费）
    start_cmd_vel_relay = Node(
        package='vehicle_simulator',
        executable='twist_stamped_to_twist.py',
        name='twist_stamped_to_twist',
        output='screen',
    )

    # ------------------------------------------------------------------ #
    #  far_planner（全局路径规划器）
    #
    #  订阅：/goal_point（来自 RViz Goalpoint 工具）
    #         /state_estimation, /terrain_map_ext, /terrain_map, /registered_scan
    #  发布：/way_point（localPlanner 订阅此话题）
    #
    #  同时包含 graph_decoder（在 far_planner.launch 内部已 include）
    #
    #  注意：far_planner.launch 内部固定设置 use_sim_time=false，
    #        与实时传感器模式（use_sim_time=false）兼容；
    #        若将来需要 bag 回放 + far_planner，需修改 far_planner.launch。
    # ------------------------------------------------------------------ #
    start_far_planner = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('far_planner'),
            'launch', 'far_planner.launch')),
        launch_arguments={
            'config': route_planner_config,
        }.items(),
    )

    start_visualization_tools = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('visualization_tools'),
            'launch', 'visualization_tools.launch')),
        launch_arguments={'world_name': 'real_world'}.items(),
    )

    # RViz：加载导航栈专用配置（含 Waypoint/Goalpoint 插件）
    start_rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(
            get_package_share_directory('vehicle_simulator'),
            'rviz', 'vehicle_simulator.rviz')],
        output='screen',
    )

    # ------------------------------------------------------------------ #
    #  TF 桥接
    # ------------------------------------------------------------------ #
    tf_map_to_camera_init = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_map_to_camera_init',
        arguments=['0', '0', '0', '0', '0', '0', '1', 'map', 'camera_init'],
    )

    tf_body_to_sensor = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_body_to_sensor',
        arguments=['0', '0', '0', '0.5', '-0.5', '0.5', '0.5', 'body', 'sensor'],
    )

    tf_sensor_at_scan_to_vehicle = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_sensor_at_scan_to_vehicle',
        arguments=['0', '0', '0', '0', '0', '0', '1', 'sensor_at_scan', 'vehicle'],
    )

    # ------------------------------------------------------------------ #
    #  组装 LaunchDescription
    # ------------------------------------------------------------------ #
    ld = LaunchDescription()

    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_sensorOffsetX)
    ld.add_action(declare_sensorOffsetY)
    ld.add_action(declare_cameraOffsetZ)
    ld.add_action(declare_vehicleX)
    ld.add_action(declare_vehicleY)
    ld.add_action(declare_maxSpeed)
    ld.add_action(declare_checkTerrainConn)
    ld.add_action(declare_route_planner_config)

    ld.add_action(SetParameter(name='use_sim_time', value=use_sim_time))

    ld.add_action(tf_map_to_camera_init)
    ld.add_action(tf_body_to_sensor)
    ld.add_action(tf_sensor_at_scan_to_vehicle)
    ld.add_action(start_fastlio)
    ld.add_action(start_odom_relay)
    ld.add_action(start_sensor_scan_generation)
    ld.add_action(start_terrain_analysis)
    ld.add_action(start_terrain_analysis_ext)
    ld.add_action(start_local_planner)
    ld.add_action(start_cmd_vel_relay)
    ld.add_action(start_far_planner)
    ld.add_action(start_visualization_tools)
    ld.add_action(start_rviz)

    return ld
