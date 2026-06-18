# drawclock

从 draw.io 时钟树图生成时钟树逻辑 JSON，或用新器件库刷新旧图。

## run

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件路径（可多次） | 必填 | `.drawio.svg` / `.drawio` |
| `--output` | `-o` | 文件 | | 未指定则标准输出 |
| `--library` | `-l` | 文件 | 必填 | |

## reload

| 长参数 | 短参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `--input` | `-i` | 文件 | 必填 | `.drawio` / `.drawio.svg` |
| `--library` | `-l` | 文件 | 必填 | `drawclock.xml` |
| `--output` | `-o` | 文件 | 必填 | `.drawio` |
