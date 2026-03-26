"""
system_scout_hesai_with_ariadne.launch.py
=========================================
Scout Mini + Hesai XT32 + RealSense D455 + ARiADNE 自主探索规划 launch 文件。

这个 launch 基于现有 `system_scout_hesai_with_tare.launch.py` 做最小替换：
- 保留 FAST-LIO2 / relay / sensor_scan_generation / terrain_analysis / localPlanner
- 删除 TARE planner
- 新增 octomap_server_node + rl_planner

前提：
- 已经 source `/opt/ros/humble/setup.bash`
- 已经 source `autonomy_stack_mecanum_wheel_platform/install/setup.bash`
- 已经 source `ARiADNE-ROS-Planner/install/setup.bash`

关键注意：
- `rl_planner` 来自独立的 `ARiADNE-ROS-Planner` 工作区，不在本仓库内
- ARiADNE 官方 launch 默认 `base_frame=sensor`
- 当前系统的 `/sensor_scan` 使用 `sensor_at_scan`，所以这里默认改成 `sensor_at_scan`
"""

import os
from datetime import datetime

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import FrontendLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    sensorOffsetX = LaunchConfiguration('sensorOffsetX')
    sensorOffsetY = LaunchConfiguration('sensorOffsetY')
    cameraOffsetZ = LaunchConfiguration('cameraOffsetZ')
    vehicleX = LaunchConfiguration('vehicleX')
    vehicleY = LaunchConfiguration('vehicleY')
    maxSpeed = LaunchConfiguration('maxSpeed')
    checkTerrainConn = LaunchConfiguration('checkTerrainConn')
    enableDebugLog = LaunchConfiguration('enableDebugLog')
    debugLogDir = LaunchConfiguration('debugLogDir')
    debugLogDecimation = LaunchConfiguration('debugLogDecimation')
    gravityLevelQx = LaunchConfiguration('gravityLevelQx')
    gravityLevelQy = LaunchConfiguration('gravityLevelQy')
    gravityLevelQz = LaunchConfiguration('gravityLevelQz')
    gravityLevelQw = LaunchConfiguration('gravityLevelQw')

    ariadneBaseFrame = LaunchConfiguration('ariadneBaseFrame')
    ariadneSensorRange = LaunchConfiguration('ariadneSensorRange')
    ariadneMapResolution = LaunchConfiguration('ariadneMapResolution')
    ariadneNodeResolution = LaunchConfiguration('ariadneNodeResolution')
    ariadnePublishGraph = LaunchConfiguration('ariadnePublishGraph')
    fastlioConfig = LaunchConfiguration('fastlioConfig')

    workspace_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(get_package_share_directory('vehicle_simulator')))))
    default_debug_log_dir = os.path.join(
        workspace_root,
        'runtime_logs',
        'navigation_debug',
        datetime.now().strftime('%Y%m%d_%H%M%S'))

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='false', description='true=bag 回放，false=实车实时')
    declare_sensorOffsetX = DeclareLaunchArgument(
        'sensorOffsetX', default_value='0.0', description='LiDAR 前向偏移 (m)')
    declare_sensorOffsetY = DeclareLaunchArgument(
        'sensorOffsetY', default_value='0.0', description='LiDAR 侧向偏移 (m)')
    declare_cameraOffsetZ = DeclareLaunchArgument(
        'cameraOffsetZ', default_value='0.2', description='传感器高度参考偏移 (m)')
    declare_vehicleX = DeclareLaunchArgument(
        'vehicleX', default_value='0.0', description='初始目标点 X')
    declare_vehicleY = DeclareLaunchArgument(
        'vehicleY', default_value='0.0', description='初始目标点 Y')
    declare_maxSpeed = DeclareLaunchArgument(
        'maxSpeed', default_value='0.5', description='最大速度 (m/s)')
    declare_checkTerrainConn = DeclareLaunchArgument(
        'checkTerrainConn', default_value='true', description='')
    declare_enable_debug_log = DeclareLaunchArgument(
        'enableDebugLog', default_value='true', description='是否记录规划/控制调试 CSV 日志')
    declare_debug_log_dir = DeclareLaunchArgument(
        'debugLogDir', default_value=default_debug_log_dir, description='规划/控制调试日志目录')
    declare_debug_log_decimation = DeclareLaunchArgument(
        'debugLogDecimation', default_value='10', description='调试日志采样降频系数')
    declare_gravity_level_qx = DeclareLaunchArgument(
        'gravityLevelQx', default_value='-0.004276', description='重力摆平补偿四元数 x')
    declare_gravity_level_qy = DeclareLaunchArgument(
        'gravityLevelQy', default_value='0.043092', description='重力摆平补偿四元数 y')
    declare_gravity_level_qz = DeclareLaunchArgument(
        'gravityLevelQz', default_value='0.000000', description='重力摆平补偿四元数 z')
    declare_gravity_level_qw = DeclareLaunchArgument(
        'gravityLevelQw', default_value='0.999062', description='重力摆平补偿四元数 w')

    declare_ariadne_base_frame = DeclareLaunchArgument(
        'ariadneBaseFrame', default_value='sensor_at_scan',
        description='ARiADNE / octomap 使用的 base frame')
    declare_ariadne_sensor_range = DeclareLaunchArgument(
        'ariadneSensorRange', default_value='20.0',
        description='ARiADNE 感知半径 (m)')
    declare_ariadne_map_resolution = DeclareLaunchArgument(
        'ariadneMapResolution', default_value='0.4',
        description='OccupancyGrid 分辨率 (m)')
    declare_ariadne_node_resolution = DeclareLaunchArgument(
        'ariadneNodeResolution', default_value='2.0',
        description='ARiADNE 图节点分辨率 (m)')
    declare_ariadne_publish_graph = DeclareLaunchArgument(
        'ariadnePublishGraph', default_value='false',
        description='是否发布图可视化')
    declare_fastlio_config = DeclareLaunchArgument(
        'fastlioConfig', default_value='hesai32_kuangye.yaml',
        description='FAST-LIO 配置文件名，位于 fast_lio/share/fast_lio/config/')

    fastlio_config_path = os.path.join(
        get_package_share_directory('fast_lio'), 'config')

    start_fastlio = Node(
        package='fast_lio',
        executable='fastlio_mapping',
        name='fastlio_mapping',
        parameters=[
            PathJoinSubstitution([fastlio_config_path, fastlioConfig]),
            {'use_sim_time': use_sim_time},
        ],
        remappings=[
            ('/Odometry', '/state_estimation_raw'),
            ('/cloud_registered', '/registered_scan_raw'),
            ('/path', '/fastlio_path'),
        ],
        output='screen',
    )

    start_registered_scan_relay = Node(
        package='vehicle_simulator',
        executable='registeredScanFrameRelay',
        name='registered_scan_frame_relay',
        parameters=[{
            'gravity_level_qx': gravityLevelQx,
            'gravity_level_qy': gravityLevelQy,
            'gravity_level_qz': gravityLevelQz,
            'gravity_level_qw': gravityLevelQw,
        }],
        output='screen',
    )

    start_odom_relay = Node(
        package='vehicle_simulator',
        executable='odom_frame_relay.py',
        name='odom_frame_relay',
        parameters=[{
            'gravity_level_qx': gravityLevelQx,
            'gravity_level_qy': gravityLevelQy,
            'gravity_level_qz': gravityLevelQz,
            'gravity_level_qw': gravityLevelQw,
        }],
        output='screen',
    )

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

    start_local_planner = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('local_planner'),
            'launch', 'local_planner.launch')),
        launch_arguments={
            'config': 'standard',
            'realRobot': 'false',
            'sensorOffsetX': sensorOffsetX,
            'sensorOffsetY': sensorOffsetY,
            'cameraOffsetZ': cameraOffsetZ,
            'goalX': vehicleX,
            'goalY': vehicleY,
            'maxSpeed': maxSpeed,
            'twoWayDrive': 'true',
            'autonomyMode': 'true',
            'vehicleLength': '0.70',
            'vehicleWidth': '0.60',
            'enableDebugLog': enableDebugLog,
            'debugLogDir': debugLogDir,
            'debugLogDecimation': debugLogDecimation,
        }.items(),
    )

    start_octomap = Node(
        package='octomap_server',
        executable='octomap_server_node',
        name='octomap',
        output='screen',
        remappings=[('cloud_in', 'sensor_scan')],
        parameters=[
            {'frame_id': 'map'},
            {'base_frame_id': ariadneBaseFrame},
            {'resolution': ariadneMapResolution},
            {'occupancy_min_z': 0.0},
            {'occupancy_max_z': 1.2},
            {'sensor_model.max_range': ariadneSensorRange},
            {'sensor_model.hit': 1.0},
            {'sensor_model.miss': 0.45},
            {'sensor_model.max': 1.0},
            {'sensor_model.min': 0.2},
        ],
    )

    start_ariadne = Node(
        package='rl_planner',
        executable='rl_planner',
        name='rl_planner',
        output='screen',
        emulate_tty=True,
        parameters=[
            {'publish_graph': ariadnePublishGraph},
            {'node_resolution': ariadneNodeResolution},
            {'sensor_range': ariadneSensorRange},
            {'utility_range_factor': 0.5},
            {'min_utility': 3},
            {'frontier_downsample_factor': 1},
            {'map_resolution': ariadneMapResolution},
            {'waypoint_threshold': 2.0},
            {'next_waypoint_threshold': 4.0},
            {'hard_update_threshold': 10.0},
            {'frontier_cluster_range': 10.0},
            {'enable_save_mode': False},
            {'enable_dstarlite': False},
            {'replanning_frequency': 2.5},
            {'use_sim_time': use_sim_time},
        ],
    )

    start_visualization_tools = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('visualization_tools'),
            'launch', 'visualization_tools.launch')),
        launch_arguments={'world_name': 'real_world'}.items(),
    )

    start_rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(
            get_package_share_directory('vehicle_simulator'),
            'rviz', 'vehicle_simulator.rviz')],
        output='screen',
    )

    tf_map_to_camera_init = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_map_to_camera_init',
        arguments=['0', '0', '0', '-0.523215', '0.518939', '-0.480123', '0.475847', 'map', 'camera_init'],
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

    ld = LaunchDescription()

    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_sensorOffsetX)
    ld.add_action(declare_sensorOffsetY)
    ld.add_action(declare_cameraOffsetZ)
    ld.add_action(declare_vehicleX)
    ld.add_action(declare_vehicleY)
    ld.add_action(declare_maxSpeed)
    ld.add_action(declare_checkTerrainConn)
    ld.add_action(declare_enable_debug_log)
    ld.add_action(declare_debug_log_dir)
    ld.add_action(declare_debug_log_decimation)
    ld.add_action(declare_gravity_level_qx)
    ld.add_action(declare_gravity_level_qy)
    ld.add_action(declare_gravity_level_qz)
    ld.add_action(declare_gravity_level_qw)
    ld.add_action(declare_ariadne_base_frame)
    ld.add_action(declare_ariadne_sensor_range)
    ld.add_action(declare_ariadne_map_resolution)
    ld.add_action(declare_ariadne_node_resolution)
    ld.add_action(declare_ariadne_publish_graph)
    ld.add_action(declare_fastlio_config)
    ld.add_action(LogInfo(msg=['Navigation debug logs: ', debugLogDir]))

    ld.add_action(SetParameter(name='use_sim_time', value=use_sim_time))

    ld.add_action(tf_map_to_camera_init)
    ld.add_action(tf_body_to_sensor)
    ld.add_action(tf_sensor_at_scan_to_vehicle)

    ld.add_action(start_fastlio)
    ld.add_action(start_registered_scan_relay)
    ld.add_action(start_odom_relay)
    ld.add_action(start_sensor_scan_generation)
    ld.add_action(start_terrain_analysis)
    ld.add_action(start_terrain_analysis_ext)
    ld.add_action(start_local_planner)
    ld.add_action(start_octomap)
    ld.add_action(start_ariadne)
    ld.add_action(start_visualization_tools)
    ld.add_action(start_rviz)

    return ld
