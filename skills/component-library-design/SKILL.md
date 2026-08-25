---
name: component-library-design
description: 为 drawclock 设计或审查通用 draw.io 器件库时使用，覆盖 mxlibrary 合约、器件几何、端口、标签、现有器件和验证方法。
---

# 器件库通用设计

先把器件库视为布局输入的一部分：形状的尺寸、可见图形、标签占用和连接点必须来自同一份几何定义。不要按器件名称在布局器中写特例。

## 使用流程

1. 阅读[库文件与器件合约](references/library-contract.md)，确定文件、title、模板和元数据边界。
2. 阅读[几何、标签与端口](references/geometry-and-ports.md)，从可见图形计算尺寸和连接点。
3. 按需查阅[当前器件目录](references/component-catalog.md)，复用已有家族的视觉语法。
4. 实现后执行[构建与验证](references/build-and-validation.md)中的结构、几何、预览和端到端门禁。
5. 需要判断资料依据时查看[参考资料](references/sources.md)。

## 不变量

- JSON 的 `kind` 直接等于库条目的 `title`；库外名称映射不属于通用合约。
- 端口锚点落在可见引脚端点上，不落在外层选择框或标签框上。
- 库条目的 `w`、`h`、mxGeometry、SVG/viewBox 和端口相对坐标使用同一几何来源。
- 标签可以超出器件本体，但必须计入布局的可见占用范围。
- 新器件通过数据和共享几何进入系统，不在自动布局代码中增加名称判断。
