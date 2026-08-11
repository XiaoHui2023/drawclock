# JSON 自动布局 examples

示例按复杂度递增：

| 级别 | 输入 | 覆盖场景 |
| --- | --- | --- |
| 1 | `01-linear.json` | 单根、单链、无分叉 |
| 2 | `02-branch-tree.json` | 一对多分叉的严格树 |
| 3 | `03-mux-dag.json` | 双根、mux fan-in，已经不是严格树 |
| 4 | `04-dual-pll.json` | 双输出 PLL、端口选择器和不同深度 |
| 5 | `05-dense-cross-root.json` | 三根、两个 mux、跨根汇入、fan-out、长边和多类器件 |

从仓库根目录运行：

```powershell
python scripts/build_auto_layout_examples.py
```

也可以单独生成一个示例：

```powershell
python src draw `
  -i example/auto-layout/03-mux-dag.json `
  -l drawio-lib/drawclock.xml `
  -o example/generated/03-mux-dag.drawio `
  --preview example/generated/03-mux-dag.svg
```

含 PLL 的示例还要提供明确器件形状：

```powershell
python src draw `
  -i example/auto-layout/04-dual-pll.json `
  --hints example/auto-layout/04-dual-pll.hints.json `
  -l drawio-lib/drawclock.xml `
  -o example/generated/04-dual-pll.drawio `
  --preview example/generated/04-dual-pll.svg
```

## ELK 压力阶梯

| 级别 | JSON | 规模 |
| --- | --- | --- |
| 简单压力 | `06-simple-16-clocks.json` | 38 nodes / 16 clocks |
| 中等压力 | `07-medium-64-clocks.json` | 136 nodes / 64 clocks |
| 极限压力 | `08-stress-512-clocks.json` | 1046 nodes / 512 clocks |
| 大规模 | `09-stress-1024-clocks.json` | 2086 nodes / 1024 clocks |
| 超大规模 | `10-stress-2048-clocks.json` | 4166 nodes / 2048 clocks |
| 极限规模 | `11-stress-4096-clocks.json` | 8326 nodes / 4096 clocks |

示例 6–11 包含 2 个晶振、4 个大量复用的 PLL、mux、分频器、gate、多类
clock cell 和末端 clock。512 及以下使用 ELK Layered；1024 及以上使用
backbone + 弱连通时钟域分解的线性分层布局。两条路径都保留固定端口和正交
连线。首次运行前执行
`npm install --ignore-scripts`。图由 JSON、器件尺寸和端口一次计算得出，没有
针对成图结果做坐标校准。

`example/generated` 中的 `.drawio` 和 `.svg` 是上述脚本的可复现产物；PNG 是视觉快照。
