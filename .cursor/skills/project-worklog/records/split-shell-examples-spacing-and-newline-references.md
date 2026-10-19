# 分项 Shell 示例、横向间距与换行无关引用

## 状态

- status: done
- created: 2026-10-19 15:30 +08:00
- updated: 2026-10-19 19:48 +08:00
- scene: 分项脚本、横向间距与换行无关引用

## 当前工作

- 发行脚本从单个混合演示迁移为 `example/run-example/` 下的单功能脚本集合，并让归档 exact-set 从源码目录动态推导。
- 修复 layered compaction 对无纵向通道仍强加 36px 的问题。
- 修复根显示锚点后处理只保留 route clearance、丢失显式 `horizontal_spacing` 的问题。
- 为节点名建立仅移除 CR/LF 的引用索引；显示身份保留原键，引用解析到唯一原键。
- 把右侧任意数据表的规范接口改为 `table_values` / `table_headers` / `table_align`，旧 frequency 名称降为兼容输入并拒绝新旧混填。
- 16:05 已实现第一批共享 owner：换行无关引用索引、唯一性检查、通用 table 选项与节点数组兼容入口；下一步迁移渲染与 CLI 并用失败测试校准。
- 16:10 通用 table 主路径已接入 CLI、布局属性序列化和 SVG 渲染，旧 frequency CLI/JSON 仅经兼容入口转换；SVG 新语义为 `data-table`、`table-heading/value` 与 `data-table-field`。
- 16:20 首次定向测试编译通过，但旧测试导入 `_frequency_table` 导致收集失败；现已迁移该 Oracle，并补充小间距、根锚点、换行引用、歧义拒绝和 frequency 兼容测试。布局 compaction 只在实际存在纵向 lane 时保留路由净空，根锚点候选同时受显式间距约束。
- 16:24 第二次定向测试为 46 通过、3 失败；失败值分别为 15.33/16.33/25.33，证明旧 36px 路由钳制已移除，剩余增量来自测试长名称的可视文字防撞。回归改用无文字溢出的短名，单独保留复杂注释反例验证防撞与显式间距共存。
- 16:32 定向测试 49/49 通过，全套 716 项可收集。冻结消费器与 SVG 质量 Oracle 已改读通用 `table_values`、`data-table`、`table-heading/value` 和 `data-table-field`，同时保留三项旧频率字段的兼容检查。
- 16:38 其余浏览器、损坏注入与空表测试已迁移到通用 SVG table 语义；旧 `func_freq`、`scan_freq`、`bist_freq` 仍作为兼容输入接受，但统一输出 table 类名与数据属性。
- 16:50 原扁平混合脚本已替换为 `run-example/` 下七组 Windows/POSIX 单功能脚本；22、34 号公开示例改用 `table_values`，34 号同时加入带换行节点由无换行 `source` 引用的公开正例。
- 17:05 发行组装器和归档 Oracle 改为从 `run-example/` 动态推导平台脚本 exact-set；缺一个脚本、多带另一平台脚本或 Linux 脚本无执行位都会失败，发行测试夹具覆盖缺失脚本反例。
- 17:12 本地构建、发布前解压和发布后下载三层 CI 消费门均改为逐个执行目录内全部平台脚本，并验证基础产物与标题专项目标，避免只打包未执行。
- 17:28 README、绘图专题、示例索引、设计笔记和 changelog 已统一到通用数据表、换行无关引用、真实横向间距与分项脚本合同；旧 frequency 名称只在兼容说明中出现。
- 17:40 发行包内的 JSON schema、成图设计和布局覆盖矩阵同步改为 `table_values`、通用 table SVG 语义和新示例名；渐进式资料不再把任意列限制为频率。
- 18:02 全量回归捕获默认间距下自定义高器件与下级端口重合：无纵向 lane 时只允许显式 `horizontal_spacing` 移除旧 36px 路由净空，未传该选项时保留安全默认值。原失败用例现作为回归门。
- 18:35 首轮 28 图完整指标门拒绝 34 号换行引用，原因是独立 Oracle 仍按原字符串绑定逻辑边；Oracle 已用独立实现加入 CR/LF 规范化与冲突拒绝，保持不导入生产源码，并增加正反单测。
- 18:43 第二轮公开图质量门 28/28、每图 29 项指标全部通过；同时修正 CLI `--title` 帮助中残留的旧默认值说明，使其与固定 `drawclock` 实现和 README 一致。
- 18:43 分组全量回归完成：普通与浏览器测试 565/565、规模压力测试 60/60、独立反馈 Oracle 92/92，总计 717/717；历史 19 项 release gate 与七轮递归攻击均通过。
- 18:43 当前 Windows frozen executable 通过完整示例工作流，最终 ZIP 的 7 个 `.bat` 在新鲜解压目录逐个执行并产出非空 SVG；归档 exact-set、actionlint 1.7.12、项目 7 个技能与 POSIX 脚本语法均通过。
- 18:43 冻结性能门使用 7,302 bytes、63 节点、110 边的交叉密集反例双跑 32.003s / 31.800s，输出确定且两轮各执行 29 项质量指标。公开大例额外实测：176 节点/190 边 2.600s，148/168 3.883s，136/196 长标签交织 41.388s，136/166 2.177s，121/122 4.500s；均低于 60s。
- 18:43 冻结消费门首次发现自身仍按精确字符串推断终端，错误把 `reference\nclock` 识别为终端；生产 SVG 的两个真实 clock 本已同列。检查器改为独立移除 CR/LF 后解析引用，并把单测改成键带换行、引用不带换行，随后定向 5/5 与 frozen workflow 均通过。
- 18:46 功能、测试、示例、文档、门禁与新鲜证据已提交为 `d656913`。首次 push 被受管门以“提交后的工作记录与 INDEX 尚未同步”拒绝；本条补齐该阶段事实，之后重新签发当前树回执并正常推送。
- 19:48 `38a2d8f` 已推送，Release run `39239959711` 全绿：反馈门 47m06s、Linux 2m29s、Windows 5m01s、publish 56s、公开 Windows 回下载 4m37s。Linux/Windows 解压脚本、librsvg、完整 frozen workflow 与 60 秒双跑均在原生 runner 通过。
- 19:48 `v1.0.0` 指向 `38a2d8f78203810ff82fcd6cb10ba8953ec51a0f`。远端资产 exact-set 为 Linux 归档、Windows 归档、版本化 Windows 性能收据；本机重新下载后三项 SHA-256 与 GitHub API digest 逐项一致，Windows ZIP 再次通过归档门、完整 frozen workflow 和 7 个 `.bat`。
- 19:48 公开性能收据为 7,302 bytes、63 节点、110 边，双跑 45.464s / 45.272s，SVG 各 71,011 bytes、哈希一致，两轮均完整执行 29 项指标。公开大例本机排序数据仍为 176/190=2.600s、148/168=3.883s、136/196=41.388s、136/166=2.177s、121/122=4.500s，未发现单次超过 60 秒的维护范围输入。
- 19:48 自主验证限制披露：尝试 `gh release verify-asset` 时返回 `no attestations found`，失败环节是 Release 未附 GitHub artifact attestation；不影响已发布字节、运行或质量，但不能给出 attestation 证明。替代方案为读取 GitHub Release API 的三项 `sha256:` digest 与本地下载字节逐项比对，全部一致。若要恢复该能力，后续需在 workflow 中生成并发布 GitHub artifact attestations。

## 已有证据

- 简单 `source→div→clock`：配置 0/1/10px 均输出 36px 间距。
- `32-annotation-text-stress.json`：240px 配置下 `ref_multiline→div_long_cjk` 只有 88.5px，统计显示 `source_anchor_column_moves=2`。
- 当前名称解析只使用 `base in device_names` 与 `nodes[source]` 精确查找。
- 当前任意列的渲染、CLI、JSON 与 SVG 类名仍绑定 frequency 术语。

## 待完成

- 无。
