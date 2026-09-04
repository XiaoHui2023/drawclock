# 自动布局示例

所有示例只需输入连接配置、器件库和一个输出文件：

```powershell
python src `
  -i example/auto-layout/03-mux-dag.json `
  -l drawio-lib/drawclock `
  -o example/generated/03-mux-dag.svg
```

输出内容固定为 SVG；文件后缀不改变格式。

| 级别 | 输入 | 覆盖场景 |
| --- | --- | --- |
| 1 | `01-linear.json` | 单根、单链、无分支 |
| 2 | `02-branch-tree.json` | 一对多分支的严格树 |
| 3 | `03-mux-dag.json` | 双根、mux 汇入 DAG |
| 4 | `04-dual-pll.json` | 双输出 PLL、端口选择和不同深度 |
| 5 | `05-dense-cross-root.json` | 三根、跨根汇入、长边和多类器件 |
| 简单压力 | `06-simple-16-clocks.json` | 38 nodes / 16 clocks |
| 中等压力 | `07-medium-64-clocks.json` | 136 nodes / 64 clocks |
| 复用回归 | `12-dual-from-reuse.json` | 两个共享 `from` / 16 条非对称 mux 分支；检查中间源分层与局部布线 |
| 文字与乱序 | `13-label-clearance-weave.json` | 136 nodes / 32 clocks；长实例名、双输出 PLL、两级 mux、交错复用 |
| 高交叉 | `14-crossing-weave-128-clocks.json` | 520 nodes / 128 clocks；多根、多级重汇合和大量允许跨线 |
| 多源簇 | `16-multi-from-clusters.json` | 多个共享输入源连接多组相似支路 |
| 末端排序 | `17-terminal-fanout-order.json` | 一分二末端与相邻单支路的交叉顺序 |
| 非对称列 | `18-asymmetric-merge-columns.json` | 长短不同的 mux 输入支路与汇聚列 |
| 复杂多源交错 | `19-dispersed-root-fanout.json` | 8 个独立 source、48 个 clock；覆盖非周期不定间隔直连、完整/稀疏 `pad3`、重叠根组合、PAD 扇出、PAD 与另一 source 经 mux 二次汇聚，以及不同链深和复用度 |
| 汇聚折线 | `20-asymmetric-merge-route-bulge.json` | 长短分支进入 mux 时的可避免外凸折线 |
| 列等级 | `21-layout-column-preference.json` | `10`、`20`、`30` 控制左右顺序，同等级器件共列 |
| 频率列 | `22-terminal-frequency-table.json` | 一行一个末端 clock，并显示工作频率、SCAN、BIST 三列 |
| 多层自由源列 | `23-middle-column-low-use-sources.json` | 公共源经共享链留在最前；直接服务 mux 的低复用源进入第 4 层、位于 mux 左侧，避免首列长线、交叉与多余折点 |
| 单源显示副本 | `24-single-source-rendering-alias.json` | 只有一个逻辑源；近端与远端消费带在质量向量更优时使用多个同名显示锚点 |
| 端口顺序组合 | `25-mixed-root-port-order-torture.json` | 混合根类型、固定多输入端口、非对称链深和输入顺序交互 |
| 反馈综合回归 | `26-feedback-reproduction-combined.json` | 公共根、低复用根、端口顺序、交叉区段与折点的综合质量场景 |
| 交替公共主干 | `27-interleaved-common-root-mux3.json` | 一个公共根与六个私有 `from` 分别接入六个稀疏连接的 `mux3`（输入 2 空置），每组继续 `cell→clock`；公共根保持一个图形和一条纵向主干 |

代表性复杂示例包含少量晶振和 PLL、复用的 mux、分频器、gate、多类 clock cell 和末端 clock。13 至 14 改变连接顺序、链深、复用源和实例名，不只是放大同一种阵列。坐标由输入连接关系以及当前器件库的尺寸、标签和端口一次计算得到，不进行成图后的坐标校准。

生成全部示例：

```powershell
python scripts/build_auto_layout_examples.py
```
