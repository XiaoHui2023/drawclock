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
- [NIST 组合测试与覆盖数组项目](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software)
- [Hypothesis 属性测试文档](https://hypothesis.readthedocs.io/en/latest/)
- [coverage.py 分支覆盖文档](https://coverage.readthedocs.io/en/latest/branch.html)

社区案例只用于识别失败模式；规范结论以官方文档、论文和项目机器门为准。
