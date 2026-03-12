# TARE 探索模块重新接入评估与计划（2026-03-11）

> 当前状态参考：`docs_ly/current_status_20260311.md`

## 1. 结论先说

**可以接回来试，而且值得试。**

但建议把它理解成“下一阶段实验项”，不是立刻替代当前主流程。

更准确的判断是：

1. 当前工作站先做 dry-run / RViz 验证：难度中等
2. 真正并入当前实机主链、跑稳定探索：难度中高

原因不是 TARE 本身和当前链路完全不兼容，而是：

1. 当前局部规划近目标收敛仍不稳定
2. TARE 会持续发布新的 `/way_point`
3. 一旦下游 `localPlanner / pathFollower` 还不够稳，探索模式会把这些问题放大

## 2. TARE 和 FAR 到底是什么关系

### 2.1 它们当前是两种并列模式，不是串联阶段

从当前仓库和原始 launch 组织方式看，作者本来的思路就是：

1. `FAR 模式`：人工指定 `Goalpoint`，由 `far_planner` 做点到点全局引导
2. `TARE 模式`：系统自己持续发布 `/way_point` 做探索

原仓库本来就有两套独立入口：

1. `system_*_with_route_planner.launch`
2. `system_*_with_exploration_planner.launch`

这说明原作者并不是让 FAR 和 TARE 同时当主规划器运行，而是把它们当成两种互斥模式。

### 2.2 为什么说“当前接线下它们是冲突的”

因为现在：

1. `far_planner` 会发布 `/way_point`
2. `tare_planner` 也会发布 `/way_point`
3. `localPlanner` 只消费一个 `/way_point`

所以如果同时开：

1. 不是谁更高级谁接管
2. 而是两个上层模块会互相抢目标

所以这里的“冲突”不是算法概念上的绝对冲突，而是**当前话题接线方式下的主导航源冲突**。

### 2.3 你原来想的“先探索再 Goalpoint”行不行

行，而且这是很合理的使用流程。

正确理解应该是：

1. 先运行 `TARE 模式` 做探索
2. 停掉 TARE
3. 再切回 `FAR 模式`
4. 在已经探索过的区域里人工点 `Goalpoint`

所以：

1. TARE 和 FAR 当前不适合同一时刻并列开跑
2. 但完全可以先后使用

## 3. 为什么说它“可以接回来”

### 3.1 仓库里已经有完整模块

当前仓库内已有：

```text
src/exploration_planner/tare_planner/
```

并且已有现成 launch：

1. `src/exploration_planner/tare_planner/launch/explore.launch`
2. `src/exploration_planner/tare_planner/launch/explore_world.launch`

### 3.2 当前输入输出和现有链路能对上

根据 `indoor_small.yaml` / `outdoor.yaml`，TARE 主要订阅：

1. `/terrain_map`
2. `/terrain_map_ext`
3. `/state_estimation_at_scan`
4. `/registered_scan`

当前系统里这些话题都已经存在。

它主要发布：

1. `/way_point`

而这正是 `localPlanner` 当前就能直接消费的话题。

所以从**数据接口**上看，TARE 与当前系统是兼容的。

## 4. 它什么时候开始探索

按当前仓库里的默认配置，**启动后通常会自动开始探索**。

原因是：

1. TARE 主节点每 1 秒执行一次主循环
2. 只有在 `!kAutoStart && !start_exploration_` 时才会等待开始信号
3. 当前 `indoor_small.yaml` 和 `outdoor.yaml` 里 `kAutoStart` 都是 `true`

这意味着在当前默认配置下：

1. 节点启动
2. 输入话题正常
3. 它就会开始规划并发布 `/way_point`

如果以后想改成“先启动，但手动决定何时开始探索”，可以把 `kAutoStart` 设成 `false`，再通过 `/start_exploration` 触发。

## 5. `use_boundary=false` 到底意味着什么

`explore_world.launch` 里有一个 `use_boundary` 开关，默认是：

```text
use_boundary=false
```

它的含义不是“TARE 不能探索”，而是：

1. launch 不会自动启动 `navigationBoundary`
2. 系统不会额外收到一条人为给定的导航边界
3. TARE 主要依赖当前观测到的地形、点云和 frontier 自己往外推进

更直白地说：

1. `use_boundary=false` = 没有人工围栏
2. 不是“探索关闭”
3. 也不是“必须先知道房间精确尺寸”

这在小场景、强监管 dry-run 下可以先试。  
但室内一旦有门、走廊、开放区域或玻璃边界，没有边界会更容易让机器人往不想去的地方扩展。

## 6. 如果我不知道实验室具体大小怎么办

不知道精确大小，不是硬阻塞。

更现实的做法是：

### 6.1 第一轮：先不要求精确边界，只做受控观察

适合条件：

1. 场景不大
2. 人在旁边
3. 随时可手动接管

这一步的目的不是正式跑完整探索，而是回答：

1. TARE 是否真的在产出合理 `/way_point`
2. waypoint 更新方向是否符合场景直觉
3. 没有边界时，它是否明显想往不该去的区域扩展

### 6.2 第二轮：根据第一轮观察，补一个保守边界

你不需要一开始就知道实验室精确长宽。  
更实用的流程是：

1. 先跑一轮或先观察一轮 RViz
2. 大概知道安全活动区域
3. 再给一个**保守的小边界**

这里的关键不是把实验室测得极其精确，而是：

1. 先把明显不该去的区域排除掉
2. 让第一版探索限定在一个可控范围内

所以你刚才问的“是不是可以先运行一次再大概知道范围”，答案是：

**可以，而且这是很合理的做法。**

## 7. 它如何判断探索结束

当前代码不是按“房间尺寸已知”来判断结束，而是按探索状态判断。

核心逻辑是：

1. `grid_world_->IsReturningHome()`
2. `local_coverage_planner_->IsLocalCoverageComplete()`
3. 并且运行超过 5 秒

满足后会把：

```text
exploration_finished_ = true
```

如果开启了回家行为，后面还会继续判断是否已经回到 home 附近：

1. `GetRobotToHomeDistance() < kAtHomeDistThreshold`

所以它的“结束”更像是：

1. 当前可探索区域基本完成
2. 系统准备回家
3. 如果回家也完成，则整个探索流程结束

而不是：

1. 预先知道房间长宽
2. 走满某个矩形区域
3. 然后机械停止

## 8. 它如何与导航结合

TARE 和当前导航链路的结合方式非常直接：

```text
terrain / odom / scan
  -> TARE
  -> /way_point
  -> localPlanner
  -> /path
  -> pathFollower
  -> /cmd_vel
```

也就是说：

1. TARE 不是离线把地图探索完后再交给另一个模块
2. 它是在线探索、在线发布 waypoint
3. 下游导航仍然是当前这套 `localPlanner + pathFollower`

所以它和 FAR 的区别是：

1. FAR：你给终点，它沿全局图给中间 waypoint
2. TARE：它自己根据覆盖/前沿不断生成新的 waypoint

## 9. 当前真正的难点

### 9.1 当前局部规划近目标行为仍不够稳

这不是 TARE 自己的问题，但会直接影响 TARE 效果：

1. TARE 会不断生成新的 waypoint
2. `localPlanner` / `pathFollower` 当前近目标时仍可能反复转向
3. 所以如果现在直接接上 TARE，常见现象不会是“完全不工作”，而是“能探索，但走得不顺、局部动作别扭”

### 9.2 当前仓库里 bundled OR-Tools 还是 x86-64

当前仓库自带的库文件是：

```text
src/exploration_planner/tare_planner/or-tools/lib/libortools.so.9.8.3296
```

当前文件架构是：

```text
x86-64
```

这意味着：

1. 在当前 x86 工作站上尝试 dry-run 是有希望的
2. 但如果后面要迁回 Jetson AGX Orin 这类 aarch64 平台，需要先替换成 ARM64 版本 OR-Tools

### 9.3 `explore_world.launch` 的 boundary 文件路径还需要检查

`explore_world.launch` 里 `navigationBoundary` 节点当前使用：

```text
<share>/tare_planner/boundary.ply
```

但仓库里的文件实际位于：

```text
src/exploration_planner/tare_planner/data/boundary.ply
```

这说明：

1. 现成 launch 不能无脑直接当“已经验证过的最终入口”
2. 真接入时需要顺手核对 boundary 文件路径

## 10. 预期难度

### 10.1 当前工作站 dry-run

**难度：中等**

原因：

1. 话题兼容性已经基本确认
2. 仓库内已有 TARE 节点和配置文件
3. 主要工作是做一个与 FAR 互斥的接入入口，并验证输出 waypoint 是否合理

### 10.2 当前实机链路联调

**难度：中高**

原因：

1. TARE 会频繁给出新 waypoint
2. 当前局部规划近目标收敛问题会被放大
3. 真正探索时对边界、障碍、回家行为的稳定性要求更高

### 10.3 未来上 Orin / ARM64

**难度：中高到高**

主要新增阻塞是：

1. OR-Tools 需要换成 ARM64 版本
2. 重新编译 `tare_planner`

## 11. 预期效果

如果接入顺利，TARE 带来的效果不是“更优雅的点到点导航”，而是：

1. 不再需要人工不断点击 Goalpoint
2. 机器人能自主生成探索 waypoint
3. 在未知或半未知区域里推进覆盖
4. 探索结束后可进一步评估回起点能力

更直白地说：

1. FAR 解决“你给终点，我帮你过去”
2. TARE 解决“没有终点，我自己找地方去探索”

## 12. 预期收益和现实边界

### 12.1 预期收益

如果只是为了先“看效果”，最现实的收益是：

1. 在室内小场景里看到 TARE 连续发布 `/way_point`
2. RViz 中能看到 waypoint 随探索推进而变化
3. 小车或干跑链路能表现出“不是朝固定单个目标，而是在自主找新目标”

### 12.2 现实边界

不要预期第一次接入就马上得到稳定完整的探索闭环。  
更现实的第一阶段目标应该是：

1. 节点能启动
2. waypoint 能合理产出
3. 不和现有 FAR / `/way_point` 链路打架

## 13. 建议的接入顺序

### 阶段 1：只做文档和方案确认

当前这一步已经可以完成：

1. 确认 TARE 模块存在
2. 确认输入输出兼容
3. 确认主要风险和优先级

### 阶段 2：先做单独 dry-run 探索入口

目标：

1. 不动当前 FAR 主入口
2. 单独准备一个“Scout + Hesai + TARE”的探索入口
3. 先看 `/way_point`、`/free_paths`、RViz 效果

这一步的验收重点不是覆盖率，而是：

1. TARE 是否稳定发布 waypoint
2. waypoint 是否大体合理
3. 是否明显放大当前局部规划问题

### 阶段 3：小范围、强监管实机验证

条件是：

1. 阶段 2 的 dry-run 已经合理
2. 当前近目标乱转问题至少没有明显恶化

然后再在小空间里试：

1. 第一轮可先不加边界，但必须强监管
2. 第二轮建议补一个保守边界
3. 人随车，随时可切手动接管

## 14. 我对“现在值不值得做”的判断

**值得做，但不建议一下子把它当成当前主模式。**

更合适的预期是：

1. 现在就可以开始做 TARE 重新接入评估和 dry-run
2. 先把它当成一个并行实验分支
3. 不要先替换掉当前 `with_far_planner` 主流程

## 15. 当前推荐计划

推荐顺序：

1. 保持当前 FAR 主入口可用
2. 新增一个独立的 TARE 试验入口
3. 先做 dry-run 和 RViz 观察
4. 第一轮不追求完整覆盖率，只看 waypoint 是否合理
5. 第二轮再根据实际场地补边界
6. 再决定是否推进到实机探索

一句话总结：

**TARE 现在已经到了“可以开始接回来试”的阶段，但更适合当下一步实验项，而不是立刻替代当前主导航模式。**
