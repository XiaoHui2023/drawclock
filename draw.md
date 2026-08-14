# 绘图

## 命令

```text
drawclock -i <配置文件> -l <器件库.xml> -o <输出文件> [--crossing-style <风格>]
```

| 参数 | 取值 | 必填 | 默认值 | 说明 |
| --- | --- | :---: | --- | --- |
| `-i`, `--input` | 文件路径 | ✓ |  | JSON、JSONC、JSON5、TOML、YAML、YML、INI、CONF 或 CONFIG |
| `-l`, `--library` | 文件路径 | ✓ |  | 每次按该库解析器件类型、尺寸、标签和端口 |
| `-o`, `--output` | 文件路径 | ✓ |  | 内容固定为 SVG |
| `--crossing-style` | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |

## 配置

顶层键是实例名。每个实例只要求 `kind`；有前级时增加 `source`。`kind` 必须与指定器件库中的器件标题相同。

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

器件库可定义任意类型。布局只依据连接关系、库内几何、标签和端口计算，不按固定器件名或实例名分支。

## 示例

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
drawclock -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg --crossing-style gap
```
