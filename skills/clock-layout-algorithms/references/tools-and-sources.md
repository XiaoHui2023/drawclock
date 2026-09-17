# 工具与资料

## 工具判断

- React Flow 是节点/边交互显示层，本身不提供自动布局；官方示例接入 Dagre、ELK 等引擎。它适合作为界面参考，不是 drawclock 的算法答案。
- Dagre/Graphviz dot 适合快速分层 DAG，但端口和正交细节控制不足时需要独立路由层。
- ELK Layered 支持动态尺寸、端口、分层、交叉最小化和正交路由，是很好的算法基准；复杂选项不应原样暴露给用户。
- libavoid 的正交可见图、A*、共享段排序和 nudging 对精确避障与少折点有直接参考价值。

## 主要资料

- [ELK Layered 官方参考](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)
- [ELK Layered 五阶段说明](https://eclipse.dev/elk/blog/posts/2025/25-08-21-layered.html)
- [ELK Node Promotion 官方参考](https://eclipse.dev/elk/reference/options/org-eclipse-elk-layered-layering-nodePromotion-strategy.html)
- [React Flow 官方布局选型](https://reactflow.dev/learn/layouting/layouting)
- [Graphviz dot 官方文档](https://graphviz.org/docs/layouts/dot/)
- [Brandes–Köpf 坐标分配论文](https://boriskoepf.de/papers/gd01a.pdf)
- [Brandes–Köpf 勘误](https://arxiv.org/abs/2008.01252)
- [Orthogonal Connector Routing](https://people.eng.unimelb.edu.au/pstuckey/papers/gd09.pdf)
- [libavoid 官方概览](https://www.adaptagrams.org/documentation/libavoid.html)
- [ELK 多 handle 次序案例](https://github.com/xyflow/xyflow/issues/3603)
- [精确 handle 位置与 FIXED_POS 讨论](https://github.com/xyflow/xyflow/discussions/5125)
- [ELK T 形共享交汇限制案例](https://github.com/kieler/elkjs/issues/54)
- [yFiles Hierarchical Layout 官方说明](https://docs.yworks.com/yfiles-html/dguide/layout/hierarchical_layout.html)
- [yFiles Node Types 官方说明](https://docs.yworks.com/yfiles-html/dguide/node_types/)（同类节点相邻是次级准则，不能新增交叉或冲突）
- [yFiles Hierarchical Layout API](https://docs.yworks.com/yfiles-html/api/HierarchicalLayout/)（约束优先级、边分组、crossing cost 与端口候选）
- [yFiles Edge and Port Grouping](https://docs.yworks.com/yfiles-html/dguide/layout-features/layout-edge_grouping.html)（同一 edge group 共享线段，是公共根纵向 bus 的直接行业语义参考）
- [Graphviz rank 官方说明](https://graphviz.org/docs/attrs/rank/)（`rank=source` 是强制最小层，不能误作无代价美观偏好）
- [NIST 组合测试与覆盖数组项目](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software)
- [Hypothesis 属性测试文档](https://hypothesis.readthedocs.io/en/latest/)
- [coverage.py 分支覆盖文档](https://coverage.readthedocs.io/en/latest/branch.html)

社区案例只用于识别失败模式；规范结论以官方文档、论文和项目机器门为准。

## 设施与总线的职责边界

公共根的重复扇出先由拓扑识别为一个 edge group / bus；这不是“可按行复制的多个独立源”。
设施拆分只由一个看到完整根扇出、完整行轴和完整可视障碍的全局阶段决定。正常规则行距即使逐条
缩短导线，也必须保留共享主干；只有相对页面标准行距存在明显空带且全量质量向量不变差时，才可
分出同名显示设施。后续局部设施、坐标和路由阶段不得重新拆分已被全局阶段保留的 bus。

此边界对应 ELK 的分相管线（分层、交叉最小化、坐标、路由）和 yFiles 的 edge grouping：共享段的
语义先成立，局部路由只能实现它，不能将其改写为逐行独立边。每次改动须同时跑公共/私人、公共/公共、
声明乱序、紧凑阵列和真实远距带；任一项失败即否决发布。
