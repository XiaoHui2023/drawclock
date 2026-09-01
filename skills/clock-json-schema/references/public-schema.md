# 公开结构与字段

概念结构：

```text
ClockTree := { InstanceName: Device }
Device := {
  "kind": LibraryTitle,
  "source"?: SourceRef | { InputKey: SourceRef },
  "layout_column"?: Integer,
  "func_freq"?: String | Number,
  "scan_freq"?: String | Number,
  "bist_freq"?: String | Number,
  ...libraryDisplayAttributes
}
```

## 字段

| 字段 | 必需 | 类型 | 规则 |
| --- | :---: | --- | --- |
| 顶层实例名 | 是 | 非空字符串键 | 在文件内唯一；用于 source 引用和显示名称 |
| `kind` | 是 | 非空字符串 | 必须精确匹配合并器件库中的一个 title |
| `source` | 否 | 字符串或非空对象 | 单输入可用字符串；多输入对象的键是目标输入连接键 |
| `layout_column` | 否 | 整数 | 越小越左、越大越右、同值尽量同列；布尔值不算整数 |
| `func_freq` | 否 | 字符串或数字 | 末端工作频率；缺省时输出空白 |
| `scan_freq` | 否 | 字符串或数字 | 末端 SCAN 频率；缺省时输出空白 |
| `bist_freq` | 否 | 字符串或数字 | 末端 BIST 频率；缺省时输出空白 |
| 其他属性 | 否 | JSON 标量为宜 | 仅供器件标签/对象元数据使用，不参与通用连接推断 |

不应写入 `component`、`hints`、坐标、宽高、waypoints 或任意 `*_kind` 并行类型字段。器件库变化时，只需让 kind 指向真实 title。

文件扩展名必须为 `.json`，编码为 UTF-8 或带 BOM 的 UTF-8；不接受 JSONC、JSON5、YAML、TOML、INI 和顶层数组。
