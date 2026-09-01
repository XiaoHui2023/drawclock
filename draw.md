# 绘图

## 命令

```text
drawclock -i <配置.json> -l <器件库.xml或目录> [<器件库.xml或目录> ...] -o <输出文件> [--crossing-style <风格>]
```

| 参数 | 取值 | 必填 | 默认值 | 说明 |
| --- | --- | :---: | --- | --- |
| `-i`, `--input` | 文件路径 | ✓ |  | JSON |
| `-l`, `--library` | 多个路径 | ✓ |  | 单器件库 XML 或目录；目录递归扫描 XML |
| `-o`, `--output` | 文件路径 | ✓ |  | 内容固定为 SVG |
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

末端 clock 可选填写 `func_freq`、`scan_freq`、`bist_freq`，值为字符串或数字。所有末端独占一行并对齐到最右列；后方依次显示“工作频率”、“SCAN”、“BIST”。频率值为红色，未填字段保持空白。

```json
{
  "clock_a": {
    "kind": "clock",
    "source": "gate_a",
    "func_freq": "800 MHz",
    "scan_freq": "50 MHz",
    "bist_freq": "100 MHz"
  },
  "clock_b": {"kind": "clock", "source": "gate_b", "func_freq": 400}
}
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
drawclock -i example/auto-layout/22-terminal-frequency-table.json -l drawio-lib/drawclock -o terminal-frequency.svg
```
