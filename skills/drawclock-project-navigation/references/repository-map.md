# 目录地图

```text
src/                       # 严格 JSON、器件库加载、布局、SVG 与 CLI
drawio-lib/                # 项目自带 mxlibrary 和器件预览
scripts/
  drawio_lib/              # 器件几何、模板、注册、构建与库验证
  *.py                     # 示例、器件库和开发辅助脚本
example/                   # 最小示例、布局反例、代表性复杂输入与生成结果
tests/                     # 单元、属性、几何、布局质量、规模和打包测试
tools/                     # 静态构建、运行时、组包和解压消费门
skills/                    # 随发行包提供的项目知识和维护导航
.github/workflows/         # 远端构建、解压验证和 rolling Release
README.md                  # 最短入口和 CLI 参数表
draw.md                    # 绘图参数、JSON 规则和示例
source-deploy.md           # 发行包源码离线运行
pyproject.toml             # 项目元数据、版本和运行时依赖
```

`build/`、`dist/`、临时解压目录和生成缓存是产物，不是设计事实来源。
