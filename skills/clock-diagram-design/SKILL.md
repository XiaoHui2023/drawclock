---
name: clock-diagram-design
description: 定义或评审 drawclock 最终 SVG 的视觉要求时使用，覆盖列与支路、竖向总线、远距源副本、交叉、折点、标签、边界和紧凑度。
---

# 时钟图成图设计

本 skill 记录最终 SVG 的视觉要求，不规定具体算法实现。布局算法应把要求转成可计算指标和测试，禁止生成后人工校准。

## 阅读路径

1. [阅读方向、列与支路](references/columns-and-branches.md)
2. [源头、总线与显示副本](references/sources-and-trunks.md)
3. [连线、交叉与折点](references/edges-crossings-and-bends.md)
4. [标签、留白与画布](references/footprints-spacing-and-canvas.md)
5. [设计验收清单](references/review-checklist.md)
6. [末端行与频率注释](references/terminal-frequency-table.md)

## 视觉优先级

正确性、可读性、规整度和美观优先；耗时其次；面积最后。允许必要跨线，默认用圆弧跨线，但不能用跨线样式掩盖本可消除的交叉。
