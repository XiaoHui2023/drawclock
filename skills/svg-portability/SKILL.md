---
name: svg-portability
description: 分析或验证 drawclock SVG 在浏览器、Ubuntu EOG、GNOME librsvg 和其它静态查看器中的兼容性时使用。
---

# SVG 通用兼容性

浏览器与桌面图像查看器不是同一种 SVG 运行时。最终成品以静态 SVG 共同子集为合同，不以“某个浏览器能打开”作为兼容证明。

## 阅读路径

1. 判断不同打开方式为何结果不同时读取[渲染器模型](references/renderer-models.md)。
2. 设计可移植输出时读取[兼容合同](references/compatibility-contract.md)。
3. 修改、打包或发布后读取[验证流程](references/validation-workflow.md)。
4. 核实资料依据时读取[来源](references/sources.md)。
