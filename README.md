# drawclock

从 draw.io 时钟树图生成时钟树相关输出的本地命令行工具。

## 目录

| 路径 | 说明 |
| --- | --- |
| `drawio-lib/` | draw.io 自定义组件库；用法见 [drawio-lib/README.md](drawio-lib/README.md) |
| `example/` | 可运行示例；说明见 [example/README.md](example/README.md) |

## 命令行参数

运行：`python src <子命令> …`

### encode（draw.io → JSON）

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件路径（可多次指定） | 必填 | 一个或多个 `.drawio.svg` / `.drawio` 源文件，多文件合并解析 |
| `--output` | `-o` | 目录 | | 输出目录；写入 `clock-tree.json`；未指定时仅配置 JSON 打印到标准输出 |
| `--layout` | | 开关 | 关 | 同时写入 `drawio-layout.json`（节点坐标与尺寸、连线样式、航点、对象属性、`mxCell` 样式）；使用本开关时必须指定 `-o` |

`clock-tree.json`：时钟树逻辑（`name`、`kind`、`source` / `target`、`connections` 等）。  
`drawio-layout.json`：画布几何与 draw.io 编辑数据，与配置 JSON 配套供 decode 还原图形。

### decode（JSON → draw.io）

| 长参数 | 类型 | 说明 |
| --- | --- | --- |
| `--config` | 文件 | `clock-tree.json` |
| `--layout` | 文件 | `drawio-layout.json` |
| `--library` | 文件 | `drawio-lib/drawclock.xml` |
| `--output` / `-o` | 文件 | 输出的 `.drawio` 路径 |

decode 会校验配置与布局中的器件名、类型一致，并确认布局中的 `drawclockType` 均存在于器件库。

## 示例

仓库根目录执行 `example.bat`，读取 `example/demo.drawio`，在 `example/out/` 生成 `clock-tree.json` 与 `drawio-layout.json`。

往返还原：

```bat
python src decode --config example\out\clock-tree.json --layout example\out\drawio-layout.json --library drawio-lib\drawclock.xml -o example\out\restored.drawio
python src encode -i example\out\restored.drawio -o example\out --layout
```

第二次 encode 得到的两个 JSON 应与第一次一致（无损往返）。

## 开发与测试

| 操作 | 命令 |
| --- | --- |
| 安装依赖 | `update.bat` |
| 运行示例 | `example.bat` |
| 运行测试 | `test.bat` |
| 打包单文件 CLI | `pack.bat`（产物 `dist/drawclock.exe`；说明见 [PACKAGING.md](PACKAGING.md)） |
