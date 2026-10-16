# 公开结构与字段

概念结构：

```text
ClockTree := { InstanceName: Device }
Device := {
  "kind": LibraryTitle,
  "source"?: SourceRef | { InputKey: SourceRef },
  "layout_column"?: Integer,
  "description"?: String,
  "description_align"?: "left" | "center" | "right",
  "description_anchor"?: Direction,
  "description_offset_x"?: Number,
  "description_offset_y"?: Number,
  "frequencies"?: Array<String | Number>,
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
| `description` | 否 | 字符串 | 注释，保留换行与空行 |
| `description_align` | 否 | `left` / `center` / `right` | 覆盖全局注释文字对齐 |
| `description_anchor` | 否 | 八方位 | `top-left`、`top`、`top-right`、`right`、`bottom-right`、`bottom`、`bottom-left`、`left` |
| `description_offset_x` / `description_offset_y` | 否 | 有限数字 | 像素偏移；正值向右/下，布尔值无效 |
| `frequencies` | 否 | 字符串或有限数字数组 | 元素次序对应表格列，支持换行；空数组不增加列 |
| 其他属性 | 否 | JSON 标量为宜 | 仅供器件标签/对象元数据使用，不参与通用连接推断 |

不应写入 `component`、`hints`、坐标、宽高、waypoints 或任意 `*_kind` 并行类型字段。器件库变化时，只需让 kind 指向真实 title。

实例名允许换行，显示为多行文字；引用保留完整原名，不移除空白、不合并实例。全局`DrawingOptions`提供注释默认值、横距、名称对齐和频率表标题/对齐，只有显式节点注释字段逐项覆盖对应全局值。

旧`func_freq`、`scan_freq`、`bist_freq`仅作为兼容输入，同一节点不得与`frequencies`混填。

文件扩展名必须为 `.json`，编码为 UTF-8 或带 BOM 的 UTF-8；不接受 JSONC、JSON5、YAML、TOML、INI 和顶层数组。
