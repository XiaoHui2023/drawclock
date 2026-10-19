# 绘图示例

`draw.json` 各使用一种源、`from`、mux、PLL、分频器、DTO、反相器、cell、gate 和末端 clock。

发行包已经包含全部 `auto-layout/*.json`。`run-example/` 中每个脚本只演示一个方面，并把 SVG 生成到调用时的当前工作目录。Linux/macOS 使用 `.sh`，Windows 使用同名 `.bat`。

```sh
./run-example/01-basic.sh
./run-example/02-title.sh custom.svg "Custom clock tree"
```

```bat
run-example\01-basic.bat
run-example\02-title.bat custom.svg "Custom clock tree"
```

| 脚本 | 演示内容 | 可选的第二个参数 |
| --- | --- | --- |
| `01-basic` | 最小绘图调用 |  |
| `02-title` | SVG 元数据标题 | 标题 |
| `03-table-headers` | 通用数据表表头和对齐 |  |
| `04-horizontal-spacing` | 横向最小间距 | 像素值 |
| `05-descriptions` | 注释对齐、方位和偏移 |  |
| `06-text-alignment` | 节点名和数据表文字对齐 |  |
| `07-crossing-style` | 跨线样式 | `arc` / `gap` / `sharp` / `none` |

所有脚本的第一个可选参数都是输出路径。标题只进入 SVG 的 `<title>` 元数据，不会在画布上增加文字。

源码仓库中也可以直接运行：

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o example/generated/draw.svg
```

`auto-layout/` 包含线性、分支、复用、交叉和最多 128 个末端时钟的代表性复杂配置。
