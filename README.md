# drawclock

从 draw.io 时钟树图生成时钟树逻辑 JSON，或用新器件库刷新旧图。

## 目录

| 路径 | 说明 |
| --- | --- |
| `src/` | 主功能：draw.io → `clock-tree.json`（仅器件库图形参与逻辑与校验） |
| `reload/` | 旧 draw.io + 新器件库 XML → 新 draw.io（刷新样式，保留坐标与非器件库内容） |
| `drawio-lib/` | draw.io 自定义组件库；用法见 [drawio-lib/README.md](drawio-lib/README.md) |
| `example/` | 可运行示例；说明见 [example/README.md](example/README.md) |
| `docs/clock-tree-json.md` | **`clock-tree.json` 数据结构**（各 `kind` 记录字段） |

## src：提取 clock-tree.json

运行：`python src -i <文件>… -l <库.xml> [-o <json文件>]`

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件路径（可多次） | 必填 | 一个或多个 `.drawio.svg` / `.drawio` |
| `--output` | `-o` | 文件 | | 输出的 JSON 文件路径；未指定时打印到标准输出 |
| `--library` | `-l` | 文件 | 必填 | 器件库，用于校验 `drawclockType` |

行为说明：

- 仅带 **`drawclockType`** 的器件库图形参与连线逻辑与 JSON；文本框等其它图形**忽略**。
- 同名 **wire** 多段图形在 JSON 中**合并**为一条（`source` 左端 + `targets` 右端列表）；左端至多一个，合并后仍须满足校验。
- 记录字段见 [docs/clock-tree-json.md](docs/clock-tree-json.md)；导出规则见项目 design-notes skill。

## reload：刷新器件库样式

运行：`python reload -i <旧图> -l <新库.xml> -o <新图.drawio>`（打包后：`dist/drawclock-reload.exe`，参数相同）

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件 | 必填 | 旧 `.drawio` / `.drawio.svg`（含压缩 diagram） |
| `--library` | `-l` | 文件 | 必填 | 新器件库 `drawclock.xml` |
| `--output` | `-o` | 文件 | 必填 | 输出的 `.drawio` |

- 器件库图形：换成新库的 **style** 与 **label 模板**（`%name%` 等占位符、`placeholders=1`，双击可编辑变量）；方框 **宽高** 为库默认；**保留** `x`/`y` 与 `name`、`freq`、`in*_label` 等属性值。
- 非器件库图形与连线：**原样保留**。
- 两端均为器件库的连线：按新库 `points` 重算 `exitX` / `entryY` / `entryX` / `entryY`（方框变宽后仍贴在端口上）；**航点**（`mxGeometry` 内 `mxPoint`）原样保留。

## 示例

仓库根目录执行 `example.bat`（五步：建库 → 生成 fig1/fig2 → `src` → **reload** → **pytest**）。说明见 [example/README.md](example/README.md)。

改 `example/` 下图或生成脚本后，须跑完整 `example.bat`（reload 为必验环节）。

## 开发与测试

| 操作 | 命令 |
| --- | --- |
| 安装依赖 | `update.bat` |
| 运行示例（含 reload 与 reload 测试） | `example.bat` |
| 运行全量测试 | `test.bat` |
| 打包 CLI | `pack.bat`（产物 `dist/drawclock.exe`、`dist/drawclock-reload.exe`；说明见 [PACKAGING.md](PACKAGING.md)） |
