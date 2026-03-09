"""
system_scout_hesai.launch.py
============================
Scout Mini + Hesai XT32 + RealSense D455 IMU 专用 launch 文件。

架构：
  FAST-LIO2 (fastlio_ws)  →  remap  →  registered_scan_frame_relay / odom_frame_relay  →  autonomy_stack
    /Odometry               →  /state_estimation_raw
    /cloud_registered       →  /registered_scan_raw  →  /registered_scan
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
from datetime import datetime
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import FrontendLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetParameter

# generate_launch_description() 是 ROS 2 launch 文件的入口函数。ros2 launch 最终就是调用它，拿到一个 LaunchDescription。
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
    maxSpeed        = LaunchConfiguration('maxSpeed') # “后面谁需要 maxSpeed，就引用这个启动参数”。
    checkTerrainConn = LaunchConfiguration('checkTerrainConn')
    enableDebugLog  = LaunchConfiguration('enableDebugLog')
    debugLogDir     = LaunchConfiguration('debugLogDir')
    debugLogDecimation = LaunchConfiguration('debugLogDecimation')

    workspace_root = os.path.dirname( # 连续四次 dirname() 回到工作区根目录
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(get_package_share_directory('vehicle_simulator')))))
    default_debug_log_dir = os.path.join( # 拼出 runtime_logs/navigation_debug/<时间戳>。
        workspace_root,
        'runtime_logs',
        'navigation_debug',
        datetime.now().strftime('%Y%m%d_%H%M%S'))

    # 真正声明了启动参数。
    declare_use_sim_time      = DeclareLaunchArgument('use_sim_time',      default_value='false',  description='true=bag 回放，false=实车实时')
    declare_sensorOffsetX     = DeclareLaunchArgument('sensorOffsetX',     default_value='0.0',    description='LiDAR 原点 = Body frame 原点（B_p_L=[0,0,0]），前向偏移为 0')
    declare_sensorOffsetY     = DeclareLaunchArgument('sensorOffsetY',     default_value='0.0',    description='LiDAR 相对车体中心的侧向偏移 (m)')
    declare_cameraOffsetZ     = DeclareLaunchArgument('cameraOffsetZ',     default_value='0.2',    description='传感器高度参考偏移 (m)，当前暂用占位值')
    declare_vehicleX          = DeclareLaunchArgument('vehicleX',          default_value='0.0',    description='初始目标点 X')
    declare_vehicleY          = DeclareLaunchArgument('vehicleY',          default_value='0.0',    description='初始目标点 Y')
    declare_maxSpeed          = DeclareLaunchArgument('maxSpeed',          default_value='0.5',    description='最大速度 (m/s)，初期保守值，Scout Mini 上限约 1.5 m/s')
    declare_checkTerrainConn  = DeclareLaunchArgument('checkTerrainConn',  default_value='true',   description='')
    declare_enable_debug_log  = DeclareLaunchArgument('enableDebugLog',    default_value='true',   description='是否记录规划/控制调试 CSV 日志')
    declare_debug_log_dir     = DeclareLaunchArgument('debugLogDir',       default_value=default_debug_log_dir, description='规划/控制调试日志目录')
    declare_debug_log_decimation = DeclareLaunchArgument('debugLogDecimation', default_value='10', description='调试日志采样降频系数')

    # ------------------------------------------------------------------ #
    #  FAST-LIO2（在本 launch 内直接以 Node 方式启动，以便设置 remappings）
    #
    #  前提：fastlio_ws 的 install/setup.bash 已 source
    #
    #  话题重映射：
    #    /Odometry         → /state_estimation_raw  (经 odom_frame_relay 修正后再发 /state_estimation)
    #    /cloud_registered → /registered_scan_raw    (sensor_msgs/PointCloud2)
    # ------------------------------------------------------------------ #
    fastlio_config_path = os.path.join( # 先拿到 fast_lio 包的 config 目录。
        get_package_share_directory('fast_lio'), 'config')
    #  这里定义 fastlio_mapping 节点，但此时还没启动，只是先构造一个 Node action。
    start_fastlio = Node(
        package='fast_lio',
        executable='fastlio_mapping',
        name='fastlio_mapping',
        parameters=[
            os.path.join(fastlio_config_path, 'hesai_xt32.yaml'),   # hesai_xt32.yaml 参数文件。
            {'use_sim_time': use_sim_time},     # 用于覆盖或补充 YAML 里的参数。
        ],
        remappings=[ # 把 FAST-LIO 原始输出改名 /Odometry -> /state_estimation_raw   ；  /cloud_registered -> /registered_scan_raw
            ('/Odometry',         '/state_estimation_raw'),
            ('/cloud_registered', '/registered_scan_raw'),
        ],
        output='screen',
    )

    # 启动 registeredScanFrameRelay，它负责把 FAST-LIO 点云世界系转成导航栈需要的 map 系
    start_registered_scan_relay = Node(
        package='vehicle_simulator',
        executable='registeredScanFrameRelay',
        name='registered_scan_frame_relay',
        output='screen',
    )

    # 启动 odom_frame_relay.py，它负责修正 FAST-LIO 里程计轴向，让下游看到标准 ROS 车体方向。
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

    #  include sensor_scan_generation.launch：将 /state_estimation + /registered_scan
    # 时间同步后输出 /state_estimation_at_scan + /sensor_scan
    start_sensor_scan_generation = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('sensor_scan_generation'),
            'launch', 'sensor_scan_generation.launch')),
    )

    #  include terrain_analysis.launch：分析地形，输出局部可通行性地图/terrain_map
    start_terrain_analysis = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis'),
            'launch', 'terrain_analysis.launch')),
    )

    # include terrain_analysis_ext.launch：扩展地形分析（障碍物连通性检查）. 把 checkTerrainConn 传进去，输出扩展地形或连通性相关结果。
    start_terrain_analysis_ext = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('terrain_analysis_ext'),
            'launch', 'terrain_analysis_ext.launch')),
        launch_arguments={'checkTerrainConn': checkTerrainConn}.items(),
    )

    # local_planner：局部规划 + pathFollower
    #   config=standard：差速/四轮驱动（Scout Mini 不是麦克纳姆）
    #   realRobot=false：不走原仓库串口控制，直接发布 ROS /cmd_vel (Twist)
    #
    #  Scout Mini 尺寸（规格：612 mm × 580 mm，向上取整留安全余量）：
    #    vehicleLength：0.70 m（前后方向，612 mm → 700 mm）
    #    vehicleWidth ：0.60 m（左右方向，580 mm → 600 mm）
    start_local_planner = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('local_planner'),
            'launch', 'local_planner.launch')),
        launch_arguments={
            'config':        'standard', # 用标准轮式配置，不用全向轮配置。
            'realRobot':     'false',  # 不用原仓库那条串口直控链，而是直接发 ROS Twist。
            'sensorOffsetX': sensorOffsetX,
            'sensorOffsetY': sensorOffsetY,
            'cameraOffsetZ': cameraOffsetZ,
            'goalX':         vehicleX,
            'goalY':         vehicleY,
            'maxSpeed':      maxSpeed,
            'twoWayDrive':   'true',    #  false表示规划器/控制器按“不允许倒车优先”的思路工作。 #####################
            'autonomyMode':  'false',
            'vehicleLength': '0.70',
            'vehicleWidth':  '0.60',
            'enableDebugLog': enableDebugLog,
            'debugLogDir':    debugLogDir,
            'debugLogDecimation': debugLogDecimation,
        }.items(),
    )

    # visualization_tools：轨迹/指标记录节点   辅助可视化和指标记录。
    start_visualization_tools = IncludeLaunchDescription(
        FrontendLaunchDescriptionSource(os.path.join(
            get_package_share_directory('visualization_tools'),
            'launch', 'visualization_tools.launch')),
        launch_arguments={'world_name': 'real_world'}.items(),
    )

    # RViz：加载导航栈专用配置（直接加载 vehicle_simulator.rviz）（含 Waypoint/Goalpoint 插件）
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
    #    1. map ← camera_init：将 FAST-LIO2 原始世界系(X=右, Y=下, Z=前) 旋正到 ROS map (X=前, Y=左, Z=上)
    #    2. body → sensor：将 D455 body 帧（Z=前，X=右，Y=下）旋转到autonomy_stack 期望的 sensor 帧（X=前，Y=左，Z=上）
    #       map ← camera_init: (qx,qy,qz,qw)=(-0.5, 0.5, -0.5, 0.5)
    #       body ← sensor:     (qx,qy,qz,qw)=( 0.5,-0.5,  0.5, 0.5)
    # ------------------------------------------------------------------ #
    tf_map_to_camera_init = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_map_to_camera_init',
        arguments=['0', '0', '0', '-0.5', '0.5', '-0.5', '0.5', 'map', 'camera_init'],
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
    ld = LaunchDescription() # 创建一个空的 LaunchDescription 容器。

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
    ld.add_action(LogInfo(msg=['Navigation debug logs: ', debugLogDir]))

    # 全局设置 use_sim_time，作用于本 launch 内所有后续节点
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
    ld.add_action(start_visualization_tools)
    ld.add_action(start_rviz)

    return ld
