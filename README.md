# drawclock

根据时钟连接配置和指定的 draw.io 器件库生成从左到右、自包含的静态 SVG 时钟图。

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg
```

末端 clock 可选填写 `func_freq`、`scan_freq`、`bist_freq`。输出会将末端逐行对齐，并在右侧按“工作频率 / SCAN / BIST”三列显示红色数值；未填项留空。完整示例见 `example/auto-layout/22-terminal-frequency-table.json`。

## 命令行参数

| 长参数 | 短参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | :---: | --- | --- |
| `--input` | `-i` | 文件路径 | ✓ |  | JSON 配置 |
| `--library` | `-l` | 多个路径 | ✓ |  | 单器件 draw.io 库 XML 或目录 |
| `--output` | `-o` | 文件路径 | ✓ |  | 内容固定为 SVG，后缀不改变格式 |
| `--crossing-style` |  | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |
