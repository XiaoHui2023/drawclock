# 注释颜色与 Python 发行边界

## 状态

- status: active
- owner: agent
- updated: 2026-09-11

## 期望结果

- 所有节点可用 `description_color` 修饰 `description`；常见 CSS 颜色写法经严格解析后规范化为稳定 SVG 色值，默认颜色保持不变。
- 注释颜色输入覆盖命名色、短/长十六进制、透明度、RGB 与 HSL 常见写法；非法、动态或渲染器不稳定的值在配置阶段明确失败。
- 独立终态质量系统对每张公开 SVG 执行新增注释颜色指标，不允许用局部测试跳过完整指标集合。
- 源码支持并真实验证尽可能低的 Python 3 版本；README 只声明实际最低版本和真实外部依赖。
- 默认发布归档只保留最终用户运行所需文件、一个最小示例和依法必须保留的许可文本；源码仍由仓库与发布 tag 提供。
- 用户根 Python 与文档 Skill 增加最低版本、跨版本验证、精简归档和去 AI 味专题，并配有可执行门禁。

## 当前证据

- success: 官方资料确认 CSS Color 4 的常见颜色语法、CSSOM 规范化方向、PyPA `requires-python` 合同和 tox/Nox 多解释器矩阵做法。
- failure: 当前 `description` 固定使用全局 `#4b5563`，没有颜色字段或颜色终态质量指标。
- failure: `pyproject.toml` 声明 Python 3.10+；Python 3.9.0 编译通过但运行因 `typing.TypeAlias` 导入失败，另有 `zip(..., strict=True)` 的 3.10 API。
- failure: 当前 README 未声明最低 Python 和零第三方运行时依赖；发行归档含 184 项，包括源码、项目 Skills、全部测试示例、`pyproject.toml` 和来源清单，超出默认用户包需要。

## 已尝试

- 2026-09-11: 审计配置、渲染、质量注册表、README、打包脚本和 Python 3.9 运行结果，冻结缺口后再开始修改。

## 下一步

- 实现颜色解析、渲染与独立质量指标；增加压力示例和恶意输入测试。
- 以 Python 3.9 真实解释器、当前解释器、全公开 SVG、七轮递归攻击、冻结包与全新解包消费闭环验证。
- 验证用户根 Skill，满足发布条件后提交、推送、发布并回下载公开资产。

## 收敛条件

- 字段、解析、SVG 渲染、终态颜色 witness、mutant 和所有公开图完整指标 exact-set 均通过。
- Python 最低版本有静态扫描与真实最低解释器运行证据；README、元数据和测试一致。
- 发布归档 allowlist、文档门、全量测试、打包、远端 workflow、tag 与公开资产消费全部通过。
