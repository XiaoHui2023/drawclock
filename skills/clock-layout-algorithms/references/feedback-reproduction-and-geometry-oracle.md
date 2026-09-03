# 多对多复现与几何 Oracle

## 证据关系

问题 ID 保持独立，测试文件不要求一对一。`tests/reproduction-corpus/` 是正常 JSON 搜索语料；每个
case 可由 `tools/feedback_layout_reproduction_oracle.py` 直接显示多个问题，一个问题也可出现在多个
case 中。总体覆盖按 `case -> observed issue IDs` 的二部关系计算，没有直接几何检测的边不存在。

正式证据由 `tools/run_feedback_reproduction_corpus.py` 生成。它从
`tests/reproduction-corpus/evidence-corpus.json` 选择稳定 case，在各自冻结 revision 的公开 CLI
运行两次，保存原始 SVG、日志和统计报告，并签发逐问题收据。跨 revision 的额外结果可以保留在
报告中，但不能混入另一 baseline 的问题收据。

## 独立统计

Oracle 不导入 `src`，只读 JSON 与最终 SVG。它先完整绑定逻辑节点、渲染节点、逻辑边、渲染边和
端口，再去重复/共线航点，区分：

- 不同网络正交线段的内部交叉事件与去重坐标；
- 端点接触、同网分叉和不同网共线重叠；
- 逐边曼哈顿长度、折点和相交边；
- 同一根网络的 split–rejoin 环；
- 低复用零入度根的可行位置反事实；
- 独占输入支路与固定目标端口的纵序反转。

“多余折点”或“根位置不佳”只在替代几何不碰节点/标签、不增加交叉或重叠、不增长，且目标指标
严格改善时成立。根按零入度且有输出判定，不按 `source`、`from` 或其它器件名特判。

## 复现顺序

1. 先运行生成器构建简单、边界、组合和压力 JSON；对全部产物形成问题结果矩阵。
2. 缺失问题只扩展相关特征：根类型、复用度、端口数、链深、消费行距、输入顺序、列自由度和规模。
3. 覆盖全部问题后比较失败样本与没有症状的样本，记录触发规律、反例和版本边界。
4. 最后才制作综合 example；它用于展示交互，不替代各冻结版本上的正式失败收据。
5. `reproduced` 只解锁产品修复；只有旧版失败、当前通过、邻近回归和 release 门全通过才可发布。

禁止改写 SVG、monkeypatch、故障注入或测试专用入口来签发自然复现。人工几何只可校准 Oracle。
