# 自动布局示例

所有示例只需输入拓扑、器件库和一个输出文件：

```powershell
python src draw `
  -i example/auto-layout/03-mux-dag.json `
  -l drawio-lib/drawclock.xml `
  -o example/generated/03-mux-dag.svg
```

`draw` 固定写入 SVG，不需要格式参数；输出后缀不会改变文件内容。

| 级别 | 输入 | 覆盖场景 |
| --- | --- | --- |
| 1 | `01-linear.json` | 单根、单链、无分支 |
| 2 | `02-branch-tree.json` | 一对多分支的严格树 |
| 3 | `03-mux-dag.json` | 双根、mux 汇入 DAG |
| 4 | `04-dual-pll.json` | 双输出 PLL、端口选择和不同深度 |
| 5 | `05-dense-cross-root.json` | 三根、跨根汇入、长边和多类器件 |
| 简单压力 | `06-simple-16-clocks.json` | 38 nodes / 16 clocks |
| 中等压力 | `07-medium-64-clocks.json` | 136 nodes / 64 clocks |
| 压力 | `08-stress-512-clocks.json` | 1046 nodes / 512 clocks |
| 大规模 | `09-stress-1024-clocks.json` | 2086 nodes / 1024 clocks |
| 超大规模 | `10-stress-2048-clocks.json` | 4166 nodes / 2048 clocks |
| 极限规模 | `11-stress-4096-clocks.json` | 8326 nodes / 4096 clocks |
| 复用回归 | `12-dual-from-reuse.json` | 两个共享 `from` / 16 条非对称 mux 分支；检查中间源分层与局部布线 |
| 文字与乱序 | `13-label-clearance-weave.json` | 136 nodes / 32 clocks；长实例名、双输出 PLL、两级 mux、交错复用 |
| 高交叉 | `14-crossing-weave-128-clocks.json` | 520 nodes / 128 clocks；多根、多级重汇合和大量允许跨线 |
| 综合折磨 | `15-routing-torture-512-clocks.json` | 1288 nodes / 512 clocks；长文字、高复用、跨层边和多级 mux 同时出现 |

压力示例包含少量晶振和 PLL、大量复用的 mux、分频器、gate、多类 clock cell 和末端 clock。后三个对抗示例改变连接顺序、链深、复用源和实例名，不只是放大同一种阵列。坐标由输入拓扑以及当前器件库的尺寸、标签和端口一次计算得到，不进行成图后的坐标校准。

生成全部示例：

```powershell
python scripts/build_auto_layout_examples.py
```
