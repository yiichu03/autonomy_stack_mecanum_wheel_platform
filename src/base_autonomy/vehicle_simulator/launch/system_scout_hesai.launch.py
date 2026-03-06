"""
system_scout_hesai.launch.py
============================
Scout Mini + Hesai XT32 + RealSense D455 IMU 专用 launch 文件。

架构：
  FAST-LIO2 (fastlio_ws)  →  remap  →  odom_frame_relay  →  autonomy_stack
    /Odometry               →  /state_estimation_raw
    /cloud_registered       →  /registered_scan
  odom_frame_relay：修正里程计方向（D455 body 帧 → ROS 标准帧）→ /state_estimation

使用方式：
  # 阶段 C：离线验证（bag 回放，不接底盘）
  # 终端 1（先启动）：
  source /opt/ros/humble/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
  ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=true

  # 终端 2（等终端 1 就绪后）：
  ros2 bag play /home/rho/Documents/data/run_20260228_194305/rosbag --clock

  # 阶段 D：上车实跑（实时，不用 bag）
  ros2 launch vehicle_simulator system_scout_hesai.launch.py use_sim_time:=false

  # 可调参数示例：
  ros2 launch vehicle_simulator system_scout_hesai.launch.py \\
    use_sim_time:=false maxSpeed:=0.3 sensorOffsetX:=0.1

修改历史：
  2026-02-28  初始版本（阶段 C 离线验证用）
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import FrontendLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter, SetRemap


def generate_launch_description():

    # ------------------------------------------------------------------ #
    #  Launch 参数
    # ------------------------------------------------------------------ #
    use_sim_time    = LaunchConfiguration('use_sim_time')
    sensorOffsetX   = LaunchConfiguration('sensorOffsetX')
    sensorOffsetY   = LaunchConfiguration('sensorOffsetY')
    cameraOffsetZ   = LaunchConfiguration('cameraOffsetZ')
    vehicleX        = LaunchConfiguration('vehicleX')
    vehicleY        = LaunchConfiguration('vehicleY')
    maxSpeed        = LaunchConfiguration('maxSpeed')
    checkTerrainConn = LaunchConfiguration('checkTerrainConn')

    declare_use_sim_time      = DeclareLaunchArgument('use_sim_time',      default_value='false',  description='true=bag 回放，false=实车实时')
    declare_sensorOffsetX     = DeclareLaunchArgument('sensorOffsetX',     default_value='0.0',    description='LiDAR 原点 = Body frame 原点（B_p_L=[0,0,0]），前向偏移为 0')
    declare_sensorOffsetY     = DeclareLaunchArgument('sensorOffsetY',     default_value='0.0',    description='LiDAR 相对车体中心的侧向偏移 (m)')
    declare_cameraOffsetZ     = DeclareLaunchArgument('cameraOffsetZ',     default_value='0.2',    description='传感器高度参考偏移 (m)，当前暂用占位值')
    declare_vehicleX          = DeclareLaunchArgument('vehicleX',          default_value='0.0',    description='初始目标点 X')
    declare_vehicleY          = DeclareLaunchArgument('vehicleY',          default_value='0.0',    description='初始目标点 Y')
    declare_maxSpeed          = DeclareLaunchArgument('maxSpeed',          default_value='0.5',    description='最大速度 (m/s)，初期保守值，Scout Mini 上限约 1.5 m/s')
    declare_checkTerrainConn  = DeclareLaunchArgument('checkTerrainConn',  default_value='true',   description='')

    # ------------------------------------------------------------------ #
    #  FAST-LIO2（在本 launch 内直接以 Node 方式启动，以便设置 remappings）
    #
    #  前提：fastlio_ws 的 install/setup.bash 已 source
    #
    #  话题重映射：
    #    /Odometry         → /state_estimation_raw  (经 odom_frame_relay 修正后再发 /state_estimation)
    #    /cloud_registered → /registered_scan        (sensor_msgs/PointCloud2)
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

    # odom_frame_relay：修正里程计坐标系方向
    #   D455 body 帧（Z=前，X=右，Y=下）→ ROS 标准帧（X=前，Y=左，Z=上）
    #   q_corrected = q_fastlio ⊗ (0.5, -0.5, 0.5, 0.5)
    start_odom_relay = Node(
        package='vehicle_simulator',
        executable='odom_frame_relay.py',
        name='odom_frame_relay',
        output='screen',
    )

    # ------------------------------------------------------------------ #
    #  autonomy_stack 导航模块
    # ------------------------------------------------------------------ #

    # sensor_scan_generation：将 /state_estimation + /registered_scan
    # 时间同步后输出 /state_estimation_at_scan + /sensor_scan
    start_sensor_scan_generation = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('sensor_scan_generation'),
            'launch', 'sensor_scan_generation.launch')),
    )

    # terrain_analysis：分析地形，输出可通行性地图
    start_terrain_analysis = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis'),
            'launch', 'terrain_analysis.launch')),
    )

    # terrain_analysis_ext：扩展地形分析（障碍物连通性检查）
    start_terrain_analysis_ext = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis_ext'),
            'launch', 'terrain_analysis_ext.launch')),
        launch_arguments={'checkTerrainConn': checkTerrainConn}.items(),
    )

    # local_planner：局部规划 + pathFollower
    #   config=standard：差速/四轮驱动（Scout Mini 不是麦克纳姆）
    #   realRobot=false：不走串口，/cmd_vel 以 TwistStamped 发布到话题
    #
    #   SetRemap 把 local_planner 组内所有 /cmd_vel 出口重定向到 /cmd_vel_stamped，
    #   由 twist_stamped_to_twist 节点中继为 Twist 再发回 /cmd_vel，
    #   供 Scout Mini ROS2 驱动消费。
    #
    #  Scout Mini 尺寸（Trossen 规格：612 mm × 580 mm，向上取整留安全余量）：
    #    vehicleLength：0.70 m（前后方向，612 mm → 700 mm）
    #    vehicleWidth ：0.60 m（左右方向，580 mm → 600 mm）
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

    # TwistStamped → Twist 中继
    #   pathFollower (realRobot=false) 发布 /cmd_vel_stamped (TwistStamped)
    #   此节点剥掉 header，以 Twist 发布 /cmd_vel 供 Scout Mini 驱动订阅
    start_cmd_vel_relay = Node(
        package='vehicle_simulator',
        executable='twist_stamped_to_twist.py',
        name='twist_stamped_to_twist',
        output='screen',
    )

    # visualization_tools：轨迹/指标记录节点
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
    #  TF 桥接：连接 FAST-LIO2 的 TF 树与 autonomy_stack 的 TF 树
    #
    #  FAST-LIO2 发布：camera_init → body
    #  local_planner 发布：sensor → vehicle, sensor → camera
    #  缺失的连接：
    #    1. map ← camera_init：FAST-LIO2 用 camera_init 作为世界帧，
    #       autonomy_stack 用 map，二者等价，发布 identity TF 桥接
    #    2. body → sensor：将 D455 body 帧（Z=前，X=右，Y=下）旋转到
    #       autonomy_stack 期望的 sensor 帧（X=前，Y=左，Z=上）
    #       旋转四元数 (qx,qy,qz,qw) = (0.5, -0.5, 0.5, 0.5)
    #       验证：body.Z(前)→sensor.X ✓  body.X(右)→sensor.(-Y) ✓  body.Y(下)→sensor.(-Z) ✓
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

    # sensor_at_scan → vehicle：让 /path 和 /free_paths (frame_id="vehicle") 在 RViz 中正确显示
    # sensor_at_scan 由 sensorScanGeneration 动态广播 (map→sensor_at_scan)，
    # vehicle 与 sensor_at_scan 代表同一物理位置（机器人当前传感器所在处）
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

    # 全局设置 use_sim_time，作用于本 launch 内所有后续节点
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
    ld.add_action(start_visualization_tools)
    ld.add_action(start_rviz)

    return ld
