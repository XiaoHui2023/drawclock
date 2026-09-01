---
name: svg-artifact-design
description: 设计或修改 drawclock 最终 SVG 表现层时使用，覆盖原生图元组合、器件标签转换、文字、画布与视觉质量门。
---

# SVG 成品设计

最终文件是自包含的静态矢量成品。器件、文字、连线和跨线符号使用同一 SVG 坐标系；不得依赖浏览器的 HTML 排版、脚本或生成后的坐标修补。

## 阅读路径

1. 修改表现层结构时读取[原生 SVG 组合](references/native-composition.md)。
2. 接入新器件库标签时读取[器件标签转换](references/library-label-conversion.md)。
3. 调整文字、边界或视觉验收时读取[视觉质量门](references/visual-quality.md)。

布局只提供节点、端口和路线坐标。表现层不得重新路由、移动端点或按器件名称改变几何。
