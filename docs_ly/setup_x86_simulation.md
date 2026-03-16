# x86_64 笔记本仿真环境配置记录

**时间**：2026-03-14
**平台**：Ubuntu 22.04 / ROS2 Humble / NVIDIA RTX 4060 Laptop 8GB
**目标**：在 x86_64 笔记本上运行 autonomy_stack_mecanum_wheel_platform Unity 仿真（indoor corridors 场景）

---

## 背景

代码通过 git 从 AGX Orin（ARM64）同步到笔记本（x86_64），需要调整环境后才能运行仿真。笔记本无需硬件（不插雷达、IMU、电机控制器），仿真场景由 Unity 提供。

---

## 前置条件（已满足）

- Ubuntu 22.04.5 LTS
- ROS2 Humble（已安装，`source /opt/ros/humble/setup.bash` 已加入 `.bashrc`）
- NVIDIA RTX 4060 Laptop，驱动已装，OpenGL 4.6 支持
- 内存 15GB，磁盘 1.5TB 可用
- miniforge3 安装在 `~/miniforge3`（base 环境默认激活）

---

## 下载的文件

放在 `env/` 目录下：

```
env/
├── unity_env_models/
│   ├── office_building_2.zip   ← 用于仿真的场景（L形多房间办公楼，走廊感强）
│   └── ...（其他 17 个 Unity 场景，备用）
├── cic_building_indoor.db3     ← CMU CIC 楼室内走廊 bag 文件（实机录制，855MB）
└── nsh_building_outdoor.db3    ← CMU NSH 楼室外 bag 文件（566MB）
```

---

## 配置步骤

### 第一步：apt 依赖安装（需要 sudo）

```bash
sudo apt update && sudo apt install -y libusb-dev ros-humble-tf-transformations python3-colcon-common-extensions
```

**说明**：`ros-humble-desktop` 和 `python-is-python3` 已预装，只缺这三个。

---

### 第二步：pip 依赖安装

```bash
pip install transforms3d pyyaml catkin_pkg "empy==3.3.4" lark colcon-common-extensions
```

**关键点**：
- `empy` 必须用 `3.3.4`，不能用 4.x（ROS Humble 和 empy 4.x API 不兼容）
- `catkin_pkg` 是 CMake 在 `ament_package()` 时调用 Python 解析 `package.xml` 需要的
- 这些包装在 miniforge 环境里是因为 miniforge 的 Python 被 CMake 优先找到

---

### 第三步：替换 OR-Tools 为 x86_64 版本

**背景**：代码在 AGX Orin 上跑过实机，`libortools.so.9.8.3296` 被替换成了 ARM64 版本并通过 git 同步过来，在 x86_64 上直接报错。

```bash
# 确认当前是 ARM64（应显示 aarch64）
file src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296

# 下载 x86_64 版本（版本号必须是 v9.8.3296，不能用其他版本）
cd ~/Downloads
wget https://github.com/google/or-tools/releases/download/v9.8/or-tools_amd64_ubuntu-22.04_cpp_v9.8.3296.tar.gz
tar xzf or-tools_amd64_ubuntu-22.04_cpp_v9.8.3296.tar.gz

# 替换（只替换 libortools.so，libortools_flatzinc.so 原本就是 x86-64 不用动）
OR_TOOLS_REPO=~/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform/src/exploration_planner/tare_planner/or-tools/lib
OR_TOOLS_NEW=~/Downloads/or-tools_x86_64_Ubuntu-22.04_cpp_v9.8.3296/lib
cp $OR_TOOLS_NEW/libortools.so.9.8.3296 $OR_TOOLS_REPO/libortools.so.9.8.3296
cp $OR_TOOLS_NEW/libortools.so.9 $OR_TOOLS_REPO/libortools.so.9
cp $OR_TOOLS_NEW/libortools.so $OR_TOOLS_REPO/libortools.so

# 验证
file $OR_TOOLS_REPO/libortools.so.9.8.3296
# 应显示：ELF 64-bit LSB shared object, x86-64
```

---

### 第四步：解压 Unity 环境模型

```bash
cd ~/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform

# 解压到 unity/ 目录下（会创建 office_building_2/ 子目录）
unzip -o env/unity_env_models/office_building_2.zip \
    -d src/base_autonomy/vehicle_simulator/mesh/unity/

# 把内容移到 unity/ 根目录（system_simulation.sh 期望的路径）
UNITY_DIR=src/base_autonomy/vehicle_simulator/mesh/unity
cp -r $UNITY_DIR/office_building_2/* $UNITY_DIR/

# 确认文件就位并给执行权限
ls $UNITY_DIR/environment/Model.x86_64
chmod +x $UNITY_DIR/environment/Model.x86_64
```

---

### 第五步：编译

**关键**：编译时必须让系统 Python (`/usr/bin/python3`) 优先于 miniforge Python，否则会有两类问题：

- **empy/catkin_pkg 缺失**：miniforge Python 没有 ROS 编译工具需要的包
- **libcurl 链接错误**：miniforge 的 `libpython3.12.so` 被链入，导致 `/home/liuyi/miniforge3/lib` 进入 rpath，链接器找到 miniforge 的 `libcurl`（无 `CURL_OPENSSL_4` 符号），与系统 `libgdal.so.30` 不兼容

**正确编译命令**（全量，跳过 SLAM 和雷达驱动）：

```bash
cd ~/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
export PATH=/usr/bin:/usr/local/bin:$PATH
source /opt/ros/humble/setup.bash
MAKEFLAGS="-j1" colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3 \
    --packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2 \
    --parallel-workers 1
```

**参数说明**：
- `export PATH=/usr/bin:/usr/local/bin:$PATH`：让系统 Python 优先
- `-DPython3_EXECUTABLE=/usr/bin/python3`：强制 CMake 用系统 Python 3.10
- `--parallel-workers 1` + `MAKEFLAGS="-j1"`：防止并行编译时内存耗尽导致系统卡死
- `--packages-skip arise_slam_mid360 arise_slam_mid360_msgs livox_ros_driver2`：仿真不需要 SLAM 和雷达驱动

---

## 遇到的卡点及解决方法

### 卡点 1：`ModuleNotFoundError: No module named 'catkin_pkg'`

**原因**：miniforge 的 Python 被 CMake 优先选中，但它缺少 `catkin_pkg`。
**解决**：`pip install catkin_pkg`（装进 miniforge 环境）

---

### 卡点 2：`ModuleNotFoundError: No module named 'em'`

**原因**：同上，`empy` 未装或版本为 4.x。
**解决**：`pip install "empy==3.3.4"`（注意必须 3.x）

---

### 卡点 3：`far_planner` 编译失败——libcurl 符号未定义

```
undefined reference to `curl_easy_getinfo@CURL_OPENSSL_4'
```

**原因**：之前编译 `visibility_graph_msg` 时用了 miniforge Python 3.12，其 CMake 导出文件 `export_visibility_graph_msg__rosidl_generator_pyExport.cmake` 硬编码了 `/home/liuyi/miniforge3/lib/libpython3.12.so`。`far_planner` 依赖 `visibility_graph_msg`，导致 `/home/liuyi/miniforge3/lib` 进入链接器搜索路径，miniforge 的 `libcurl`（无版本符号）覆盖了系统的 `libcurl`（有 `CURL_OPENSSL_4`），与 `libgdal.so.30` 产生符号冲突。

**解决**：
```bash
# 清除被污染的 build/install 目录
rm -rf build/visibility_graph_msg install/visibility_graph_msg \
       build/domain_bridge install/domain_bridge \
       build/far_planner install/far_planner \
       build/graph_decoder install/graph_decoder \
       build/local_planner install/local_planner \
       build/vehicle_simulator install/vehicle_simulator

# 用系统 Python 重新编译（加 -DPython3_EXECUTABLE）
export PATH=/usr/bin:/usr/local/bin:$PATH
source /opt/ros/humble/setup.bash
MAKEFLAGS="-j1" colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3 \
    --packages-select visibility_graph_msg domain_bridge far_planner \
                       graph_decoder local_planner vehicle_simulator \
    --parallel-workers 1
```

---

### 卡点 4：编译时系统卡死

**原因**：默认并行编译（最多 20 个包同时编译，每包多线程）耗尽内存和 CPU。
**解决**：加 `--parallel-workers 1` 和 `MAKEFLAGS="-j1"`，一次只编一个包单线程。

---

## 运行方式

每次运行前设置 PATH（防止 miniforge 干扰运行时库搜索）：

```bash
cd ~/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform
export PATH=/usr/bin:/usr/local/bin:$PATH
source install/setup.bash
```

### 模式一：基础仿真（Waypoint 模式）

```bash
./system_simulation.sh
```

RViz 启动后可用 `Waypoint` 按钮设置近距离目标点，小车自主导航并避障。

### 模式二：路径规划仿真（Goalpoint 模式）

```bash
./system_simulation_with_route_planner.sh
```

RViz 启动后用 `Goalpoint` 按钮设置远距离目标，far_planner 构建可见性图引导导航。
**注意**：Goalpoint 按钮只在此模式下有效，在模式一中无响应（far_planner 未启动）。

### 模式三：探索规划仿真（TARE 自主探索）

```bash
./system_simulation_with_exploration_planner.sh
```

RViz 启动后点 `Resume Navigation to Goal`，TARE 开始自主覆盖探索。
探索配置默认为 `indoor_small`，适合室内走廊场景。

---

## 注意事项

| 事项 | 说明 |
|------|------|
| Unity 首次启动慢 | 20-30 秒，等待加载，不要关闭 |
| Unity 桥接偶尔不稳 | RViz 没数据就重启一次（README 已知问题） |
| 不要 source fastlio_ws | 仿真不需要，source 了可能有话题冲突 |
| OR-Tools 版本锁定 | 必须 v9.8.3296，换其他版本会编译报错 |
| 每次编译前设置 PATH | `export PATH=/usr/bin:/usr/local/bin:$PATH` 防止 miniforge 污染 |

---

## bag 文件回放（可选）

如需回放真实室内走廊数据：

```bash
# 启动 bag 处理系统
./system_bagfile.sh

# 另开终端回放 CIC 楼室内走廊录包
source install/setup.bash
ros2 bag play env/cic_building_indoor.db3
```
