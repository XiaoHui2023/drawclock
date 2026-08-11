# drawclock

在 draw.io 时钟树图与逻辑 JSON 之间双向转换，支持自动布局，并可用新器件库刷新旧图。

## extract（图转 JSON）

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件路径（可多次） | 必填 | `.drawio.svg` / `.drawio` |
| `--output` | `-o` | 文件 | | 未指定则标准输出 |
| `--library` | `-l` | 文件 | 必填 | |

兼容别名为 `drawio-to-json` 和旧名称 `run`；新脚本和文档使用 `extract`。

## draw（JSON 自动布局成图）

```powershell
python src draw -i clock-tree.json -l drawio-lib/drawclock.xml `
  -o clock-tree.drawio --crossing-style gap `
  --preview clock-tree.png --preview-format png
```

`--crossing-style` 可选 `arc`、`gap`、`sharp`、`none`，默认 `arc`。draw.io
文件保存对应的原生 jump style；独立 SVG/PNG 预览使用白色断口表达 `arc`、`gap`
和 `sharp`，`none` 不处理跨线。

`--preview-format` 可选 `auto`、`svg`、`png`。`auto` 根据 `--preview` 的
`.svg`/`.png` 后缀判断；PNG 使用真实 Edge/Chrome 渲染 `foreignObject` 器件，
并通过 `--preview-max-size` 控制最长边，默认 16384 px。SVG 保留完整矢量图，
更适合查看 1024 个以上末端时钟的超长图。

推荐先在仓库根目录运行一次 `npm install --ignore-scripts`。`--engine auto`
（默认）会优先使用 ELK Layered 的固定端口、从左到右、正交布局；依赖不可用时
回退到纯 Python `native` 引擎。可用 `--engine elk` 强制要求 ELK，或用
`--engine native` 明确选择原引擎。React Flow 是渲染/交互层，不是布局引擎，
因此没有作为布局依赖引入。

压力示例分为 16、64、512、1024、2048、4096 个末端 clock。自动策略不按
节点总数硬切换，而是从扇出分布、跨层边负载和剩余连通域判断是否分解
高复用 backbone，并在每个域内保持
mux → 分频器 → gate → cell → clock 的横向链；所有坐标仍由拓扑、器件尺寸
和端口一次计算得到。

```powershell
python scripts/build_stress_examples.py
python scripts/build_auto_layout_examples.py
```

布局使用器件库的真实尺寸和端口，执行从左到右分层、确定性候选排序和障碍感知正交布线。`pll`/`pll2` 等无法仅由拓扑唯一确定的形状必须通过 `--hints` 指定。完整的递增示例见 `example/auto-layout/README.md`。

布局由当前 JSON 和器件库一次计算得到，不对生成后的示例图做坐标校准。器件尺寸、端口位置或连接关系变化时会重新计算全部约束。

## reload

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件或目录 | 必填 | 支持 `.drawio` / `.drawio.svg` 格式 |
| `--library` | `-l` | 文件 | 必填 | `drawclock.xml` |
| `--output` | `-o` | 文件或目录 | 必填 | 单文件输出路径，或批量输出目录 |
