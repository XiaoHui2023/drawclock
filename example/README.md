# 绘图示例

`draw.json` 各使用一种源、`from`、mux、PLL、分频器、DTO、反相器、cell、gate 和末端 clock。

发行包已经包含全部 `auto-layout/*.json`。在解压包的 `example` 目录运行对应平台脚本，会把 `drawclock-example.svg` 生成到当前工作目录：

```sh
./run-example.sh
./run-example.sh custom.svg "Custom clock tree"
```

```bat
run-example.bat
run-example.bat custom.svg "Custom clock tree"
```

脚本展示输入、器件库、输出、SVG 元数据标题、跨线样式、注释位置、列间距、名称对齐和频率表头参数。标题只进入 SVG 的 `<title>` 元数据，不会在画布上增加文字。

源码仓库中也可以直接运行：

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o example/generated/draw.svg
```

`auto-layout/` 包含线性、分支、复用、交叉和最多 128 个末端时钟的代表性复杂配置。
