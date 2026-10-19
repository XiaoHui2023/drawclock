# drawclock

根据时钟连接配置和指定的 draw.io 器件库生成从左到右、自包含的静态 SVG 时钟图。

源码运行需要 Python 3.9 或更高版本，不依赖第三方 Python 包。发行版可执行文件不要求安装 Python。

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg
```

末端节点用 `table_values` 数组设置右侧数据表内容，列数由数组长度决定。表头可自定义，标题和值均支持换行，列宽随文字调整。

任意节点可填写字符串 `description`。`description_color` 设置该段注释的颜色；省略时使用 `#4b5563`。支持 CSS 命名色、3/4/6/8 位十六进制、`rgb()`、`rgba()`、`hsl()`、`hsla()` 和 `hwb()`。示例为 `example/auto-layout/33-description-colors.json`。

SVG 不显示输入文件名或文件名前缀标题。`--title` 只设置 SVG 的可访问性元数据标题，不在画布中增加文字。

## 命令行参数

| 长参数 | 短参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | :---: | --- | --- |
| `--input` | `-i` | 文件路径 | ✓ |  | JSON 配置 |
| `--library` | `-l` | 多个路径 | ✓ |  | 单器件 draw.io 库 XML 或目录 |
| `--output` | `-o` | 文件路径 | ✓ |  | 内容固定为 SVG，后缀不改变格式 |
| `--title` |  | 字符串 |  | `drawclock` | SVG 元数据标题，不在画布中显示 |
| `--crossing-style` |  | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |
| `--description-align` |  | `left` / `center` / `right` |  | `left` | 注释文字对齐 |
| `--description-anchor` |  | 八方位 |  | `top-left` | `top-left`、`top`、`top-right`、`right`、`bottom-right`、`bottom`、`bottom-left`、`left` |
| `--description-offset-x` |  | 数字 |  | `0` | 注释水平偏移，单位像素 |
| `--description-offset-y` |  | 数字 |  | `0` | 注释垂直偏移，单位像素 |
| `--horizontal-spacing` |  | 非负数字 |  |  | 列间最小距离，单位像素；布线需要时增加 |
| `--name-align` |  | `left` / `center` / `right` |  | `center` | 多行名称对齐 |
| `--table-headers` |  | 多个字符串 |  |  | 依次对应各列，可含换行 |
| `--table-align` |  | `left` / `center` / `right` |  | `center` | 表头和内容对齐 |
