"""
system_scout_hesai_with_tare.launch.py
=======================================
Scout Mini + Hesai XT32 + RealSense D455 + TARE 自主探索规划 launch 文件。

在 system_scout_hesai.launch.py 的基础上加入 TARE 探索规划器，替代 far_planner。
机器人启动后将自动开始探索（kAutoStart=true），无需手动指定目标点。

数据流：
  TARE ←── /terrain_map, /terrain_map_ext, /state_estimation_at_scan, /registered_scan
        ──→ /way_point
                ↓
       localPlanner → /path → pathFollower → /cmd_vel (Twist)

与 far_planner 模式的区别：
  - far_planner 模式：人工点击 Goalpoint，far_planner 规划全局路径
  - TARE 模式：系统自主生成探索 waypoint，无需人工干预
  - 两种模式互斥（都发布 /way_point），通过不同 launch 文件切换

使用方式：
  # 终端 A / B：PTP 时间同步（Hesai 需要）
  sudo ptp4l -f /etc/linuxptp/ptp4l-xt32.conf -i eno1 -m
  sudo phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -O 0 -m

  # 终端 C：Hesai 驱动
  source ~/Documents/hesai_ws/install/setup.bash
  ros2 launch hesai_ros_driver start.py

  # 终端 D：RealSense 驱动
  source ~/Documents/isaac_ros_ws/install/setup.bash
  ros2 launch realsense2_camera rs_launch.py unite_imu_method:=1 enable_gyro:=true enable_accel:=true

  # 终端 E：主导航栈
  source /opt/ros/humble/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/fastlio_ws/install/setup.bash
  source ~/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/install/setup.bash
  ros2 launch vehicle_simulator system_scout_hesai_with_tare.launch.py

  # 观察：
  ros2 topic echo /way_point    # TARE 发出的探索目标点
  ros2 topic echo /cmd_vel      # pathFollower 发布的最终速度命令

TARE 配置说明：
  scenario=indoor_small（默认）：室内小空间，viewpoint 网格 9m×9m，kSensorRange=3m
  config 文件：src/exploration_planner/tare_planner/config/indoor_small.yaml
  kAutoStart=true：启动后立即开始探索
  kRushHome=true：探索结束后自动返回起点

修改历史：
  2026-03-11  基于 system_scout_hesai_with_far_planner.launch.py 新增 TARE 集成
"""

import os
from datetime import datetime
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, SetEnvironmentVariable
from launch.launch_description_sources import FrontendLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter


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
    tareConfig        = LaunchConfiguration('tareConfig')
    enableDebugLog    = LaunchConfiguration('enableDebugLog')
    debugLogDir       = LaunchConfiguration('debugLogDir')
    debugLogDecimation = LaunchConfiguration('debugLogDecimation')
    gravityLevelQx    = LaunchConfiguration('gravityLevelQx')
    gravityLevelQy    = LaunchConfiguration('gravityLevelQy')
    gravityLevelQz    = LaunchConfiguration('gravityLevelQz')
    gravityLevelQw    = LaunchConfiguration('gravityLevelQw')

    workspace_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(get_package_share_directory('vehicle_simulator')))))

    # OR-Tools ARM64 .so 放在 install/tare_planner/lib/，但 ament 未自动加入 LD_LIBRARY_PATH
    # 需要手动注入，否则 tare_planner_node 无法加载 libortools.so.9
    or_tools_lib_path = os.path.join(workspace_root, 'install', 'tare_planner', 'lib')
    default_debug_log_dir = os.path.join(
        workspace_root,
        'runtime_logs',
        'navigation_debug',
        datetime.now().strftime('%Y%m%d_%H%M%S'))

    declare_use_sim_time        = DeclareLaunchArgument('use_sim_time',          default_value='false', description='true=bag 回放，false=实车实时')
    declare_sensorOffsetX       = DeclareLaunchArgument('sensorOffsetX',         default_value='0.0',   description='LiDAR 前向偏移 (m)')
    declare_sensorOffsetY       = DeclareLaunchArgument('sensorOffsetY',         default_value='0.0',   description='LiDAR 侧向偏移 (m)')
    declare_cameraOffsetZ       = DeclareLaunchArgument('cameraOffsetZ',         default_value='0.2',   description='传感器高度参考偏移 (m)')
    declare_vehicleX            = DeclareLaunchArgument('vehicleX',              default_value='0.0',   description='初始目标点 X')
    declare_vehicleY            = DeclareLaunchArgument('vehicleY',              default_value='0.0',   description='初始目标点 Y')
    declare_maxSpeed            = DeclareLaunchArgument('maxSpeed',              default_value='0.5',   description='最大速度 (m/s)')
    declare_checkTerrainConn    = DeclareLaunchArgument('checkTerrainConn',      default_value='true',  description='')
    declare_tare_config         = DeclareLaunchArgument('tareConfig',            default_value='indoor_small.yaml', description='TARE 配置文件：indoor_small.yaml / indoor_large.yaml / outdoor.yaml')
    declare_enable_debug_log    = DeclareLaunchArgument('enableDebugLog',        default_value='true',  description='是否记录规划/控制调试 CSV 日志')
    declare_debug_log_dir       = DeclareLaunchArgument('debugLogDir',           default_value=default_debug_log_dir, description='规划/控制调试日志目录')
    declare_debug_log_decimation = DeclareLaunchArgument('debugLogDecimation',   default_value='10',    description='调试日志采样降频系数')
    declare_gravity_level_qx    = DeclareLaunchArgument('gravityLevelQx', default_value='-0.004276', description='重力摆平补偿四元数 x')
    declare_gravity_level_qy    = DeclareLaunchArgument('gravityLevelQy', default_value='0.043092',  description='重力摆平补偿四元数 y')
    declare_gravity_level_qz    = DeclareLaunchArgument('gravityLevelQz', default_value='0.000000',  description='重力摆平补偿四元数 z')
    declare_gravity_level_qw    = DeclareLaunchArgument('gravityLevelQw', default_value='0.999062',  description='重力摆平补偿四元数 w')

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
            ('/cloud_registered', '/registered_scan_raw'),
            ('/path',             '/fastlio_path'),
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
            'twoWayDrive':   'true',
            # TARE publishes /way_point and expects the vehicle to start moving
            # without a joystick mode switch.
            'autonomyMode':  'true',
            'vehicleLength': '0.70',
            'vehicleWidth':  '0.60',
            'enableDebugLog': enableDebugLog,
            'debugLogDir':    debugLogDir,
            'debugLogDecimation': debugLogDecimation,
        }.items(),
    )

    # ------------------------------------------------------------------ #
    #  TARE 探索规划器
    #
    #  订阅：/terrain_map, /terrain_map_ext, /state_estimation_at_scan, /registered_scan
    #  发布：/way_point（localPlanner 订阅此话题，与 far_planner 相同接口）
    #
    #  kAutoStart=true：启动后立即开始探索
    #  配置文件：install/tare_planner/share/tare_planner/<tareConfig>
    # ------------------------------------------------------------------ #
    start_tare_planner = Node(
        package='tare_planner',
        executable='tare_planner_node',
        name='tare_planner_node',
        parameters=[
            PathJoinSubstitution([get_package_share_directory('tare_planner'), tareConfig]),
            {'use_sim_time': use_sim_time},
            {'enableDebugLog': enableDebugLog},
            {'debugLogDir': debugLogDir},
            {'debugLogDecimation': debugLogDecimation},
        ],
        output='screen',
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

    # ------------------------------------------------------------------ #
    #  TF 桥接
    # ------------------------------------------------------------------ #
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
    ld.add_action(declare_tare_config)
    ld.add_action(declare_enable_debug_log)
    ld.add_action(declare_debug_log_dir)
    ld.add_action(declare_debug_log_decimation)
    ld.add_action(declare_gravity_level_qx)
    ld.add_action(declare_gravity_level_qy)
    ld.add_action(declare_gravity_level_qz)
    ld.add_action(declare_gravity_level_qw)
    ld.add_action(LogInfo(msg=['Navigation debug logs: ', debugLogDir]))

    ld.add_action(SetParameter(name='use_sim_time', value=use_sim_time))

    # 注入 OR-Tools 库路径（ament 未自动注册，tare_planner_node 需要 libortools.so.9）
    ld.add_action(SetEnvironmentVariable(
        name='LD_LIBRARY_PATH',
        value=[or_tools_lib_path, ':', EnvironmentVariable('LD_LIBRARY_PATH', default_value='')],
    ))

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
    ld.add_action(start_tare_planner)
    ld.add_action(start_visualization_tools)
    ld.add_action(start_rviz)

    return ld
