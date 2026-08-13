# draw

`draw` 使用指定的 draw.io 器件库，将时钟拓扑配置生成一个成品图片。

## 命令

```text
drawclock draw -i <配置文件> -l <器件库.xml> -o <输出文件> [--crossing-style <风格>]
```

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-i, --input` | 是 | 配置文件。支持 `.json`、`.jsonc`、`.json5`、`.toml`、`.yaml`、`.yml`、`.ini`、`.conf`、`.config` |
| `-l, --library` | 是 | 本次生图使用的 draw.io 器件库 XML |
| `-o, --output` | 是 | 单个输出文件；内容始终是 SVG |
| `--crossing-style` | 否 | 跨线风格：`arc`、`gap`、`sharp`、`none`；默认 `arc` |

`draw` 只会写入 SVG，不根据 `--output` 的后缀选择格式。例如输出名为 `clock.png`、`clock.drawio` 或没有后缀，文件内容仍然是 SVG XML。发布包不包含浏览器或 PNG 渲染运行时。

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
| `kind` | 必填。直接填写当前器件库中的器件 title，例如 `mux2` |
| `source` | 根器件可省略；其它器件写上游器件名，多输入器件写输入名字到上游器件名的对象 |
| 其它字段 | 可选。作为器件属性写入图中，属性名与含义由当前器件库定义 |

多输出器件使用 `器件名[输出键]`。`draw` 中的 `from` 是普通根器件，可以像 `source` 一样连接到下游器件；这与 `extract` 合并跨图连接时对 `from` 的处理规则不同。

## 通用性

- 器件图形、尺寸、样式和端口均从 `--library` 指定的库读取，不依赖内置库坐标。
- `kind` 直接、唯一选择器件库 title；不会根据已连接端口数量猜测器件。
- `source_kind`、`inv_kind`、`cell_kind` 等不是通用必填字段，只在当前器件库需要对应属性时填写。
- 多输入器件只需填写实际连接的输入键，未连接端口可以省略。例如 `mux2` 可只连接 `0`、只连接 `1`，或同时连接两路。
- 布局固定从左到右，节点数量没有命令行上限。

## 布局

- 末端 `clock` 对齐在最右层。根源使用最晚可行层；较短分支的源可以位于中间，前提是所有连线仍从左向右。
- 普通一入一出链优先对齐端口轴；mux 按实际连接的固定端口顺序排列。
- 连线为正交折线。长连线在所属时钟域内选择近端、无障碍的走廊，不默认绕到全图顶部或底部。
- 同一源端口的多个分支共用一条纵向主干；不同网络不共用长共线段。

## 示例

发布包中的 `example/draw.json` 覆盖一条最小完整链：

```text
source + from → mux2 → pll → div → dto → inv → cell → gate → clock
```

生成 SVG：

```text
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg --crossing-style gap
```
