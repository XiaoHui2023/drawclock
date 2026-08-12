# draw

`draw` 使用指定的 draw.io 器件库，将时钟拓扑配置生成一个图文件。

## 命令

```text
drawclock draw -i <配置文件> -l <器件库.xml> -o <输出文件> [--crossing-style <风格>]
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-i, --input` | 是 | 配置文件。支持 `.json`、`.jsonc`、`.json5`、`.toml`、`.yaml`、`.yml`、`.ini`、`.conf`、`.config` |
| `-l, --library` | 是 | 本次生图使用的 draw.io 器件库 XML |
| `-o, --output` | 是 | 单个输出文件。支持 `.drawio`、`.svg`、`.png` |
| `--crossing-style` | 否 | 跨线风格：`arc`、`gap`、`sharp`、`none`；默认 `arc` |

输出格式由 `--output` 后缀确定。不支持的后缀会在读取配置和计算布局前报错。发布压缩包已经包含 PNG 渲染运行时，无需另装浏览器；源码运行时也可用 `CHROME_PATH` 指定浏览器。

## 输入

配置顶层是“器件名称 → 器件属性”：

```json
{
  "osc": {"kind": "source"},
  "clk": {"kind": "clock", "source": "osc"}
}
```

| 字段 | 说明 |
| --- | --- |
| `kind` | 必填。器件逻辑类型，必须与当前器件库兼容 |
| `source` | 根器件可省略；其它器件写上游器件名，多输入器件写输入名字到上游器件名的对象 |
| `component` | 可选。自动选择不能唯一确定时，写当前器件库中的图形 title |
| 其它字段 | 可选。作为器件属性写入图中，属性名与含义由当前器件库定义 |

多输出器件使用 `器件名[输出键]`。`draw` 中的 `from` 是普通根器件，可以像 `source` 一样连接到下游器件；这与 `extract` 合并跨图连接时对 `from` 的处理规则不同。

## 通用性

- 器件图形、尺寸、样式和端口均从 `--library` 指定的库读取，不依赖内置库坐标。
- `component` 省略时按 `kind`、输入/输出端口和连接名字自动选择兼容图形。
- `component` 只用于无法唯一确定的同类型图形；普通器件不需要填写。
- `source_kind`、`inv_kind`、`cell_kind` 等不是通用必填字段，只在当前器件库需要对应属性时填写。
- mux、PLL、cell 等同类器件可以由器件库提供任意兼容变体；配置通过端口键和 `component` 消除歧义。
- 布局固定从左到右，节点数量没有命令行上限。

## 示例

发布包中的 `example/draw.json` 覆盖一条最小完整链：

```text
source + from → mux2 → pll → div → dto → inv → cell → gate → clock
```

生成 draw.io 文件：

```text
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.drawio
```

生成 SVG 或 PNG 时只需更换输出后缀：

```text
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.png --crossing-style gap
```
