---
name: clock-json-schema
description: 设计、生成或审查 drawclock 输入 JSON 和内部数据结构时使用，说明字段、端口引用、生成规则、验证顺序与兼容边界。
---

# 时钟连接 JSON 设计

输入是严格 JSON，顶层对象把“实例名”映射到“器件属性对象”。JSON 只描述逻辑连接和少量布局意图，不保存坐标、waypoint 或渲染副本。

## 使用流程

1. 按[公开结构与字段](references/public-schema.md)建立最小数据模型。
2. 按[端口与 source 引用](references/source-references.md)生成连接。
3. 按[生成与验证规则](references/generation-and-validation.md)保证确定性和错误前置。
4. 从[示例与反例](references/examples.md)选择最接近的起点。
5. 需要通用 schema 原则时查看[参考资料](references/sources.md)。

## 核心原则

- `kind` 是唯一必需字段，值直接等于所加载器件库的 title。
- `source` 和 `layout_column` 都是可选字段。
- 未连接的器件端口合法；不要用空 source 对象表示“没有连接”。
- 逻辑名称唯一且稳定；布局坐标由器件库和连接关系计算。
