---
name: clock-layout-algorithms
description: 修改、评审或扩展 drawclock 自动布局算法时使用，覆盖分层 DAG、排序、列约束、正交路由、总线、规模化和质量目标。
---

# 时钟图布局算法

把输入建模为“带固定端口和可见占用范围的、从左到右的分层 DAG”。它具有树状阅读习惯，但允许多源、汇聚、复用和交叉，不能退化为普通树布局或无约束图布局。

## 算法链

1. 按[图模型与分层](references/layering.md)构建逻辑节点、端口边、层级和主观列约束。
2. 按[行序与坐标](references/ordering-and-placement.md)减少交叉、对齐相似支路并分配可见矩形。
3. 按[正交路由与总线](references/orthogonal-routing.md)从精确端口寻路、合并同源干线并简化折点。
4. 按[规模化与确定性](references/scalability.md)限制候选、分解接多路下游的结构并保持输出稳定。
5. 使用[质量目标与门禁](references/quality-gates.md)选择候选和阻止回归。
   通用零入度源显示副本专项的边界、指标、反例和回退点见[源副本能力合同](references/source-replication-capability.json)。
   自由源列、逐元素统计和特性覆盖专项见[自由源与覆盖能力合同](references/free-source-coverage-capability.json)。
   当前可执行的特性、风险交互、场景、Oracle 与故障注入映射见[布局特性覆盖账本](references/layout-feature-coverage.json)。
   用户反馈的自然红灯、跨问题语料和独立最终 SVG 统计见[多对多复现与几何 Oracle](references/feedback-reproduction-and-geometry-oracle.md)。
6. 选型或继续研究时查看[工具与资料](references/tools-and-sources.md)。

Agent 需要定位某个节点或某根线的质量代价时，运行 `scripts/layout_statistics.py`。它显式启用几何统计，输出每个逻辑节点、每条逻辑边和每个出边节点的长度、折点、跨线、分支和显示锚点统计；这是包内质检工具，不是 `drawclock` 的用户子命令。正常 SVG 生成不物化逐边交叉伙伴集合，避免让诊断成本拖慢用户入口。

## 优先级

严格按词典序处理：连接与端口正确、无节点/可见文字穿越、无异网重合、少交叉、少折点、短路径，最后才是面积和耗时。不得为了缩小画布接受多余折点或交叉。
