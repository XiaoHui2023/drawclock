---
name: project-goals
description: drawclock 当前目标、验证证据与完成条件索引。
---

# 项目目标

- [ ] 每条用户反馈先经公开入口自然复现，再允许修改对应生产 owner。
- [ ] 每条非共享普通边都通过可行通道的最少拐点证明，避免两拐点路线逃逸。
- [ ] `FB-BEND-014`：自然复现并判定相邻高根器件的折点是否由真实可视碰撞所需；若直连净空成立则消除多余折点。
- [x] `FB-ROOT-015`：自然复现并消除紧凑工整消费带中的零入度逻辑根过度显示拆分；公共/私人 `from→mux2→clock` 数组由一个公共显示设施和一条纵向总线分发，合理远距消费带仍可保留多个设施。
- [x] `FB-BEND-013`：交叉分割后的首段、中段、尾段和端口邻域分别通过局部最少拐点反事实，消除“整边有交叉所以尾段漏检”的逃逸。
- [x] `FB-BEND-011`：自然复现并消除无交叉收益的可避免折点，同时保留合理避障折线反例。
- [x] `FB-ROOT-012`：自由零入度设施在高优先级几何不退化时优先形成稳定局部列，不再无理由滞留首列或分散。
- [ ] 末端一分二与相邻一分一不产生可避免交叉。
- [x] 非对称前后级的同源汇聚节点保持同列。
- [ ] 跨大区域根从合适边界进入，同根消费域不夹杂可分离的无关域。
- [x] Agent 质检记录末层交叉、根消费域夹杂、合理局部主干、微线段和可避免拐点。
- [x] `gate_a_tap` 类长距末端使用结构性整组换行消除非必要拐点，面积不再优先于美观。
- [x] v1.0.0 只保留直接绘图主功能，v0.0.0 可恢复。
- [x] 发布包仅靠标准库 Python 源码与包内 ELK 运行时完成 JSON 绘图，不携带 Python 运行时依赖。
- [x] `--library` 同时接受多个器件库文件和目录，并确定性合并扫描结果。
- [x] [发布项目 Skills](goals/release-project-skills.md)
- [用户反馈自然复现门禁](goals/user-feedback-natural-reproduction-gate.md)

- [x] [逐边最少拐点证明](goals/per-edge-bend-minimality.md)
- [v1.0.0 单功能重构](goals/v1-draw-only.md)
- [非对称汇聚输入异常外凸](goals/asymmetric-merge-route-bulge.md)
- [坐标与正交路由联合优化](goals/joint-coordinate-routing-optimization.md)
- [最小通用 draw 示例](goals/minimal-draw-example.md)
- [发行包源码离线部署](goals/offline-source-deployment.md)
- [多器件库输入与合并](goals/multiple-library-inputs.md)
