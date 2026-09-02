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
6. 选型或继续研究时查看[工具与资料](references/tools-and-sources.md)。

## 优先级

严格按词典序处理：连接与端口正确、无节点/可见文字穿越、无异网重合、少交叉、少折点、短路径，最后才是面积和耗时。不得为了缩小画布接受多余折点或交叉。
