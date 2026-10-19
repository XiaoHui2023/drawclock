# 绘图

## 命令

```text
drawclock -i <配置.json> -l <器件库.xml或目录> [<器件库.xml或目录> ...] -o <输出文件> [--title <标题>] [--crossing-style <风格>]
```

| 参数 | 取值 | 必填 | 默认值 | 说明 |
| --- | --- | :---: | --- | --- |
| `-i`, `--input` | 文件路径 | ✓ |  | JSON |
| `-l`, `--library` | 多个路径 | ✓ |  | 单器件库 XML 或目录；目录递归扫描 XML |
| `-o`, `--output` | 文件路径 | ✓ |  | 内容固定为 SVG |
| `--title` | 字符串 |  | `drawclock` | SVG 元数据标题，不在画布中显示 |
| `--crossing-style` | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |

## 配置

顶层键是实例名。每个实例只要求 `kind`；有前级时增加 `source`。`kind` 与指定器件库中的器件标题相同。

```json
{
  "osc": {"kind": "source"},
  "external_clk": {"kind": "from"},
  "select": {
    "kind": "mux2",
    "source": {"0": "osc", "1": "external_clk"}
  },
  "divider": {"kind": "div", "source": "select"},
  "clock": {"kind": "clock", "source": "divider"}
}
```

`source` 为字符串时连接默认输入端口；为对象时，键是输入端口序号。未列出的输入端口可以不连接。多输出器件用 `器件名[输出键]` 选择输出。

`layout_column` 是可选整数等级。数值越小越靠左，越大越靠右；相同数值的器件尽可能进入同一列。数值只表示顺序，`10` 与 `100` 不会保留中间空列。连接方向冲突时保持从左到右。

```json
{
  "a": {"kind": "from", "layout_column": 10},
  "b": {"kind": "from", "layout_column": 10},
  "select_a": {"kind": "mux2", "layout_column": 20, "source": {"0": "a"}},
  "select_b": {"kind": "mux2", "layout_column": 20, "source": {"0": "b"}}
}
```

末端节点通过 `table_values` 数组填写右侧数据表，元素为字符串或有限数字。列数取所有末端数组的最大长度，较短行的缺项留空；空数组不增加列。默认表头为“列 1”、“列 2”等，可全局设置。标题和值支持 `\n` 换行，默认居中，列宽按最长一行调整。所有末端独占一行并对齐到最右列，表格值为红色。字段不限定含义，可用于频率、电压、模式或其他需要并列展示的数据。

```json
{
  "clock_a": {
    "kind": "clock",
    "source": "gate_a",
    "table_values": ["800\nMHz", "0.90 V", "RUN", "primary"]
  },
  "clock_b": {"kind": "clock", "source": "gate_b", "table_values": [400]}
}
```

旧配置仍接受 `frequencies` 数组以及 `func_freq`、`scan_freq`、`bist_freq` 三个字段；它们只作为兼容输入。同一节点不能混填 `table_values` 与旧字段。

所有节点都可选填写字符串字段 `description`。相同列的注释共享文字排列边界；相同逻辑节点即使存在显示副本也只标一次。显式换行、空行和尾随换行会保留，长行自动换行。布局会预留文字空间；限定距离内没有安全位置时生成失败。

节点的 `description_align` 可为 `left`、`center`、`right`，默认 `left`。`description_anchor` 可为 `top-left`、`top`、`top-right`、`right`、`bottom-right`、`bottom`、`bottom-left`、`left`，默认 `top-left`。`description_offset_x`、`description_offset_y` 默认 `0`，单位为像素，正值分别向右、向下移动。避障会在所选方位内调整距离。

`description_color` 只修饰该节点的 `description`。省略时为 `#4b5563`。输入支持 CSS 命名色、3/4/6/8 位十六进制、RGB(A)、HSL(A) 和 HWB；输出统一为小写 `#rrggbb` 或 `#rrggbbaa`。动态值 `var()`、`currentColor`、`url()` 与宽色域函数不进入 SVG，配置阶段直接报错。

```json
{
  "pll_main": {
    "kind": "pll",
    "source": "xtal",
    "description": "主 PLL；上电后由固件配置倍频参数",
    "description_color": "hsl(271 81% 56%)",
    "description_align": "right",
    "description_anchor": "top-right",
    "description_offset_x": 12,
    "description_offset_y": -6
  }
}
```

纯文字排布示例为 `example/auto-layout/31-node-descriptions.json`；颜色输入示例为 `example/auto-layout/33-description-colors.json`。

输出画布不添加输入文件名或文件名前缀标题。`--title` 设置根 SVG 的可访问性 `<title>` 元数据，不会生成画布内文字。

实例名中的 `\n` 在图中显示为多行，名称对齐默认居中。解析 `source` 时会忽略实例名和引用中的 CR/LF，因此引用既可以写换行，也可以不写；空格等其他字符仍参与匹配。若两个实例名仅换行位置不同，配置会因引用有歧义而被拒绝。多输出后缀保持不变。

```json
{
  "PLL\nmain": {"kind": "gate"},
  "clock_a": {"kind": "clock", "source": "PLLmain"},
  "clock_b": {"kind": "clock", "source": "PLL\nmain"}
}
```

## Python 调用

`DrawingOptions` 设置整张图的默认值；节点显式填写的注释属性逐项覆盖全局值。`horizontal_spacing` 为列间最小距离，复杂布线可能使用更大距离。自定义表头数量必须与实际表格列数一致。

```python
from auto_layout import load_clock_tree
from elk_layout import generate_elk_layout
from layout_preview import write_preview_svg
from presentation import DrawingOptions

options = DrawingOptions(
    description_align="left",
    description_anchor="top-left",
    description_offset_x=0,
    description_offset_y=0,
    horizontal_spacing=160,
    name_align="center",
    table_headers=("工作\n频率", "电压", "模式", "备注"),
    table_align="center",
)
document, report = generate_elk_layout(
    load_clock_tree("clock.json"),
    library_path="drawio-lib/drawclock",
    options=options,
)
write_preview_svg(document, "clock.svg")
```

器件库可定义任意类型。布局只依据连接关系、库内几何、标签和端口计算，不按固定器件名或实例名分支。

每个器件库 XML 必须使用标准 draw.io `mxlibrary` 格式，并且只包含一个器件。文件名不参与器件识别，器件类型始终取文件内的 `title`。

多个文件按参数顺序合并；目录内 XML 按路径稳定排序后合并。不同文件出现同名器件时直接报错，避免无提示覆盖。`-l` 可以重复填写，并可同时传入多个文件和多个目录。

## 输出

器件、文字和连线均为原生 SVG 图元，不使用 XHTML、脚本或外部资源。输出文件可直接由浏览器、Ubuntu EOG 和 librsvg 打开，不需要 HTTP 服务。

器件库标签若包含无法转换为静态 SVG 的 HTML 元素、容器变换或外部资源，绘图会报错，不生成缺少器件的结果。

## 示例

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg
drawclock -i example/draw.json -l libraries/source.xml libraries/components -l libraries/project -o clock-tree.svg
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg --crossing-style gap
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg --title "Main clock tree"
drawclock -i example/auto-layout/22-terminal-data-table.json -l drawio-lib/drawclock -o terminal-data-table.svg
drawclock -i example/auto-layout/25-mixed-root-port-order-torture.json -l drawio-lib/drawclock -o mixed-root-torture.svg
```

`25-mixed-root-port-order-torture.json` 混合使用 `source`、`from` 和无上级的普通输出器件，交叉覆盖公共根复用、单连接根靠近 pad、固定输入端口顺序、共享干线与直连最少拐点。
