# 分项 Shell 示例、可控横向间距与换行无关引用

## 状态

- status: active
- owner: agent
- updated: 2026-10-19

## 期望结果

- `example/run-example/` 是按单一功能拆分的脚本目录；基础绘图、SVG 标题、频率标题、横向间距、注释与其它公开表现参数各有独立示例，Windows 与 Linux 发行消费路径都可执行。
- `horizontal_spacing` 同时约束普通列与零入度 source/from 到直接下游的水平间距；配置增大时两侧相关列都响应，配置小于旧路由净空时无无条件最小值钳制，仅真实路由所需空间可以增大结果。
- 节点键中的 CR/LF 只影响生成图里的多行显示。`source` 引用以移除 CR/LF 后的名称匹配，引用写换行或不写换行都指向同一节点；规范化后重名必须明确报错而非静默连错。
- 右侧数据区采用通用表格术语：节点使用 `table_values`，全局/Python/CLI 使用 `table_headers`、`table_align`、`--table-headers`、`--table-align`；新 SVG 语义、示例和文档不再把任意表格限定成 frequency。旧 frequency 参数作为冲突可检测的兼容别名保留，已有配置不失效。
- 既有公开示例 exact-set、布局质量指标、全量测试、双平台归档检查、解压脚本消费、性能预算和发布流程全部保持通过。

## 当前证据

- failure: `example/run-example.sh` 和 `run-example.bat` 把标题、交叉样式、注释、横向间距、名称与频率表参数混在一个脚本中，不能按单一方面学习和验证。
- failure: 公开配置 `32-annotation-text-stress.json` 在 `horizontal_spacing=240` 时，`ref_multiline` 被根锚点重定位从 x=93.8 移到 x=315.8，其到 `div_long_cjk` 的节点体间距仅 88.5px；该后处理绕过了 240px 合同。
- failure: 简单 `source→div→clock` 在 `horizontal_spacing=0/1/10` 时两个节点体间距都固定为 36px；无纵向通道路由仍被 `2 * route_clearance` 无条件钳制。
- failure: 当前 `validate_config` 与 `build_logical_edges` 按字符串精确查找节点名；键为 `reference\nclock` 时，`source: referenceclock` 会被判未知器件。
- failure: 已支持任意列值与任意标题的右侧表格仍以 `frequencies`、`frequency_headers`、`frequency_align` 及 SVG `frequency-*` 命名，接口含义窄于真实能力。
- pass: 当前实现与 717 项分组全量测试通过；28 个公开示例各执行 29 项质量指标，19 项历史问题 release gate 和七轮递归攻击均通过。
- pass: 当前 Windows 冻结版在 7,302 bytes、63 节点、110 边的真实复杂反例上双跑 32.003s / 31.800s，确定性一致且低于 60 秒；公开 136 节点、196 边长标签交织反例为 41.388s。
- pass: Windows 归档 exact-set 与新鲜解压消费通过，7 个 `.bat` 均实际运行；POSIX 7 个 `.sh` 语法与执行位已由本地结构门验证，待 Linux CI 原生执行。

## 已尝试

- 2026-10-19: 对 0、1、10、40、100、180、240px 做公开入口几何探针 -> 同时复现小间距 36px 钳制与大间距下根锚点回缩。
- 2026-10-19: 定位到 layered compaction 的无条件双净空，以及 `_relocate_root_rendering_anchors` 只按 route clearance 计算最右根位置；二者都是共享 owner。

## 下一步

- 提交并推送 main，值守 Linux/Windows Release jobs 与 publish；从公开 Release 下载资产后完成 tag/SHA、exact-set、摘要和解压运行复验。

## 收敛条件

- 自然反例修复前失败、修复后通过；0/1/10px 简单直连间距可继续缩小，公开 32 号复杂反例的 source/from 直接边不小于显式配置值。
- 换行引用正例、输出端口正例、规范化重名反例与仅空白差异反例全部由测试覆盖。
- 通用表格 Python/CLI/JSON/SVG 正例、旧参数兼容正例和新旧混填冲突反例全部通过；公开示例只使用新名称。
- 所有分项脚本在对应平台新鲜归档中逐个执行并产出非空 SVG；旧扁平脚本缺失且归档检查器能击杀漏脚本变异。
- 项目正式质量与发布门新鲜通过，且本目标文件通过完成态校验。
