---
name: drawclock-project-navigation
description: 进入 drawclock 项目、判断文件职责、选择相关 skill、规划修改、验证和发行时使用，是项目目录与知识归属的总导航。
---

# drawclock 项目导航

按改动所属层读取对应 skill。器件几何、JSON 规则、布局算法和视觉要求分别维护。

## Skill 路由

- 设计器件、端口、标签或 mxlibrary：读取 [component-library-design](../component-library-design/SKILL.md)。
- 修改 rank、排序、坐标、路由、总线或性能：读取 [clock-layout-algorithms](../clock-layout-algorithms/SKILL.md)。
- 设计输入字段、source 引用或生成器：读取 [clock-json-schema](../clock-json-schema/SKILL.md)。
- 判断最终 SVG 是否美观、规整、可读：读取 [clock-diagram-design](../clock-diagram-design/SKILL.md)。

## 项目路由

1. 阅读[目录地图](references/repository-map.md)。
2. 用[职责与归属](references/ownership.md)选择唯一事实来源。
3. 按[修改工艺](references/change-workflow.md)实现和验证。
4. 发布前执行[打包与发行门禁](references/package-and-release.md)。

项目 skill 是发行包中的维护知识，不是运行时依赖，也不改变公开 CLI。
