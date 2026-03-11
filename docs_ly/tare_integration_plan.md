# TARE 探索模块重新接入评估与计划（2026-03-11）

> 当前状态参考：`docs_ly/current_status_20260311.md`

## 1. 结论先说

**可以接回来试，而且值得试。**

但建议按两阶段理解难度：

1. **当前工作站先做 dry-run / RViz 验证**：难度中等
2. **真正并入当前实机主链、跑稳定探索**：难度中高

原因不是 TARE 本身话题不兼容，而是：

1. 当前局部规划近目标收敛仍不稳定
2. TARE 会持续发布新的 `/way_point`
3. 一旦下游 `localPlanner / pathFollower` 还不够稳，探索模式会把这些问题放大

## 2. 为什么说它“可以接回来”

### 2.1 仓库里已经有完整模块

当前仓库内已有：

```text
src/exploration_planner/tare_planner/
```

并且已有现成 launch：

1. `src/exploration_planner/tare_planner/launch/explore.launch`
2. `src/exploration_planner/tare_planner/launch/explore_world.launch`

### 2.2 当前输入输出和现有链路能对上

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

## 3. 当前真正的难点

### 3.1 它不能和 FAR 直接并列开跑

当前 `far_planner` 和 `tare_planner` 都会往 `/way_point` 发目标。  
这意味着：

1. 两者不适合同时作为主导航源运行
2. 更合理的做法是单独做一个“探索模式”入口
3. 也就是把 TARE 做成与 FAR 互斥的 launch 方案

### 3.2 当前局部规划近目标行为仍不够稳

这不是 TARE 自己的问题，但会直接影响 TARE 效果：

1. TARE 会不断生成新的 waypoint
2. `localPlanner` / `pathFollower` 当前近目标时仍可能反复转向
3. 所以如果现在直接接上 TARE，常见现象不会是“完全不工作”，而是“能探索，但走得不顺、局部动作别扭”

### 3.3 当前仓库里 bundled OR-Tools 还是 x86-64

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

### 3.4 `explore_world.launch` 的 boundary 文件路径还需要检查

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

## 4. 预期难度

### 4.1 当前工作站 dry-run

**难度：中等**

原因：

1. 话题兼容性已经基本确认
2. 仓库内已有 TARE 节点和配置文件
3. 主要工作是做一个与 FAR 互斥的接入入口，并验证输出 waypoint 是否合理

### 4.2 当前实机链路联调

**难度：中高**

原因：

1. TARE 会频繁给出新 waypoint
2. 当前局部规划近目标收敛问题会被放大
3. 真正探索时对边界、障碍、回家行为的稳定性要求更高

### 4.3 未来上 Orin / ARM64

**难度：中高到高**

主要新增阻塞是：

1. OR-Tools 需要换成 ARM64 版本
2. 重新编译 `tare_planner`

## 5. 预期效果

如果接入顺利，TARE 带来的效果不是“更优雅的点到点导航”，而是：

1. 不再需要人工不断点击 Goalpoint
2. 机器人能自主生成探索 waypoint
3. 在未知或半未知区域里推进覆盖
4. 探索结束后可进一步评估回起点能力

更直白地说：

1. FAR 解决“你给终点，我帮你过去”
2. TARE 解决“没有终点，我自己找地方去探索”

## 6. 预期收益和现实边界

### 6.1 预期收益

如果只是为了先“看效果”，最现实的收益是：

1. 在室内小场景里看到 TARE 连续发布 `/way_point`
2. RViz 中能看到 waypoint 随探索推进而变化
3. 小车或干跑链路能表现出“不是朝固定单个目标，而是在自主找新目标”

### 6.2 现实边界

不要预期第一次接入就马上得到稳定完整的探索闭环。  
更现实的第一阶段目标应该是：

1. 节点能启动
2. waypoint 能合理产出
3. 不和现有 FAR / `/way_point` 链路打架

## 7. 建议的接入顺序

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

1. 带明显边界
2. 人随车
3. 随时可切手动接管

## 8. 我对“现在值不值得做”的判断

**值得做，但不建议一下子把它当成当前主模式。**

更合适的预期是：

1. 现在就可以开始做 TARE 重新接入评估和 dry-run
2. 先把它当成一个并行实验分支
3. 不要先替换掉当前 `with_far_planner` 主流程

## 9. 当前推荐计划

推荐顺序：

1. 保持当前 FAR 主入口可用
2. 新增一个独立的 TARE 试验入口
3. 先做 dry-run 和 RViz 观察
4. 再决定是否推进到实机探索

一句话总结：

**TARE 现在已经到了“可以开始接回来试”的阶段，但更适合当下一步实验项，而不是立刻替代当前主导航模式。**
