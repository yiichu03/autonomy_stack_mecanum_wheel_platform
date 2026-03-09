# 导航乱转与目标不可达问题调试记录

更新时间：2026-03-09  
项目目录：`/home/rho/Documents/liuyi/projects/thermal_nav/autonomy_stack_mecanum_wheel_platform`

## 1. 这份文档的目的

这份文档不是单纯记录“哪里出错了”，而是专门回答下面几个问题：

1. 当前小车为什么会出现左右旋转、不能稳定朝目标点前进
2. 我们为什么要重点关注 `local_planner` 和 `pathFollower`
3. 如果后续继续 debug，应该先读哪些代码、看哪些日志、按什么顺序理解
4. 哪些异常可能只是人为干预造成，哪些异常更像代码逻辑本身有问题

这份文档的目标是降低后续调试成本，让开发者能逐步建立对整条“目标点 -> 局部路径 -> 速度控制”链路的理解。

## 2. 当前问题现象

在已经跑通整条导航链路之后，仍然观察到如下问题：

1. RViz 中能够正常设置 `goalpoint`，`global path` 也基本合理
2. 但实车或 dry run 过程中，小车会频繁左右旋转
3. 小车有时并不朝目标点前进，而是在原地或小范围内反复调整方向
4. 在调试日志中，能够看到局部规划结果有时会突然变成“朝车后方”的路径

这说明：

1. 全局目标链路并不是完全坏掉的
2. 问题更可能出在“局部规划输出”和“控制器对局部路径的响应”之间

## 3. 当前导航链路的最小理解模型

对当前问题，先不用把整个项目全部读完。只要先抓住下面这条主链路即可：

```text
RViz Goalpoint
  -> far_planner
  -> /way_point
  -> localPlanner
  -> /path
  -> pathFollower
  -> /cmd_vel
  -> scout_base
```

对应含义：

1. `far_planner` 决定“往哪里去”
2. `localPlanner` 决定“当前这一小段怎么走”
3. `pathFollower` 决定“把这条局部路径变成什么速度命令”

当前“乱转”问题，最值得怀疑的是第 2 和第 3 步。

## 4. 为什么重点看这几个代码文件

### 4.1 `system_scout_hesai_with_far_planner.launch.py`

文件：
`src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py`

关注它的原因：

1. 它定义了当前实际运行模式
2. 它决定 `local_planner` 和 `pathFollower` 吃到的 launch 参数是什么
3. 当前 Scout 模式明确设置了 `twoWayDrive=false`

这一步非常关键，因为很多后续分析都建立在“Scout 不是双向驱动/不是允许倒车优先规划”的前提上。

如果不先看 launch，你会误以为代码默认还是原仓库那套平台逻辑。

### 4.2 `local_planner.launch`

文件：
`src/base_autonomy/local_planner/launch/local_planner.launch`

关注它的原因：

1. 它定义了 `localPlanner` 的主要规划参数
2. 这里能看到 `dirThre`、`freezeAng`、`freezeTime`、`goalBehindRange` 等参数
3. 这些参数直接决定：目标在车后方时，planner 会怎么处理

如果不看这里，就很难理解为什么日志里会出现 `freeze_status=1/2`、`joy_dir=95/-95` 这些现象。

### 4.3 `standard.yaml`

文件：
`src/base_autonomy/local_planner/config/standard.yaml`

关注它的原因：

1. 它定义 `pathFollower` 的行为参数
2. 包括 `dirDiffThre`、`maxYawRate`、`yawRateGain` 等
3. 这些参数决定控制器是“先转再走”还是“边走边修正”

这份文件主要帮助理解控制器为什么会在目标方向偏差较大时只发角速度。

### 4.4 `localPlanner.cpp`

文件：
`src/base_autonomy/local_planner/src/localPlanner.cpp`

这是当前问题最核心的文件。

需要重点回答的问题：

1. `goalX/goalY` 是怎么变成车体坐标系下的 `relativeGoalX/relativeGoalY` 的
2. `joyDir` 是怎么计算出来的
3. `freezeStatus` 是什么时候触发的
4. `twoWayDrive=false` 时，planner 如何限制目标方向
5. 最终选择了哪一组候选路径，为什么会出现 `selected_rot_deg=-180`

这也是为什么当前 debug 里，我们把 `local_planner.csv` 作为第一优先级日志。

### 4.5 `pathFollower.cpp`

文件：
`src/base_autonomy/local_planner/src/pathFollower.cpp`

它负责把 `/path` 变成 `/cmd_vel`。

需要重点回答的问题：

1. 新 `/path` 到来时，控制器如何更新自己的跟踪状态
2. `dirDiff` 是怎么计算的
3. 在什么条件下允许前进
4. 在什么条件下只会原地转向

如果 `localPlanner` 给出的是一条后向路径，那么 `pathFollower` 往往只是忠实执行那条坏路径，不一定是它自己“发疯”。

### 4.6 `far_planner.cpp`

文件：
`src/route_planner/far_planner/src/far_planner.cpp`

这个文件不是本问题的第一核心，但仍然值得读。

关注它的原因：

1. 它解释 `/goal_point` 为什么会变成 `/way_point`
2. 它帮助理解 `original_goal`、`free_goal`、`waypoint`、`global path` 之间的关系
3. 当怀疑“局部路径抖动是否来自全局 waypoint 自身跳变”时，需要回来看这里

## 5. 当前最值得怀疑的原因

当前不是所有异常都值得同等重视。  
需要区分两类情况：

### 5.1 可以暂时忽略的异常

如果在运行过程中：

1. 人为用遥控器把车挪到了另一个位置
2. 重新点击了新的 `goalpoint`
3. 中途切换了手动/自动状态

那么日志里出现：

1. `goal_x/goal_y` 突然大跳
2. `selected_rot_deg` 在短时间内大幅变化
3. 路径长度突然缩短

这些现象不一定代表代码有 bug。

### 5.2 不能忽略的异常

如果满足下面三个条件：

1. `goal_x/goal_y` 在一段时间内基本不变
2. `autonomy_mode=1`，说明不是手动遥控
3. 仍然反复出现 `selected_rot_deg=-180` 或局部路径目标点落在车后方

那么这更像是代码逻辑问题，而不是人为操作造成的扰动。

当前我们已经在日志里看到了这种情况。

## 6. 当前最强的怀疑点：`twoWayDrive=false` 分支

这是本轮 debug 的核心结论。

### 6.1 现象

在日志中，当目标相对方向逐渐跑到车后侧时，`localPlanner` 会出现：

1. `joy_dir` 被截到 `95` 或 `-95`
2. `freeze_status` 进入 `2`
3. `selected_rot_deg` 直接变成 `-180`

对应地，`pathFollower` 收到的目标点会变成：

1. `target_x < 0`
2. `dir_diff ≈ ±2.67`
3. `cmd_yaw` 长时间打满 `±1.047`

这正是“小车原地左右旋转”的直接表现。

### 6.2 为什么这更像是规划层问题，不是控制层问题

原因很简单：

1. `pathFollower` 只是跟踪 `localPlanner` 给它的 `/path`
2. 当 `/path` 的第一个有效目标点已经在车后方时，控制器只能先拼命转向
3. 当 `/path` 恢复成前向路径时，控制器又能正常给出前进速度

也就是说：

1. 控制器并不是一直坏的
2. 它是在“坏路径”和“正常路径”之间来回切换

所以更强的根因应该优先放在 `localPlanner` 上。

### 6.3 为什么怀疑 `twoWayDrive=false` 的索引语义不一致

`localPlanner` 的一段逻辑大意是：

1. 当 `twoWayDrive=false`
2. 如果 `joyDir > 95`，就把 `preSelectedGroupID = 0`
3. 如果 `joyDir < -95`，就把 `preSelectedGroupID = 6`

问题在于：

1. `0` 和 `6` 看起来像“路径组编号”
2. 但后面代码把 `selectedGroupID` 当成“全局候选编号”使用
3. 全局候选编号实际上是 `rotDir * groupNum + pathGroup`

由于 `groupNum=7`，所以：

1. `selectedGroupID=0` 时，`rotDir=0`
2. `selectedGroupID=6` 时，`rotDir=0`

而 `rotDir=0` 在后面会对应 `selectedRotDeg=-180`

这就解释了为什么在 `twoWayDrive=false` 的情形下，planner 却可能频繁地产生 `-180°` 的后向路径。

## 7. 推荐的阅读顺序

如果想真正看懂本轮分析，推荐按下面顺序读，而不是从文件头到尾硬啃：

### 第一步：先看 launch

先看：

1. `system_scout_hesai_with_far_planner.launch.py`
2. `local_planner.launch`
3. `standard.yaml`

目标：

1. 先搞清楚当前实际运行参数是什么
2. 不要一上来就钻进 cpp 细节

### 第二步：看 `localPlanner.cpp`

重点搜索这些变量：

1. `goalX`
2. `goalY`
3. `relativeGoalX`
4. `relativeGoalY`
5. `joyDir`
6. `freezeStatus`
7. `preSelectedGroupID`
8. `selectedGroupID`
9. `selectedRotDeg`

目标：

1. 理解“目标点是怎么变成局部路径方向的”
2. 理解“什么时候会被判定为目标在车后方”
3. 理解“为什么会选到某一组路径”

### 第三步：看 `pathFollower.cpp`

重点搜索这些变量：

1. `pathPointID`
2. `dirDiff`
3. `vehicleYawRate`
4. `vehicleSpeed`
5. `cmd_vel`

目标：

1. 理解“为什么有时只转不走”
2. 理解“为什么路径一旦跳到后方，就会表现成原地旋转”

### 第四步：再回来看日志

不要一边读代码一边瞎猜。  
更有效的方法是：

1. 看 `local_planner.csv` 里的 `joy_dir / freeze_status / selected_rot_deg`
2. 再去对照 `localPlanner.cpp`
3. 看 `path_follower.csv` 里的 `target_x / dir_diff / cmd_yaw`
4. 再去对照 `pathFollower.cpp`

这样会比只读代码快很多。

## 8. 当前 debug 时建议优先关注的日志字段

### 8.1 `local_planner.csv`

最关键的列：

1. `goal_x`, `goal_y`
2. `goal_rel_x`, `goal_rel_y`
3. `joy_dir`
4. `freeze_status`
5. `selected_rot_deg`
6. `selected_path_group`
7. `path_points`
8. `planner_left_points`, `planner_right_points`
9. `obstacle_left_points`, `obstacle_right_points`

这些列回答的是：

1. 当前目标相对车体是在前方还是后方
2. planner 最终想让车朝哪个方向走
3. 左右障碍分布是否合理
4. 局部路径是否被退化成很短的异常路径

### 8.2 `path_follower.csv`

最关键的列：

1. `path_size`
2. `path_point_id`
3. `target_x`, `target_y`
4. `dir_diff`
5. `cmd_x`
6. `cmd_yaw`
7. `path_update_mode`
8. `path_update_match_id`
9. `path_update_match_dis`

这些列回答的是：

1. 控制器当前跟的是前方路径还是后方路径
2. 它是不是因为没对准而拒绝前进
3. 这次路径更新是“保留进度”还是“从头重置”

## 9. 当前阶段的实用 debug 规则

### 规则 1

如果 `goal_x/goal_y` 在几百毫秒内大跳，不要急着下结论，先排除人为干预。

### 规则 2

如果目标固定不变，但 `selected_rot_deg` 仍反复跳到 `-180`，优先怀疑 `localPlanner` 的选路逻辑。

### 规则 3

如果 `pathFollower` 里 `target_x < 0` 且 `cmd_yaw` 长时间打满，先不要调控制参数，应该先去查规划输出为什么变成后向路径。

### 规则 4

只有当 `/path` 已经稳定且合理时，调 `dirDiffThre`、`yawRateGain`、`maxYawRate` 才有意义。

## 10. 当前结论（供后续继续验证）

基于目前的日志和代码阅读，当前更强的判断是：

1. 主链路已经跑通，系统不是“整体不可用”
2. 问题主要集中在局部规划与控制接口处
3. `pathFollower` 之前确实存在“路径频繁更新就重置”的问题，这部分已经缓解
4. 但更关键的问题是：`localPlanner` 在 `twoWayDrive=false` 的情形下，仍可能产出 `-180°` 的后向局部路径
5. 这会直接导致控制器表现成原地左右旋转

注意：

这不是说控制器完全没问题，而是当前阶段最值得优先解决的问题，不在控制器末端，而在局部规划的前一层决策逻辑。

## 11. 后续建议

后续继续 debug 时，建议严格按照下面顺序推进：

1. 先验证 `localPlanner` 在 `twoWayDrive=false` 时是否仍会选出 `selected_rot_deg=-180`
2. 再验证这是否和 `preSelectedGroupID` 的使用方式有关
3. 修复这层逻辑后，重新录一轮日志
4. 只有在 `/path` 已稳定合理后，再继续调 `pathFollower`

## 12. 附：当前最值得反复看的文件清单

1. `src/base_autonomy/vehicle_simulator/launch/system_scout_hesai_with_far_planner.launch.py`
2. `src/base_autonomy/local_planner/launch/local_planner.launch`
3. `src/base_autonomy/local_planner/config/standard.yaml`
4. `src/base_autonomy/local_planner/src/localPlanner.cpp`
5. `src/base_autonomy/local_planner/src/pathFollower.cpp`
6. `src/route_planner/far_planner/src/far_planner.cpp`

如果只能先读 3 个文件，优先级是：

1. `localPlanner.cpp`
2. `pathFollower.cpp`
3. `system_scout_hesai_with_far_planner.launch.py`
