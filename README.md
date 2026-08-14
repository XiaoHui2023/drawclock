# drawclock

根据时钟连接配置和指定的 draw.io 器件库生成从左到右的 SVG 时钟图。

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
```

## 命令行参数

| 长参数 | 短参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | :---: | --- | --- |
| `--input` | `-i` | 文件路径 | ✓ |  | JSON、JSONC、JSON5、TOML、YAML 或 INI 配置 |
| `--library` | `-l` | 文件路径 | ✓ |  | draw.io 器件库 XML |
| `--output` | `-o` | 文件路径 | ✓ |  | 内容固定为 SVG，后缀不改变格式 |
| `--crossing-style` |  | `arc` / `gap` / `sharp` / `none` |  | `arc` | 跨线样式 |
