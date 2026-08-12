# drawclock

在 draw.io 时钟图与结构化时钟拓扑之间转换，也可以使用指定器件库自动生成从左到右的时钟图。

## draw：拓扑自动生图

```text
drawclock draw -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
```

参数、输入规则、器件库通用性和使用示例见 [draw.md](draw.md)。

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

`tools/pack.sh` 生成 PyInstaller + staticx Linux 可执行文件。发布流水线必须通过冻结后可执行文件的 `extract`、`reload`、固定 SVG 生成、任意输出后缀、自定义器件库和大图边界测试，才允许发布 Release。

## 示例

从简单链路到 4096 个末端时钟的输入位于 `example/auto-layout/`。生成脚本：

```powershell
python scripts/build_stress_examples.py
python scripts/build_auto_layout_examples.py
```
