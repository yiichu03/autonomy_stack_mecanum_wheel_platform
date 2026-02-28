"""
system_scout_hesai.launch.py
============================
Scout Mini + Hesai XT32 + RealSense D455 IMU 专用 launch 文件。

架构：
  FAST-LIO2 (fastlio_ws)  →  remap  →  autonomy_stack navigation modules
    /Odometry               →  /state_estimation
    /cloud_registered       →  /registered_scan

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
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import FrontendLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter


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
    declare_sensorOffsetX     = DeclareLaunchArgument('sensorOffsetX',     default_value='0.1',    description='LiDAR 相对车体中心的前向偏移 (m)，需按实物测量后调整')
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
    #    /Odometry         → /state_estimation   (nav_msgs/Odometry)
    #    /cloud_registered → /registered_scan    (sensor_msgs/PointCloud2)
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
            ('/Odometry',         '/state_estimation'),
            ('/cloud_registered', '/registered_scan'),
        ],
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
    #                    （上车时需要 TwistStamped → Twist relay，或改此参数逻辑）
    #
    #  Scout Mini 尺寸参数（需按实物测量后精调）：
    #    vehicleLength：0.93m（官方数据）
    #    vehicleWidth ：0.70m（官方数据 699mm，保守取整）
    start_local_planner = IncludeLaunchDescription(
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
        }.items(),
    )

    # visualization_tools：RViz 可视化辅助
    start_visualization_tools = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('visualization_tools'),
            'launch', 'visualization_tools.launch')),
        launch_arguments={'world_name': 'real_world'}.items(),
    )

    # ------------------------------------------------------------------ #
    #  TF 桥接：连接 FAST-LIO2 的 TF 树与 autonomy_stack 的 TF 树
    #
    #  FAST-LIO2 发布：camera_init → body
    #  local_planner 发布：sensor → vehicle, sensor → camera
    #  缺失的连接：
    #    1. map ← camera_init：FAST-LIO2 用 camera_init 作为世界帧，
    #       autonomy_stack 用 map，二者等价，发布 identity TF 桥接
    #    2. body → sensor：FAST-LIO2 的机体帧 = IMU 帧，
    #       autonomy_stack 的 sensor 帧 = LiDAR 帧，
    #       此处用 identity 近似（真实偏移 < 10cm，可视化足够）
    # ------------------------------------------------------------------ #
    tf_map_to_camera_init = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_map_to_camera_init',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'camera_init'],
    )

    tf_body_to_sensor = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_body_to_sensor',
        arguments=['0', '0', '0', '0', '0', '0', 'body', 'sensor'],
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
    ld.add_action(start_fastlio)
    ld.add_action(start_sensor_scan_generation)
    ld.add_action(start_terrain_analysis)
    ld.add_action(start_terrain_analysis_ext)
    ld.add_action(start_local_planner)
    ld.add_action(start_visualization_tools)

    return ld
