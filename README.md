# drawclock

根据时钟连接配置和指定的 draw.io 器件库生成从左到右、自包含的静态 SVG 时钟图。

源码运行需要 Python 3.9 或更高版本，不依赖第三方 Python 包。发行版可执行文件不要求安装 Python。

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg
```

末端 clock 可选填写 `func_freq`、`scan_freq`、`bist_freq`。输出会将末端逐行对齐，并在右侧按 `工作频率 / SCAN / BIST` 三列显示红色数值；未填项留空。示例为 `example/auto-layout/22-terminal-frequency-table.json`。

任意节点可填写字符串 `description`。`description_color` 设置该段注释的颜色；省略时使用 `#4b5563`。支持 CSS 命名色、3/4/6/8 位十六进制、`rgb()`、`rgba()`、`hsl()`、`hsla()` 和 `hwb()`。示例为 `example/auto-layout/33-description-colors.json`。

SVG 不显示输入文件名或文件名前缀标题。

## 命令行参数

| 长参数 | 短参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | :---: | --- | --- |
| `--input` | `-i` | 文件路径 | ✓ |  | JSON 配置 |
| `--library` | `-l` | 多个路径 | ✓ |  | 单器件 draw.io 库 XML 或目录 |
| `--output` | `-o` | 文件路径 | ✓ |  | 内容固定为 SVG，后缀不改变格式 |
| `--crossing-style` |  | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |
