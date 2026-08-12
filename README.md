# drawclock

在 draw.io 时钟图与结构化时钟拓扑之间转换，也可以使用指定器件库自动生成从左到右的时钟图。

## draw：拓扑自动生图

`draw` 每次只生成一个输出文件。输出格式完全由 `--output` 后缀决定：

```powershell
drawclock draw -i clock-tree.json -l drawio-lib/drawclock.xml -o clock-tree.drawio
drawclock draw -i clock-tree.yaml -l drawio-lib/drawclock.xml -o clock-tree.svg
drawclock draw -i clock-tree.toml -l drawio-lib/drawclock.xml -o clock-tree.png --crossing-style gap
```

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件 | 必填 | 时钟拓扑配置 |
| `--library` | `-l` | 文件 | 必填 | 本次生成使用的 draw.io 器件库 XML |
| `--output` | `-o` | 文件 | 必填 | `.drawio`、`.svg` 或 `.png` |
| `--crossing-style` |  | 枚举 | `arc` | `arc`、`gap`、`sharp` 或 `none` |

程序在读取输入和计算布局之前检查输出后缀。不支持的后缀会立即报错并列出兼容格式，不会产生半成品。

PNG 使用 Microsoft Edge、Google Chrome 或 Chromium 渲染器，以正确处理器件库中的 HTML/SVG 图形；可通过 `CHROME_PATH` 指定兼容浏览器。机器没有兼容浏览器时会在布局开始前报错。SVG 是不依赖浏览器的矢量输出，适合超大规模图。

### 输入格式

输入由 Python `config-library`（导入名 `configlib`）统一加载，支持：

- `.json`、`.jsonc`、`.json5`
- `.toml`
- `.yaml`、`.yml`
- `.ini`、`.conf`、`.config`

无论文件格式如何，加载结果的顶层都必须是“器件名称 → 属性对象”。完整字段规则见 [json.md](json.md)。

### 自动策略

用户不需要选择 engine、profile、candidate、hints 或预览模式：

- 程序根据图结构自动选择全局分层或高复用时钟域分解；ELK 运行环境可用时使用固定端口的 ELK Layered，否则使用内置确定性分层布局。
- 内部比较确定性候选，并按正确性、交叉、重叠、折点、线长和面积依次选取结果。
- 器件解析只使用当前 `--library` 中的类型元数据、子类型、端口数量、端口键、尺寸和样式，不写死某个器件库的坐标或尺寸。
- JSON 中可用 `component` 明确指定当前库的 title；未指定时，程序选择满足类型和端口约束的最小兼容图形。
- 节点数量没有产品参数上限；大规模高复用网络由结构特征触发分解，不按固定节点数量切换。

## extract：图转拓扑

```powershell
drawclock extract -i fig1.drawio fig2.drawio -l drawio-lib/drawclock.xml -o clock-tree.json
```

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件路径（一个或多个） | 必填 | `.drawio.svg` 或 `.drawio` |
| `--library` | `-l` | 文件 | 必填 | 解析时使用的器件库 |
| `--output` | `-o` | 文件 | 标准输出 | 拓扑 JSON |

兼容别名为 `drawio-to-json` 和旧名称 `run`；新脚本使用 `extract`。

## reload：刷新旧图

```powershell
drawclock reload -i old.drawio -l drawio-lib/drawclock.xml -o refreshed.drawio
```

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件或目录 | 必填 | `.drawio` / `.drawio.svg` |
| `--library` | `-l` | 文件 | 必填 | 新器件库 XML |
| `--output` | `-o` | 文件或目录 | 必填 | 单文件输出或批量输出目录 |

## 静态包

`tools/pack.sh` 生成 PyInstaller + staticx Linux 可执行文件。发布流水线必须通过冻结后可执行文件的 `extract`、`reload`、JSON→draw.io、JSON→SVG、JSON→PNG、拓扑回环和非法后缀前置拒绝测试，才允许发布 Release。

## 示例

从简单链路到 4096 个末端时钟的输入位于 `example/auto-layout/`。生成脚本：

```powershell
python scripts/build_stress_examples.py
python scripts/build_auto_layout_examples.py
```
