# 实际 Windows 制品与布局复现恢复

- status: done
- created: 2026-09-18 11:10 +08:00
- updated: 2026-09-23 11:52 +08:00
- scene: 实际 Windows 制品与布局复现恢复

## 失败基线和冻结范围

- 用户再次确认已发布程序仍显示公共根总线过早横穿、随后纵向穿越多行的路线；此前“已完成”结论撤销。
- 审计发现 `a854b00` 是 2026-09-17 的源码提交，但本机 `dist/drawclock.exe` 和 `dist/drawclock-1.0.0-windows.zip` 均为 2026-09-16 旧文件；GitHub release 工作流只构建、回下载并验证 Linux tarball。源码、Linux CI 和用户 Windows 运行物之间没有可验证血缘。
- 用公开 CLI 尝试让旧 `dist/drawclock.exe` 渲染 `premature-interior-trunk-entry.json` 两次。两个进程均在 30 秒后未退出、没有 SVG；它们由本轮命令启动，随后已停止。此异常只证明 Windows 目标制品的运行门缺失，不能证明布局症状已经自然复现。
- Windows 发布和“用户正在运行的包已经修复”的声明，仍必须取得实际入口、当前制品 SHA-256 和双跑 SVG；但这不是算法布局复现的前置条件。布局缺陷必须由 Agent 用公开 JSON schema 自主构造精确拓扑、经正式公开 CLI 双跑并由独立 SVG Oracle 命中后才允许修改 `src/**` owner。允许修改问题账本、复现 runner、独立 Oracle、测试语料、发行门和用户根 skill。

## 逃逸分类与采用方案

- `coverage_escape`：历史 corpus 只覆盖项目构造的近似输入，未绑定这次用户实际运行。
- `oracle_escape`：全图质量脚本可测几何，却没有先证明它拒绝用户当前 SVG；合成绿灯被误作最终结论。
- `lineage_escape`：Windows EXE 未被当前 CI 构建，也没有 manifest、版本或哈希与提交绑定。
- `claim_escape`：Linux release job 绿灯被误说为用户的 Windows 发行包已经更新。
- 采用 SLSA/GitHub 的最小可验证实践：每个可运行制品记录源提交、构建入口、平台、输入和制品 SHA-256；验证必须对正在运行的产物执行。它不取代布局质量 Oracle。

## 当前恢复顺序

1. 登记开放反馈和真实入口证据要求，并使 release gate 在该证据缺失时失败闭合。
2. 用公开 CLI 双跑用户输入；由独立 SVG 几何脚本记录每边方向、折点、交叉、总线离开点和可行外侧绕行反事实。
3. 只有自然红灯稳定后，定位最早的布局/设施/routing owner，单一 owner 修改，先让旧 SVG 被 Oracle 拒绝。
4. 修复前先为每个被报告的结构语义构造可审计 JSON，并双跑正式 CLI；修复后在同一 Agent 生成输入、相邻组合矩阵和最终 SVG Oracle 上复验。
5. Windows 发布时，再以实际目标平台的包建立构建、解包、执行、SVG 质量和发布资产回下载的同一提交证据链。

## 已完成的外部学习

- SLSA v1.2 将 provenance 定义为可追溯制品到源码和构建过程的信息；GitHub 文档要求对待运行制品验证 attestation。项目会采用小型本地 manifest/哈希合同并在可用时接入 GitHub artifact attestation，而不会假装本地自写 JSON 是签名证明。
- Find Skills 三次查询分别检索 artifact provenance、bug reproduction 和 diagram quality；只记录候选，不自动安装第三方 skill 或执行第三方脚本。

## 2026-09-18 11:12：可执行血缘门

- 新增独立工具 `tools/verify_release_lineage.py`，不导入布局实现。它要求 sidecar manifest 同时绑定可执行制品名称与 SHA-256、源 revision、构建入口和平台；缺 manifest、篡改制品、revision 不一致均非零退出。
- `tests/test_release_lineage.py` 的正例、缺 manifest 和篡改/revision 双负例共 3/3 通过。Python 3.10 与 Python 3.13 环境均未安装 pytest，不能作为测试成功环境；项目 `.venv` 的 pytest 运行 3/3 通过。工具本身以 Python 3.9 兼容语法编写并已 `py_compile` 通过。
- 对真实旧 `dist/drawclock.exe` 运行该工具稳定返回 `build manifest is missing`（SHA-256 `CF72344002382BB1F68A4F0C7F6B8A18606A1861E1FB16324E325C05506E6FF4`）。这将旧包从“可能已发布”降级为“无血缘、不得验证/发布”的状态；下一步是在获得真实入口后补 Windows 构建、清单、解包 smoke 和 SVG Oracle，而不是为旧 EXE 伪造清单。

## 2026-09-18 11:15：当前源码公开入口分层复核

- 当前源码经 `.venv/Scripts/python.exe -I -S src` 对 `premature-interior-trunk-entry.json` 正常生成 SVG（SHA-256 前缀 `0D8EC3A1B2CEA040`）。专项 `FB-ROUTE-023` Oracle 返回 `symptom not observed`，因此该项目语料不能替代用户实际 Windows 输入，也不授权布局修改。
- 第一次调用全指标工具把 `--output` 误写为 `--receipt`，argparse 以 exit 2 拒绝；该调用不计检测。以正确参数重跑后，29/29 指标完整执行，`crossing_treatment` 失败（`--crossing-style none` 与有交叉图不满足跨线可见性要求）。这证明全指标系统有实际拒绝能力，但该失败是显示风格与交叉存在的组合，尚不能直接等同用户的“总线过早横穿”缺陷。
- 结论保持：源码的一个历史语料专项 clean、全指标一项 fail、旧 Windows 包不能运行且无血缘。三者都不足以自然复现用户当前问题；必须捕获实际 Windows 输入和命令后再进入 `src/**` 修复。

## 进程归属事故

- 初次排查时将一个刚出现的 Python 子进程误认成当前 CLI，停止了 `<external-project>/.venv/Scripts/python.exe tools/run_browser_quality.py` 的子进程；其父进程仍在，未进一步操作该外部项目。这是本轮安全错误，不能淡化为 drawclock 失败。
- 已把“先验证 PID、父 PID、完整命令行、工作目录和本轮启动回执，未知归属不得停止”写入用户根质量 skill。后续本项目只停止由当前命令明确创建并可回溯的子进程。

## 2026-09-18 11:36：旧 Windows 制品公开入口双跑

- 不再以 30 秒作为失败阈值。以本轮记录的 PID 先后运行旧 `dist/drawclock.exe` 两次；每次约 80 秒后正常退出，分别生成 160,692-byte SVG，SHA-256 完全一致：`D4F63ACB32BEA876049B0EEF1303EC7B3AAE0AC4B5EB7776F2DE498421B8E751`。
- 输入是 `tests/reproduction-corpus/premature-interior-trunk-entry.json`，入口为正式 EXE CLI，未调用内部布局函数。`FB-ROUTE-023` 独立 Oracle 返回 `symptom not observed`；全图质量系统执行完整 29/29 exact-set，结果 PASS。因此该历史项目语料是有效干净反例，不能被改写为用户问题复现。
- 旧 EXE 仍没有 build manifest，故其版本血缘未知；双跑仅证明这一个 EXE/输入组合的确定性。下一步必须取得用户正在运行的输入/命令或可定位的输出，才能为用户实际症状签发自然红灯。

## 2026-09-18 11:38：实际输入发现边界

- 只读筛选 PowerShell 历史发现旧命令 `drawclock-reload.exe -i test.drawio.svg -o test-new.drawio.svg`。当前仓库仅残留 2026-07-29 的 `test.drawio.svg`；对应 EXE、输出和 XML 路径均不存在，且该 SVG 不是当前 CLI 的 JSON 输入格式。
- 因此该历史记录不能用来重放或推断当前布局缺陷。已排除的来源不再作为候选；需要实际运行的 JSON 与命令，或用户当前生成 SVG 的可验证路径。

## 2026-09-18 12:10：复现输入责任更正

- 用户明确指出：测试集和复现输入应由 Agent 自主制造。此前把“用户实际 JSON 缺失”错误提升为布局修改的绝对阻塞，混淆了**部署制品血缘**与**算法性质复现**两种证据。
- 更正后的双轨合同：对布局算法，Agent 根据公开 schema 建造精确/相邻/对抗性 JSON，在正式 CLI 上双跑，独立 SVG Oracle 命中才是自然红灯；对已下载 Windows 制品是否已更新，仍需真实用户制品身份和入口证据。两类证据不得互相替代，也不得一类缺失阻断另一类的研究与修复。
- 新一轮先审计旧生成器遗漏的“双公共根、每行独立 gate、异深链、后排错列 mux、提前横离主干”组合；覆盖以语义方向和必需交互为准，不以固定轮次数充数。

## 2026-09-18 12:16：生成语料与 Oracle 漏洞审计

- 旧 `search_boundary_trunk_coverage.py` 固定了一个 `common_from` 加私人分支的模型；虽有障碍根，却不表达两个都应形成总线的公共根，也没有“第二个公共 `source` 带额外输出”的独立轴。
- `feedback_layout_reproduction_oracle.py` 的 `shared_root_bus_fragmentation` 只把 `kind: from` 纳入总线验收，而生产布局把 `source` 与 `from` 都识别为公共根。这个 production/Oracle 语义不对称会让第二条公共 `source` 总线散开而质量门不报错，已修正为同时检查 `from` 与 `source`。
- 下一步新增独立生成式双公共根 coverage runner；它只使用公开 JSON/CLI 和最终 SVG Oracle，每案双跑并执行完整质量注册表。

## 2026-09-18 12:20：自主生成双公共根首轮

- 新增 `tools/search_dual_public_bus_coverage.py`。它把两根公共根的类型组合、4/8 行、第二路 `gate`/`gate-div`、末行/外部右移 mux、第二根额外输出和声明正逆序作为覆盖因素；四个具名高风险结构加确定性 pairwise 精简为 11 案、95 个 required 覆盖单元。
- 已用正式公开 CLI 每案独立生成两张 SVG，11/11 哈希一致；每案均经 29/29 最终 SVG 指标，0 失败；`FB-ROUTE-023` 为 0 命中。该组是当前源码的**干净边界**，而不是把用户报告降级为不存在。它证明此前“第二公共 source 未受 Oracle 检查”的缺口已经被这一结构方向覆盖。
- 将追加一个 Oracle mutant：同一公共 `source` 的两条 mux 路径故意使用两个不同纵向通道。它必须被 `shared_root_bus_fragmentation` 拒绝，避免只用干净 SVG 验证刚修正的类别分支。
- Mutant 的成功条件固定为：一个物理根、同一起点、两个不同 source-side 纵向通道、两个 mux 目标轴；Oracle 必须报告期望一条通道而实测两条。该反例只审计检测器，不伪装成产品复现。

## 2026-09-18 13:13：第二轮自然搜索设计

- 首轮 six-factor pairwise 的 11 个干净 case 不足以检验用户所述“主干先横离、随后在内部纵穿”的几何逃逸：它没有把障碍密度、目标所在行带、右移量、第二总线相对轴、远端目标链深、端口置换和 16 行压力作为可追踪因素。
- 本轮只扩展 `tools/search_dual_public_bus_coverage.py` 与其生成的公开 JSON/最终 SVG 收据，保持 `src/elk_layout.py` 冻结。候选因素为 obstacle pattern（无、交织公共根、反向私有分支、密集下游）、target band（top/middle/lower/external-lower）、mux offset（0/2/4）、root bus position（同左轴/第二根分支轴）、late target depth（direct/gate/gate-div）、extra consumers、branch order、port permutation 与 4/8/16 行阵列。
- 每个保留 case 仍须由同一公开 CLI 双跑、比对 SVG SHA-256、执行 `quality-metrics.json` 的完整 exact-set，并运行独立 `FB-ROUTE-023` Oracle；出现该问题的自然 witness 前不得修改布局生产 owner。

## 2026-09-18 13:15：搜索资源边界

- 11 因素的朴素全排列候选池约为 373,248 个组合；首次运行在创建任何 case 目录前被运行环境中止，未产生 SVG、质量结果或布局结论。
- 将候选构造改为：每个单因子和二元组合的基准扩展、具名高风险场景、固定随机种子的有限补充池；`required_units()` 仍以全部单值和二元笛卡尔积为精确合同。这样候选池只承担集合覆盖搜索，不把未执行全排列误报为测试范围。

## 2026-09-18 13:20：扩展搜索结果

- 以有界候选池运行 `tools/search_dual_public_bus_coverage.py --producer-root . --output .reproduction/receipts/dual-public-bus-expanded --expect clean`。正式回执为 21 个生成 case、495/495 required/covered pairwise units、missing=0、quality_failure_cases=0、reproduced_cases=0；每个 case 都由公开 CLI 双跑并执行完整 29 项 SVG 质量合同。
- 结论是扩展因素空间内的干净边界，而不是用户报告已解决：`FB-ROUTE-023` 没有自然 witness，`src/elk_layout.py` 未被修改。下一轮应在不削减已覆盖 exact-set 的前提下补充“已有公共纵线的强制候选通道”与“目标周边占用/文本可见盒”结构，继续寻找具体几何逃逸。
- 定向 Oracle 回归 `tests/test_feedback_layout_oracle.py -k 'dual_public_root_generator_uses_public_cli_and_full_svg_oracle or shared_bus_oracle_rejects_fragmented_public_source_mutant'` 为 2 passed；它证明公共 `source` 的分裂 mutant 仍会被拒绝，但不替代自然复现。

## 2026-09-18 13:22：触发几何前提审计

- 对 21 个生成 SVG 从独立解析器逐条统计公共 `from/source` 出边：所有 case 的最大点数为 4、最大纵段数为 1。`FB-ROUTE-023` 的 lateral-departure 分支要求同一路线至少两个不同 x 的纵段；detached-backbone 分支也需要与共享骨干不同的远端纵段。因此上一轮虽覆盖输入因素，却在最终几何上不可能产生被测症状。
- 下一轮加入 `row_topology` 因素：保留既有 simple mux 行，同时构造合法 `pll2` 输出、三输入初级 mux、每行 gate/div 和含第二公共根的 reconvergent mux。该结构旨在迫使公开布局器面对与历史红灯相同的多层交叉走廊，而不手工改 SVG 或产品代码。

## 2026-09-18 13:27：可触发几何已形成

- 以 16 行 `pll-reconvergent-mux3` 生成合法 181 节点探针并走公开 CLI。独立解析确认 `public_root_b → reconvergent_mux_00..15` 各有 6 个 route 点、两条纵段；这满足 `FB-ROUTE-023` 检查的多纵段前提，修复了上一轮“所有根出边至多一条纵段”的生成空间缺口。
- 探针本身的独立 Oracle 为 `detected_issues=[]`（1137 个 proper crossing events、51 个 distinct crossing points），故仍不是红灯。已对扩展后的 22-case exact-set 启动正式 CLI 双跑、全 29 项 SVG 质量和独立 Oracle 搜索；后台 PID 27032 由本轮启动，继续运行中。

## 2026-09-18 13:35：跨行消费因素

- 当前 reconvergent 行虽已形成两段纵线，但每个 `a_pll_i` 与 `b_pll_i` 只被本行 mux 消费，仍缺少跨行竞争。下一集合增加 `pll_weave`：aligned、mirror、rotate；它只改公开 JSON 中合法 PLL 输出引用，让公共根派生的 PLL 输出接入镜像或循环偏移行的 mux，制造目标周边多层横向/纵向竞争。
- 正在运行的 22-case 集合不重启、不改写；它仍是独立的 exact-set 证据。新因素将在该集合终态后以另一个输出目录运行，避免混合两次的收据。

## 2026-09-18 13:58：两段纵线集合终态与非目标失败

- `dual-public-bus-reconvergent` 已结束：22/22 case、561/561 pairwise units、`FB-ROUTE-023` 命中 0，但 `case-005` 失败 `mergeable_root_facility`（Oracle 同时报 `FB-ROOT-015`）。因此该集合的 `--expect clean` 正确非零退出，不能作为 clean 边界或目标复现。
- 失败结构是 4 行复杂图把 `public_root_b` 直接接入每一行 reconvergent mux；这使多个物理根设施存在可合并反事实。它是生成器合同缺陷，不是用户所述“过早横离后纵穿”的直接 witness。下一版仅在 late target 行保留该直接根输入，其他行使用已有的逐行 `b` gate/div 支路；仍保留 PLL/reconvergent 和跨行 weave，以满足目标几何前提且要求所有非目标指标通过。

## 2026-09-18 14:00：生成器收敛与织网搜索

- 已将 complex reconvergent mux 的第二公共根输入收窄为：仅 late target 行直接连接，其他行复用其各自 `b` gate/div 分支。对原 `case-005` 因素的合法 JSON 重新经公开 CLI 双跑；首张 SVG 的完整质量系统与独立 Oracle 均返回空失败集，修复了非目标 `FB-ROOT-015` 诱因。
- 跨行 `pll_weave` 集合的静态 exact-set 为 21 个 case、666/666 required/covered 单值和 pairwise 单元。该集合在独立目录运行；若 `FB-ROUTE-023` 命中，将冻结该 case 的输入、双 SVG 和 witness 后才考虑任何生产 owner。

## 2026-09-18 14:22：跨行织网终态

- `dual-public-bus-pll-weave` 已结束，21/21 case、666/666 单值和 pairwise 单元、目标 `FB-ROUTE-023` 命中 0。三个 case 出现非目标质量失败：case-002 与 case-005 为 `downstream_corridor_tail_bend` / `FB-BEND-013`，case-020 为 `physical_anchor_relocation` / `FB-ROOT-010`。全部来自完整 29 项终态系统，不可忽略或并入目标红灯。
- 现有 weave 同时交叉接入初级 mux 的 `a_pll` 和 reconvergent mux 的 `b_pll`；两层交叉共同制造了下游尾部折返/根设施重定位。下一版仅让初级 mux 使用 mirror/rotate `a_pll`，并把 reconvergent 的 `b_pll` 固定到本行。这保留公共根到错行消费端的交叉压力，同时移除已测出的非目标诱因。

## 2026-09-18 14:25：织网诱因归类

- 收窄到初级 mux 后，4 行 rotate probe 仍稳定失败 `FB-BEND-013`。独立 witness 表明将 `mux_02` 平移 4.8331px 能在交叉对数保持 6 的同时，使 `a_gate_02`、`b_gate_02` 与错行 `a_pll_03` 的两个尾部折返变为零；这证明跨行 PLL 消费本身是非目标下游排列缺陷。
- 该合法图与完整指标回执保留为诊断，不混入 `FB-ROUTE-023` clean/reproduced 集合。主搜索恢复行对齐 PLL，增加 target/row-band 的长 description 注释压力；Oracle 使用 visual bounds，会验证文字邻域是否使主干提前离开而非只看组件框。

## 2026-09-18 14:28：可见边界搜索集合

- 主集合将 `pll_weave` 固定为 aligned（mirror/rotate 保留在独立非目标诊断收据），新增 `annotation_pressure`：none、late-target、row-band。`description` 通过公开 schema 写入目标 mux 或全行 mux；独立 SVG Oracle 将其纳入 visual bounds。
- 静态覆盖为 22 case、704/704 required/covered 单值与 pairwise 单元。接下来每案仍进行两次公开 CLI、SHA-256 比较、全部 29 项质量与独立 `FB-ROUTE-023` Oracle；收据目录与织网诊断分离。

## 2026-09-18 14:46：注释压力终态

- `dual-public-bus-annotation-pressure` 已结束：22/22 case、704/704 coverage units、目标 `FB-ROUTE-023` 命中 0；仅 case-002 出现 `downstream_corridor_tail_bend` / `FB-BEND-013`。该 case 组合为 16 行、aligned complex PLL、late-target description、lower/right-offset、reverse-private 障碍和 interleaved 声明。
- 该非目标失败不计入目标复现。下一步以完全相同的合法图仅去除 `description` 双跑并跑完整质量集，确定失败是否由可见注释边界引入；若对照 clean，则将 complex-annotation 作为独立诊断而不偷删质量结果。

## 2026-09-18 15:03：无注释同图对照

- 对 case-002 完全保留 16 行、aligned complex PLL、lower/right-offset、reverse-private 障碍、interleaved 声明和双公共根；唯一将 `annotation_pressure` 从 `late-target` 改为 `none`。公开 CLI 双跑 SVG 的 SHA-256 同为 `7F89D99DD2B109F4FF5C998A51C74DA18D4BA044B5D39D38720D54339451D4CC`。
- 完整 29 项质量系统仍失败 `downstream_corridor_tail_bend`，独立最终 SVG Oracle 也只报告 `FB-BEND-013`，其反事实将 `mux_15` 平移 4.8332px、保持 15 个 crossing pair，却将总 bends 188 降为 184。由此排除 description 可见边界是该失败的主因，复现图的 complex 行尾布局本身不满足全质量合同。
- 该对照不是 `FB-ROUTE-023`：目标 Oracle 未报告公共根过早横离/内部纵穿。后续搜索将保留这一完整失败回执，改从不引入 complex-row tail-bend 的合法多纵段公共根结构探索；`src/elk_layout.py` 继续冻结。

## 2026-09-18 15:03：单目标阶梯预检

- 新增 `pll-target-ladder` 行拓扑：仅 late target 行构造 public-root 驱动的 `pll2`、primary gate/div 与 reconvergent mux，其余行保持简单 mux2，避免把已证实会产生 `FB-BEND-013` 的 complex 行尾复制到整张图。
- 16 行、lower/right-offset、second-branch-axis、dense-downstream、interleaved 的合法探针经公开 CLI 双跑，SHA-256 均为 `AE30EE78DB4AF5135C369458D8550A24A9C4D7B67EF5E32319D001801B4699CA`；完整 29/29 质量指标均通过，独立 Oracle 无 issue。
- 解析到 `public_root_b → reconvergent_mux_15` 为 6 点、5 段、含两条不同 x 的纵段（最大纵段 1044.0153px）；它满足目标检查所需的多纵段几何，但尚未出现 `FB-ROUTE-023`。该拓扑将纳入下一份单值/pairwise exact-set 搜索。

## 2026-09-18 15:03：已隔离拓扑域

- 阶梯集合首次启动后，case-000/001 已各自双跑、全质量通过；case-002 是已在先前集合完整诊断过的 16 行 `pll-reconvergent-mux3`，双 SVG 已生成但其耗时质量阶段被停止。它不构成新的目标证据，也不应让相互独立的阶梯方向重复等待同一已知尾部折返。
- runner 增加 `--topology-domain non-tail-bend`：该域严格只包含 `simple-mux2` 和新 `pll-target-ladder`，并重算其自身的单值/pairwise exact-set；`all` 仍保留原 complex 诊断域。此分离保留历史非目标失败收据、不把失败藏进 clean 声明，同时让后续合法目标结构能独立完成全质量搜索。

## 2026-09-18 15:06：注释可渲染性边界

- `non-tail-bend` 首次 24-case 运行的 case-000..002 已完成；case-003 的 4 行、row-band description 输入在**第一**公开 CLI 退出 1，明确错误为 `annotation placement has no collision-free candidate: mux_02`，未生成 SVG。该原始 JSON 和 stderr 保留在 `dual-public-bus-target-ladder-clean` 回执目录。
- 因目标合同要求“合法生成式输入”经公开 CLI 双跑，不能把这个无 SVG 的组合伪作清洁或质量失败 case。下一次 non-tail-bend exact-set 将把 `annotation_pressure` 固定为 `none`；早先 annotation 压力结果继续作为独立可渲染/不可渲染边界证据，而非被删除。

## 2026-09-18 15:08：收窄域覆盖器修正

- 首次收窄后的启动在 case 创建前由 `pairwise coverage candidate space exhausted` 终止。原因是 topology 筛选只检查了 `row_topology`，保留的具名 simple scenario 仍含已移出本域的 `row-band` 注释值；候选池不会生成这个值，贪婪覆盖器因此不应继续。
- 该失败无 CLI/SVG/质量回执，不影响此前可验证边界。runner 将改为只保留**每个** factor 值均属于当前 `FACTORS` 域的具名 scenario，再计算 required/covered 单元；这保持 exact-set 的诚实性而不把失配场景静默当作已测。

## 2026-09-18 15:12：可渲染阶梯域终态

- `dual-public-bus-target-ladder-renderable-v2` 已完成 22/22 case、632/632 required/covered units、每案公开 CLI 双跑且 SVG 哈希一致。没有 case 命中 `FB-ROUTE-023`；因此目标自然红灯仍未出现，`src/elk_layout.py` 未改。
- 仅 case-020（4 行 simple mux2、lower/right-offset、reverse-private）失败 `mergeable_root_facility` / `FB-ROOT-015`。独立 Oracle recheck 的反事实把 `public_root_b` 两条设施合并为一条，crossing events 维持 8、display cost 由 1439.5616 降到 1372.2925；这是生成结构的另一非目标根设施问题，不是目标总线提前横离。
- 完整失败回执保留，不声称 clean。下一轮将继续以已验证全质量通过的单目标阶梯作为核心，增加多个不跨行织网的晚期阶梯消费端，尝试创造两条公共根共享主干后的更强目标周边竞争，同时逐案仍要求完整质量和独立 Oracle。

## 2026-09-18 15:12：并列阶梯消费端因素

- 生成器的 exact-set 因素新增 `ladder_consumers=one/paired/triple`。它仅影响 `pll-target-ladder` 的 late target：多个 reconvergent mux 共享同一 primary gate/div、第二公共根 branch 与 PLL 输出，但额外消费者不直接接 public root，避免重引已测出的可合并根设施。
- 因素意图是提高同一晚期目标走廊的合法共享压力，并保留本地（非跨行）排列，避免已知 `pll_weave` 尾部折返；它不是手工 SVG 改写。后续先对高压 probe 双跑、完整质量与独立 Oracle，只有通过才扩展为新的 pairwise domain。

## 2026-09-18 15:15：三消费者预检通过

- 16 行、lower/right-offset、second-branch-axis、dense-downstream、interleaved、`pll-target-ladder` 与 `ladder_consumers=triple` 探针经公开 CLI 双跑，SHA-256 均为 `3043A86BC730F055E695C9EFFA2FCEBCCB80A7C66CFD892D13F1136A72E1C4AB`。
- 完整 SVG 质量系统为 29/29 通过，独立 Oracle `detected_issues=[]`；因此三并列晚期消费者没有复现已知尾部折返或根设施问题，也尚未命中 `FB-ROUTE-023`。该结构可诚实纳入下一次 exact-set，而不修改生产 owner。

## 2026-09-18 15:20：并列消费者 exact-set 终态

- `dual-public-bus-ladder-consumers` 已完成：21/21 case、743/743 required/covered 单值与 pairwise 单元，每案公开 CLI 双跑、SVG 哈希一致、完整质量无失败，独立 Oracle 的 `reproduced_cases=[]`。这是含 one/paired/triple 本地阶梯消费者的干净边界，不是“用户红灯不存在”的结论。
- 审计发现 `target_band=external-lower` 在 `pll-target-ladder` 分支仍生成普通 external mux2，未获得阶梯的两段纵线；该值虽在输入覆盖内，却没有达到目标症状的几何前提。下一步会让外部低位目标使用同样的合法 PLL/primary/reconvergent 阶梯和消费者因素，再以 probe 证明多纵段、双跑和全质量。

## 2026-09-18 15:25：外部低位阶梯反证

- external-lower 现已接入合法 PLL/primary/reconvergent 的三消费者阶梯。16 行高压 probe 的公开 CLI 双跑 SHA-256 均为 `6D7D24BF4CBC0D6356EB59B4619BE56F60B2A5EEE27E6D73B2C4FCFC520F589A`，完整质量 29/29 通过，独立 Oracle 无 issue。
- 但直接关键边 `public_root_b → external_reconvergent_mux` 仍只有 4 个 route 点、1 条纵段，不具备 `FB-ROUTE-023` lateral/de­tached 分支所需的多纵段几何。该输入是 clean 反证，不会被并入下一轮“多纵段目标候选”覆盖声明。
- 因此继续搜索应改为增加**同一公共根在目标内部的串行分叉/再合流**，而非单纯把目标移到外部低位；生产 `src/elk_layout.py` 继续未修改。

## 2026-09-18 15:25：串行再合流因素

- 新增 `ladder_shape=one-stage/serial-remerge` 作为可追踪因素。`serial-remerge` 只会在 `pll-target-ladder` 的晚期 row 构造首个 reconvergent 之后的 gate/div/第二 mux；第二 mux 使用已有 `b` branch 与 PLL 输出，禁止新增 public-root 直连。
- 这比单纯增加横向消费者更贴合“先横离主干、随后在内部纵穿”的历史几何：根的直接出边必须服务于被后续再合流约束的内部结构。先以 16 行高压 probe 证明实际 route 点数、公开 CLI 双跑、全质量和独立 Oracle，再决定是否扩大 exact-set。

## 2026-09-18 15:31：串行再合流非目标诊断

- 16 行 serial-remerge/triple 高压 probe 的公开 CLI 双跑 SHA-256 均为 `0C98C15A681F1D5EE9EF888B4805460D0F64D19DF0D59C964BF79924FFFDD65C`；关键 `public_root_b → reconvergent_mux_15` 为 6 点、两条纵段，达成目标几何前提。
- 独立 Oracle 但报告 `FB-ROUTE-002`，完整 29 项质量系统失败 `split_rejoin`。其根因是同一 `public_root_b:right` 的分叉在串行 mux 后再合流，不是 `FB-ROUTE-023` 的“提前横离/内部纵穿”反事实 witness。
- 该完整失败诊断保留，serial-remerge 不进入 target exact-set。目标继续寻找不引入 split/rejoin 的多纵段公共根走廊；`src/elk_layout.py` 仍冻结。

## 2026-09-18 15:36：纵向栅栏淘汰

- 按 `FB-ROUTE-023` 的图外走廊反事实，试验在通过的三消费者阶梯 JSON 中加入独立 `fence_root`（layout column 4）及 12 个 column 8 gate/clock 消费端，意图在内部制造可减少的交叉。公开 CLI 双跑 SHA-256 均为 `1340516F95AD599FEF3DE4D5ADF88C476D1B4AD29D91B9599EE5F98B6A020D38`。
- 独立 Oracle 显示该栅栏反而把关键 `public_root_b → reconvergent_mux_15` 压缩到 2 点、0 条纵段并报告非目标 `FB-ROOT-015`。它不满足目标几何前提，故不升级为完整质量/coverage case；这是有双跑与 Oracle 支持的淘汰，而非漏测。

## 2026-09-18 15:42：目标列筛选

- 对干净的三消费者内部阶梯进行四个单跑筛选，只改变 late reconvergent 与两个 PLL 的合法 `layout_column=5/7/9/11`；此阶段明确仅用于选择值得按合同双跑的候选，未作为自然复现结论。
- 四个公开 CLI 均成功，Oracle 均无 issue：column 5、7 仍为 6 点/2 纵段/1 crossing，column 11 为 6 点/2 纵段/2 crossings，column 9 退化为 2 点/0 纵段/1 crossing。没有 `FB-ROUTE-023` 候选，故不对无目标的筛选输入浪费双跑/全质量资源。
- 下一轮变量应从“同一内部列”转为根出口相对列与目标前独立 branch 深度，以实际增加可由图外 lane 改善的交叉，而不是把无效列范围误包装成覆盖。

## 2026-09-18 15:48：根出口/branch 列淘汰

- 固定干净三消费者阶梯，对 `public_root_b.layout_column` 与 late `b_gate_15`/`b_div_15` 的合法列做五个单跑筛选：(0,2)、(1,3)、(3,4)、(4,5)、(5,6)。五案均成功渲染且 Oracle 无 issue，但关键直连根边全部退化为 2 点、0 条纵段、1 crossing。
- 这些设置实际破坏了目标几何前提，故不进入双跑/完整质量；筛选回执明确保存它们为低价值构型。下一步保留原阶梯列关系，试验短 description 的目标视觉边界，避免 row-band 注释曾出现的不可放置组合。

## 2026-09-18 15:54：短目标注释淘汰

- 保持三消费者阶梯原列关系，只对 `mux_15` 施加三个可放置 short description：`bus`、`late bus`、`outer backbone`。三案公开 CLI 均成功、Oracle 无 issue，但每案将关键根边降为 2 点、0 纵段、1 crossing。
- 因此文字的可见边界并未增加可由图外 lane 改善的内部交叉，反而消除了目标前提；它们按单跑筛选记录，不进入双跑/质量集合。下一步保留无注释的有效布局，增加不再合流公共根的独立目标前 branch 深度。

## 2026-09-18 16:00：追加式独立 spur 淘汰

- 在有效三消费者阶梯 JSON 的末尾追加第二公共根的独立 gate 或 gate/div→clock spur，分别为 count 1/4。四个公开 CLI 变体均成功、Oracle 无 issue，却无例外地将关键直连根边压缩为 2 点、0 纵段、1 crossing。
- 这表明 declaration position 是该布局空间的强变量：末尾追加改变了原 interleaved 行的层级关系。该组按单跑筛选保存；下一组将把 spur 插入两公共根之后、原行节点之前，以便在不破坏原行顺序的情况下重新验证真实压力。

## 2026-09-18 16:06：根邻接 spur 淘汰

- 将同一四组独立 b-root spur 改为紧随 `public_root_b` 插入、先于原 interleaved 行节点，仍全部渲染成功、Oracle 无 issue，且所有关键边仍为 2 点/0 纵段/1 crossing。
- 因此问题并非仅来自追加位置；新增独立公共根 consumer 本身改变了布局分层。该组也按单跑筛选保存。下一步保持 public-root fanout 集不变，改为加深 late row 已有 `b` branch，考察内部深度是否能造成目标 root route 的交叉改善反事实。

## 2026-09-18 16:12：既有目标 branch 深度淘汰

- 保持 `public_root_b` 的 consumer 集不变，只在 `b_gate_15` 前插入 1、2、3 层 gate chain。三案均可渲染、Oracle 无 issue，但关键直连 root 边仍全部退化为 2 点、0 纵段、1 crossing。
- 因此不仅新 fanout，连目标既有 branch 的额外深度也会破坏当前两段纵线布局。下一步暂停盲目拓扑枚举，直接测量原干净基线的 top/bottom 图外 lane counterfactual，找出其未命中 `FB-ROUTE-023` 的具体交叉或 box 约束，再按该差异设计输入。

## 2026-09-18 16:18：反事实诊断绑定修正

- 初版诊断直接使用 `parse_svg`，未复用 Oracle `analyze()` 中的 `parse_topology`→`bind_routes` 端点绑定步骤，故无法按 source/target 查找目标边；一次内联补救亦有括号语法错误。两次均未输出 SVG 或改变任何布局结论。
- 诊断将严格复用正式解析/绑定顺序，再计算基线 `public_root_b → reconvergent_mux_15` 的 top/bottom outside-lane crossing、overlap 与 box-hit 差异。该失败被记录以避免将无绑定数据误作 Oracle 证据。

## 2026-09-18 16:24：三消费者几何归因更正

- 重新按 Oracle `parse_topology`→`parse_svg`→`bind_routes` 检查发现：`target-ladder-triple-probe` 的 `public_root_b → reconvergent_mux_15` 实际为 2 点、0 纵段；真正的 6 点、两纵段证据属于早先单消费者 `target-ladder-probe`（点序列 x=123.83→177.66→797.76→901.10）。
- 因此所有基于 triple JSON 的 column、root-branch、short-annotation、spur 筛选只能证明该本已不具备目标前提的图未触发症状，不能用作目标几何淘汰或压力结论。它们保留为原始单跑记录，但从有效目标搜索证据中撤回。
- 后续反事实诊断及任何新输入扩展将以单消费者 6 点基线为唯一起点；之后每案重新验证 route 点数/纵段，再谈目标 Oracle。此前已完成的正式 exact-set 回执本身仍按其记录解释，不把这一更正外推为它们的结果。

## 2026-09-18 16:30：基线反事实与内部 spur 诊断

- 真正 6 点单消费者基线的 `FB-ROUTE-023` 反事实为：内部原图 2 crossing points/2 events；top lane 恶化到 17/23 且有 18 overlap，bottom lane 为 3/3、无 overlap。因此自然红灯需至少添加一条只穿当前内部横段、但不穿 bottom lane 的非同网竖向路由，且保持公共根锚点不变。
- 试验从既有 `a_pll_15[1]` 派生 `fence_gate`→clock（column 6），不增加公共根 fanout。公开 CLI 双跑 SHA-256 均为 `07D6C7264BD993A5E5A7BE2E1D45BA8C425F7FEE2938F031EDF99F71A9B677F3`；关键边仍 6 点/2 纵段/2 crossings，却仅报告非目标 `FB-ROOT-010`，没有增加目标交叉。
- 因此此 spur 不进 full-quality target set；下一轮应复用既有下游 `dense_gate` 边制造内部竖线，避免从 PLL 输出新增消费端导致的根锚点重定位。

## 2026-09-18 16:36：目标行 dense 边列筛选

- 不新增节点或 fanout，仅移动已存在的 `dense_gate_15`/`dense_clock_15` 到四组列 (4,7)、(5,8)、(6,9)、(7,10)。四案均可渲染、关键根边保持 6 点/2 纵段，但 crossing 从基线 2 降为 1，Oracle 无 issue。
- 这证明目标行自身的 dense 下游边不是所需内部竖向竞争来源。下一筛选会改变其它行的既有 dense 边，目标是让其穿过 target 内部横段而不增加根 fanout 或改变目标 anchor。

## 2026-09-18 16:42：其它行 dense 边筛选

- 分别移动 row 0、4、8、12 的既有 dense gate/clock（columns 5/9），不新增节点或 fanout。四案均公开 CLI 成功，关键根边保持 6 点、两纵段、2 crossings，Oracle 均无 issue。
- 其它行的下游边虽不破坏目标前提，也不能增加内部 crossing 到超过 bottom-lane 的 3 个交叉阈值。该组按单跑筛选保留；截至目前尚无通过 Oracle 的自然 `FB-ROUTE-023`，生产 owner 继续冻结。

## 2026-09-18 16:48：单消费者网格执行失败披露

- 计划中的 24-case（障碍×声明顺序×root kind）单消费者网格的两个 Python 实例均停在首案生成前：零 CPU、输出目录未写入首个 JSON/SVG/Oracle；它们均由本轮启动且已停止。最小 `.venv` Python 与 `search_dual_public_bus_coverage` import 随后均在 2 秒内成功，故不是解释器或导入不可用。
- 失败环节是网格脚本的未定位首案执行路径；没有产生任何可计入 coverage 或自然复现的回执，对目标交付没有正向证据。替代方案是下一轮使用不导入生成器、基于已经双跑的单消费者 JSON 的小批量驱动；恢复原网格需要在每个阶段写心跳/进度文件后再运行。

## 2026-09-18 16:54：冻结基线根类型与顺序驱动

- 带阶段心跳的无生成器 6-case 驱动完成并写出全部 JSON/SVG/Oracle。原 `from/source` 基线仍为 6 点/2 纵段/2 crossings、无 issue；交换为 `source/from` 使关键边增至 3 crossings，但报告非目标 `FB-ROOT-010` 与 `FB-ROOT-012`，没有 `FB-ROUTE-023`。
- body reverse/sorted 的四个组合均保持 6 点/2 纵段却降到 1 crossing，并同样触发 `FB-ROOT-010/012`。由此，声明顺序和根类型可影响 crossing，却以根设施重定位为代价；这些不满足全质量合同，不是自然目标红灯。
- 该成功执行也验证了心跳小批量替代方案。下一次输入扩展需保持 `from/source` 原根语义与 original order，同时从非根内部边增加 crossing，避免已量化的 root relocation 诱因。

## 2026-09-18 17:00：非根 dense spur 内部压力边界

- 从已有 non-root `dense_gate` 的 row 0/4/8/12 各派生一条 gate→clock spur（columns 7/10），维持原 `from/source`、声明顺序及公共根 fanout。带心跳驱动全部完成；四案 CLI 成功、关键根边均为 6 点/2 纵段/2 crossings，Oracle 均无 issue。
- 这组是安全但无效的内部压力：没有重定位根，也没有增加到超越 bottom-lane 的 3 crossings。它不进入双跑/全质量目标集合；下一步必须改变内边的**端点行/目标拓扑**而非只添加同类终止 spur。

## 2026-09-18 17:06：跨行目标端口筛选

- 将 non-root `dense_gate` row 0/4/8/12 分别作为 late `mux_15` 的第四输入端口，未改变 public-root fanout。带心跳四案均完成，均保留关键根边 6 点/2 纵段；row 0/4/8 为 2 crossings，row 12 提高到 3 crossings，所有 Oracle issue 均为空。
- row-12 是首个安全的三 crossing 近邻，但独立 Oracle 仍没有 `FB-ROUTE-023`，表示 bottom lane 未获得严格更小的全局 crossing。下一步将该 non-root 边接到直接承接 `public_root_b` 的 reconvergent mux，增加与目标边更近的内部竞争。

## 2026-09-18 17:12：reconvergent 端口容量边界

- 将 non-root dense gate 接入 `reconvergent_mux_15`：row-08 单输入得到 1 crossing，row-12 单输入为 2，row-08/12 双输入为安全的 3 crossings；三案均保持 6 点/2 纵段、Oracle 无 issue，但都未命中目标。
- 进一步用 row-04/08/12 构造合法 `mux6`，关键根边退化为 2 点、0 纵段、3 crossings，Oracle 无 issue；它失去 `FB-ROUTE-023` 前提。由此该端口扩展的可保持几何上限是双 non-root 输入/3 crossings，不能再用加端口方式寻找目标红灯。

## 2026-09-18 17:18：另一公共根直接输入反证

- 在单消费者 6 点基线中只把 late `reconvergent_mux_15` 的直接端口从 `public_root_b` 换为 `public_root_a`，不改变节点、端口数量或其余公共 fanout。公开 CLI 双跑 SHA-256 均为 `989147AACD5C40E85D5283C6F138CDD7F43A077B77B09DB2C4F8266ED6AE5D2B`。
- 独立 Oracle 无 issue，但 `public_root_a → reconvergent_mux_15` 仅为 2 点、0 纵段、0 crossings，因此另一根的直接接入在此布局语义中不具 `FB-ROUTE-023` 所需前提。该方向不扩展为质量/coverage 集合。

## 2026-09-18 17:24：中间行带多纵段反证

- 以生成器构造 16 行、middle late target（`reconvergent_mux_08`）的单消费者阶梯，保持 `from/source`、dense downstream、interleaved 和原端口策略。公开 CLI 双跑 SHA-256 均为 `C200CAFEB2C1B56C16EC7C4A66C00A80E19F62063679DA4D27D722835A14E43E`。
- 关键 `public_root_b → reconvergent_mux_08` 有 6 点、2 纵段，却有 0 crossings，独立 Oracle 无 issue。因此 middle band 虽满足路径复杂度前提，却没有形成可由图外 lane 改善的内部竞争；它不扩展为 target quality set。

## 2026-09-18 17:30：顶行带多纵段反证

- 以同一生成器因素仅改为 top late target（`reconvergent_mux_00`）并公开 CLI 双跑，SHA-256 均为 `03E0C047A334720D9C4E6929D105ABBAB5D8FDC83A8D7989B81E043B2AB7F5F9`。
- 关键 b-root 路径为 6 点、2 纵段、1 crossing，但 Oracle 同时报非目标 `FB-ROOT-010`/`FB-ROOT-012`，没有目标 issue。结合 middle 的 0 crossing 和 lower 的安全 2 crossing，只有 lower b-root 行带保留无非目标故障的目标几何候选；生产 owner 继续冻结。

## 2026-09-18 17:36：lower 行数密度边界

- lower 单消费者阶梯的带心跳 4/8/16 行网格均 CLI 成功、6 点/2 纵段且 Oracle 无 issue：4 行为 0 crossings，8 行与 16 行均为 2 crossings，没有 `FB-ROUTE-023`。
- 4 行公开 CLI 双跑 SHA-256 均为 `443777799C33698D1013B743A8D02AED672C23E685874C7266EA6D5CC91927C4`；8 行双跑均为 `A19DC1F2D01154153B56B3737DB5000BB0EB8C1DBACE08B82BDF477C72A6225C`。行密度不足不会形成目标交叉，16 行也未超过 2 个安全交叉；需引入不同于纯行数的合法内部几何压力。

## 2026-09-18 17:48：历史自然红灯对照（非当前复发）

- 只读审计确认历史回执的 baseline revision 为 `33cceec83733ea45403611c823c4b3ffc730292f`，而当前为修复后的 `a854b00`。在隔离 worktree（不改当前 `src/**`）中，以当前 corpus 的同一输入 SHA-256 `77850A8F…` 运行该历史公开 CLI 两次，SVG SHA-256 均为 `698EEB1811B267FB3E9AF0ED99B83BBC064447D8A192CF22AAC7D35B24BB77FF`；当前独立 Oracle 报告 `FB-ROUTE-023`。
- 这成功重建了**历史版本**的自然红灯，但当前 29 指标质量系统还报告 `diagram_title_absence`、`frequency_column_visibility`（历史版本早于这些契约）及 `premature_interior_trunk_entry`。因此它不能作为当前 `a854b00` 的“仅目标失败”复发、不能授权当前 production 修改，也不覆盖用户的当前制品报告。
- 历史对照的价值是验证 Oracle/输入血缘未断；当前自然红灯仍未命中，`src/elk_layout.py` 继续冻结。恢复当前目标需要在 `a854b00` 的合法输入上命中并使非目标 28 项保持通过。

## 2026-09-18 18:00：历史形状双公共 from 探针运行限制

- 当前 `a854b00` 将历史 corpus 中 `reference_clock_source_with_long_instance_name_2` 从 `source` 改为合法 `from`，与既有 root-0 形成两条真实 public from（各 outdegree 9）。公开 CLI 最终生成 SVG，独立 Oracle 为 `detected_issues=[]`，确认该双根形状并未复发目标。
- 但 CLI Python 进程在写出 SVG 后未正常退出、CPU 近零；等待后由本轮停止。因不能取得第二次正常结束的 CLI 运行，这个实验不能计入双跑/完整质量自然复现，也不能将 clean 单 SVG 误报为当前清洁边界。错误日志为空；恢复条件是定位该大图 CLI 后台退出阻塞或采用能确认正常退出的运行环境。

## 2026-09-18 18:12：双公共 from 历史形状当前 clean control 更正

- 对同一 dual-from 输入再次运行并连续观察两段约 50 秒后，CLI 在约 80 秒正常退出；先前把 55 秒存活误记为退出阻塞的结论撤回。两次最终 SVG SHA-256 均为 `43F4D46042ABAC37556DA587BD5A067068367D441DAE8B8586A1A708410AEF8A`。
- 当前独立 Oracle `detected_issues=[]`，完整当前质量系统 29/29 通过。这建立了一个有效的 current `a854b00` 双公共 from（各 outdegree 9）、历史复杂形状 clean control；它不出现 `FB-ROUTE-023`，不能作为目标自然红灯。
- 后续对该形状的扩展可安全要求至少 80 秒的 CLI 完成观察，避免再将大图收尾误分类为阻塞；`src/elk_layout.py` 仍未修改。

## 2026-09-18 18:24：双公共历史 structural-outlier 筛选

- 从历史 `search_structural_trunk_recurrence` 的最高风险组合构造当前输入：last target、gate-div public chain、column 17、gate-and-descendant 约束、extra-far outlier fanout 与 reverse 顺序；随后把第二个直接 reconvergent 公共根合法设为 `from`。当前 CLI 正常在约 80 秒完成并生成 SVG。
- 独立 Oracle `detected_issues=[]`，确认两个 public from 根各 outdegree 9；未出现 `FB-ROUTE-023` 或其他 issue。因无症状，此单跑筛选不升级为双跑/完整质量自然复现，不以历史高风险命名代替实际红灯。

## 2026-09-18 18:30：外层阻塞审计

- 按受管门禁运行持久账本审计：三态自测通过；当前会话没有可恢复的 pending record。历史会话的孤立 pending 状态未被外推为项目或产品阻塞。
- 外层合同由 `validate_outer_goal.py` 验证为 `BLOCKED/20`：唯一未完成项是 `actual-user-entry`，其恢复动作是提供实际输入或命令；外部条件为缺少当前 Windows 可执行入口与有效 JSON 输入。此前已双跑的旧 EXE/corpus 是 clean counterexample，不能替代用户报告图。
- 当前源码的自主生成搜索、历史 worktree 红灯对照与 current 双公共根 clean controls 已保留；它们不构成真实 Windows 入口的精确复现。下一步将用当前会话重签名该合同回执后，以受限状态向用户请求最小可重放证据；`src/elk_layout.py` 未修改。

## 2026-09-18 18:36：恢复后的生成式输入切片

- 目标恢复 active 后重新审计 `search_dual_public_bus_coverage.py`：其构造器已实现 `pll_weave=mirror/rotate`，但正式 factors 只启用 `aligned`，因此跨行 PLL weave 与双公共根、晚期 reconvergent target 的组合尚未在当前生成器入口双跑。
- 将新增仅位于 `.reproduction` 的公开 CLI probe，对 `mirror` 与 `rotate` 逐案生成合法 JSON、双跑 SVG，并由独立 Oracle 记录目标及任何非目标 issue。无论结果如何，不修改 `src/elk_layout.py`。

## 2026-09-18 20:22：跨行 PLL weave runner 中断

- `mirror` 合法输入与首张公开 CLI SVG 已写出（198,876 bytes），但共享两案 runner 没有生成第二张 SVG、`rotate` 输入或最终 JSON receipt；检查时无本轮存活 Python 进程且无标准输出。因此没有确定性双跑或 Oracle 结果可计入复现。
- 后续改为逐案、有独立 stdout/stderr 与明确退出码的运行方式；避免把单张产物或宿主观察超时误记为 clean/blocked。生产 `src/elk_layout.py` 未修改。

## 2026-09-18 23:08：跨行 PLL weave 双跑结果

- `mirror` 双次公开 CLI 正常退出，SVG SHA-256 均为 `4D6923CB491D62A2D0213C01DD82E020082F4FE94C50DD90EFAB44E21F579659`；独立 Oracle 完整输出 `proper_crossing_events=36`、`distinct_crossing_points=33`，但 `detected_issues=[]`，未命中 `FB-ROUTE-023`。
- `rotate` 双次公开 CLI 正常退出，SVG SHA-256 均为 `9B3B848F9A42235F78373928FB0EECB005365EE043A23BEFFE7A3978524625EA`；Oracle 已完整写出 `proper_crossing_events=36`、`distinct_crossing_points=33` 且 `detected_issues=[]`，但解释器写完后未正常收尾，属 runner 收尾异常，不计为自然红灯。该进程由本轮明确启动，检查时已终止/消失。
- 两案均为合法双公共 `from`、16 行、PLL reconvergent、lower target、dense downstream、cross-row weave 组合；当前 `a854b00` 仍无目标自然红灯，`src/elk_layout.py` 未修改。

## 2026-09-18 23:12：历史结构轴双公共根扩展

- 继续沿历史 `search_structural_trunk_recurrence.py` 的合法输入轴扩展：公共链 `gate-cell`、中间目标列 `13`、仅 descendant 约束、extra-near outlier fanout、reverse 声明顺序；将历史第二公共根 `reference_clock_source_with_long_instance_name_2` 保持为 `from`。
- 该切片用于一次新的公开 CLI 双跑与独立 `FB-ROUTE-023` Oracle；只写 `.reproduction/receipts`，不触碰 `src/elk_layout.py`。

## 2026-09-18 23:20：历史结构轴 root-position 近邻

- `gate-cell`/column-13/descendant/extra-near/reverse 组合双跑完成：SVG 两次均 `f372e976a1ee662924959c8f0f68384bf1345b17beafa366c7cf41411f34f119`，Oracle 有 1006 crossing events、334 distinct points，但 `detected_issues=[]`；三个 public-like source roots 中仅 root-0 是原始 from，root-2 变为第二 public from。
- 为覆盖 root-position 变量，下一步保持全部结构因素不变，分别将等价的 root-1 或 root-3 设为第二个 public `from`，各自执行公开 CLI 双跑和 Oracle。

## 2026-09-18 23:24：root-1 近邻结果

- root-1 设为第二个 public `from` 后，两次公开 CLI 正常退出，SVG SHA-256 均为 `b25b30f95ac701f2ccb8256cc354e452041bc574c61a95572a67c54b5dd43110`；独立 Oracle 为 1006 crossing events、334 distinct points，`detected_issues=[]`。
- root-0/root-1 双公共根的历史结构轴仍未命中 `FB-ROUTE-023`；继续执行 root-3 作为最后一个等价位置对照。

## 2026-09-18 23:28：root-3 探针未完成

- root-3 参数已写入新的输入并生成首张 SVG（160,653 bytes），但探针在第二次 SVG/Oracle/receipt 完成前退出；检查时 receipt 仍保持 root-1 的 `b25b30f9…` 内容，不能借用旧收据推断 root-3 结果。
- 该尝试只计为 `reproduction_in_progress` 的运行时失败；后续必须重新以独立输出路径完成 root-3 双跑，或明确记录入口收尾失败。生产 `src/elk_layout.py` 未修改。

## 2026-09-18 23:31：root-3 独立结果

- root-3 的两张 SVG 实际均已生成，独立 Oracle 输出单独保存为 `historical-structural-root3.oracle.json`；两张 SVG 均 160,653 bytes，Oracle 观察 1006 crossing events、334 distinct points，`detected_issues=[]`，三个 root-position（root-1/root-2/root-3）均未命中 `FB-ROUTE-023`。
- Oracle 解释器写完约 998 KB JSON 后仍未正常收尾，已将其分类为 runner 生命周期异常；几何输出可审计但不把该异常升级为产品红灯。`src/elk_layout.py` 仍冻结。

## 2026-09-19 00:02：双公共根额外直接扇出切片

- root-position 近邻全部 clean 后，下一条未覆盖语义是第二公共根在复杂 reconvergent 图上同时拥有额外直接 `clock` 与 `gate→clock` 扇出。该输入仍是公开 JSON 合法拓扑，不修改既有边或 SVG。
- 将对 root-2/from 形状执行两次公开 CLI 和独立 `FB-ROUTE-023` Oracle；若新增扇出只产生非目标问题，按直接结果记录并继续筛选。

## 2026-09-19 00:08：额外扇出探针语义校正

- 首次额外扇出探针复用了上次 root-3 输入，实际产生三个 `from` 根（root-0、root-2、root-3），虽双跑确定且 Oracle clean，但不满足本目标的“双公共根” exact-set，已从目标证据中撤回。
- 探针将改为从原始历史 corpus 重新构造，只把 root-2 设为第二公共 `from`，再加入该根的直接 clock 与 gate→clock 扇出；旧结果仅保留为语义审计失败记录。

## 2026-09-19 00:18：双公共根额外扇出 exact-set 结果

- 修正版从原始历史 corpus 构造，严格保留两个 public `from`（root-0/root-2，各原始 outdegree 9；root-2 增至 11），其余根为 `source`。公开 CLI 两次正常退出，SVG SHA-256 均为 `5bcd48fbb4ae084b515e75256a943d566526a4437bcd7fef2fae0d674f159fc1`。
- 独立 Oracle 观察 1421 crossing events、429 distinct points、不同网无重叠，但 `detected_issues=[]`；高交叉总量仍不等于公共根过早横穿反事实成立。`src/elk_layout.py` 未修改。

## 2026-09-19 00:44：原始历史 corpus 单根切换双公共根探针登记

- 下一轮只从原始历史 `premature-interior-trunk-entry.json` 复制输入，将一个原本为 `source` 的根单独切换为第二个 `from`，不增删节点、边、声明或布局列；目标是隔离“历史几何 + 双公共根分类”这一尚未直接覆盖的组合。
- 计划仍为公开 CLI 双跑、SHA 一致性与独立 SVG Oracle；在 Oracle 命中前继续冻结 `src/elk_layout.py`。

## 2026-09-19 00:50：原始历史 root-2 双公共根结果

- 仅将原始 corpus 的 `reference_clock_source_with_long_instance_name_2` 从 `source` 切换为第二个 `from`，其余节点、边、声明与布局列保持不变；exact-set 公共根为 root-0/root-2。
- 公开 CLI 两次均退出 0，SVG 均 160,496 bytes，SHA-256 均为 `43f4d46042abac37556da587bd5a067068367d441dae8b8586a1a708410aef8a`。
- 独立 Oracle 观察 1,417 crossing events、428 distinct points、不同网重叠 0，但 `detected_issues=[]`，退出码 1 且明确 `symptom not observed: FB-ROUTE-023`；该组合已覆盖为 clean，`src/elk_layout.py` 继续冻结。

## 2026-09-19 00:56：原始历史 root-1 双公共根结果

- 仅将原始 corpus 的 `reference_clock_source_with_long_instance_name_1` 切换为第二个 `from`，exact-set 公共根为 root-0/root-1。
- 公开 CLI 两次均退出 0，SVG 均 160,496 bytes，SHA-256 均为 `face37d66f16f527bae750446b63b77f4d5bf7c6a6f848869ad9b04b6d649b3d`。
- 独立 Oracle 同样观察 1,417 crossing events、428 distinct points、不同网重叠 0，`detected_issues=[]`，退出码 1 并报告 `symptom not observed: FB-ROUTE-023`；该根位置已覆盖为 clean，布局器继续冻结。

## 2026-09-19 01:03：原始历史 root-3 双公共根结果与穷举收敛

- 仅将原始 corpus 的 `reference_clock_source_with_long_instance_name_3` 切换为第二个 `from`，exact-set 公共根为 root-0/root-3；原始历史 root-1、root-2、root-3 三个候选位置均已分别覆盖。
- 公开 CLI 两次均退出 0，SVG 均 160,496 bytes，SHA-256 均为 `8ad00e1158a13eb3cd36419b3c5878be83833381170754345bde965e3e6e8f6d`。
- 独立 Oracle 仍观察 1,417 crossing events、428 distinct points、不同网重叠 0，`detected_issues=[]`，退出码 1 并报告 `symptom not observed: FB-ROUTE-023`。原始历史几何 + 单根公共分类变量已穷举为 clean，`src/elk_layout.py` 未修改。

## 2026-09-19 01:15：公共根边界选择组合探针登记

- 原始历史 root 分类变量已穷举 clean；下一轮转向生成式合法因子的交互边界，固定双 `from` 或不对称双公共根，组合错位 root bus、反向私有障碍、外部 lower target、reconvergent mux 与额外直接扇出。
- 每个候选仍必须通过公开 CLI 双跑、SHA 一致和独立 Oracle；仅在 Oracle 真正报告 `FB-ROUTE-023` 后才允许触碰布局器。

## 2026-09-19 01:32：公共根边界选择组合首轮结果

- `both-public`（双 `from`、16 行 reconvergent mux、late target、reverse-private 障碍、额外直接输出）公开 CLI 双跑 SHA 均为 `8be9566e814c326c9ca9e8b4f6180a7d61294b79aaef0371bb99e54e9e68807c`；Oracle 未命中 `FB-ROUTE-023`，仅保留已有非目标质量诊断。
- `external`（不对称双公共根、external-lower target、错位 root bus、dense-downstream）公开 CLI 双跑 SHA 均为 `3b59329995c2d509ab4c82e6fea38d2d2d9dfed8c037e5370c605d239ff4afa9`；Oracle `detected_issues=[]`。
- 两个合法高风险组合均未形成目标自然红灯，`src/elk_layout.py` 继续未修改。

## 2026-09-19 02:04：PLL 公共根交叉编织切片登记

- 现有生成器已实现 `pll_weave=mirror/rotate`，但正式因子域此前只启用 `aligned`；这使双公共根跨行交叉编织仍未经过公开 CLI 双跑与 Oracle。
- 下一轮只运行双 `from` / 不对称双公共根的 reconvergent、late-target、错位列与障碍组合切片；命中前继续冻结 `src/elk_layout.py`。

## 2026-09-19 02:18：PLL 编织探针输入生成失败与修复

- 首次生成 `mirror/rotate` 输入时，PowerShell 字符串把字面量 `\\n` 写入 JSON 末尾；公开 CLI 可验证地报 `Extra data: line 939 column 2`，因此该次未产生布局或 Oracle 结论。
- 该失败归类为探针生成错误，不是产品红灯；改用 Python `write_text(... + '\\n')` 重新生成同一输入后再执行双跑与 Oracle。

## 2026-09-19 02:24：PLL 编织探针修复脚本二次校正

- 首次修复只替换了部分转义层，文件尾仍残留字面量 `\\n\\n`；JSON 解析再次以 `Extra data` 失败。
- 该次仍属于探针输入清理错误；下一步以最后一个合法 JSON `}` 截断并重新追加真实换行，再做解析校验后运行 CLI。

## 2026-09-19 03:05：PLL mirror/rotate 双公共根切片结果

- 修复探针 JSON 尾部后，`mirror` 双 `from` reconvergent/late-target/错位列/反向障碍输入公开 CLI 双跑 SHA 均为 `a22509bc102fd7c179d5d04061331a99cf1bbc0efb6059f741b0f9f607037ce2`；Oracle 退出 1，`detected_issues=[]`。
- `rotate` 同类输入公开 CLI 双跑 SHA 均为 `b5ecfdd087e40c0302e40d7270e25342ae36da609e9b89d4f1d7c5e7c7c1a366`；Oracle 退出 1，`detected_issues=[]`。
- 跨行 PLL 编织单独未形成 `FB-ROUTE-023`，`src/elk_layout.py` 继续冻结。

## 2026-09-19 03:18：复合目标几何小批搜索登记

- 下一批固定合法双公共根与 reconvergent 结构，组合 top/middle/lower/external-lower 目标带、serial-remerge、paired/triple consumers、端口排列和 root bus 轴；每案仍公开 CLI 双跑并由独立 Oracle 判定。

## 2026-09-19 03:34：复合切片生成器换行错误

- 首次生成 32 个复合案时沿用了 PowerShell 字面量 `\\n` 写法，公开 CLI 8 个代表案均可验证报 `Extra data`，未产生产品布局结论。
- 该失败与上一轮相同，归类为探针生成器缺陷；后续统一使用 Python `json.dump`/真实换行写入并先批量 `json.load` 校验，再运行 CLI。

## 2026-09-19 04:02：复合目标几何代表案结果

- 修正 32 个输入尾部字面量换行并批量 `json.load` 校验后，运行 8 个代表案；所有公开 CLI 双跑均 SHA 一致、退出 0。
- 可完整解析的 Oracle 报告（case-16/20/28）均为 `detected_issues=[]`；其余报告含终端控制码/超大输出，离线 JSON 提取失败，不能据此声称命中。
- 本轮没有可靠的 `FB-ROUTE-023` 命中证据；输出完整性问题已与产品结果区分记录，`src/elk_layout.py` 继续冻结。

## 2026-09-19 04:18：Oracle 文件报告完整性修复

- 终端输出含控制码/超大 JSON，导致部分代表案无法可靠解析；Oracle 原生支持 `--report`，本轮改为将报告直接写入独立 JSON 文件，再读取 `detected_issues` 与 witness 字段。
- 该改进只增强证据采集，不修改产品布局器或 Oracle 判定逻辑。

## 2026-09-19 04:34：完整 pairwise 双公共根套件登记

- 启用 `pll_weave=aligned/mirror/rotate` 后，生成器的正式 `covering_suite()` 规模为 23 案，覆盖根类型、目标带、串行重汇、消费者数量、障碍、列轴与声明顺序的 pairwise 组合。
- 下一步运行完整 23 案，公开 CLI 双跑并将每案 Oracle 通过 `--report` 写入文件；命中真实 `FB-ROUTE-023` 即停止扩展并保存证据。

## 2026-09-19 05:12：完整 23 案 pairwise 结果

- 启用 `aligned/mirror/rotate` 后完整 `covering_suite()` 共 23 案，`missing_coverage_units=0`；每案公开 CLI 双跑均生成确定性 SVG。
- `reproduced_cases=[]`，没有任何案真实命中 `FB-ROUTE-023`。
- `case-002`（双 `from`、16 行 reconvergent、late lower target、reverse-private、额外直接输出）与 `case-018`（双 `from`、serial-remerge、row-band、额外多输出）分别触发非目标 `FB-BEND-013`；套件质量门禁因此返回 failed，但不能把该独立弯折问题当作目标红灯。
- `src/elk_layout.py` 仍未修改；下一轮以 `case-002` 为最小变异基线，针对其已暴露的公共根边界几何继续搜索 `FB-ROUTE-023`。

## 2026-09-19 05:28：case-002 尾部可移动 witness 分析

- case-002 独立 Oracle 完整报告：唯一质量 witness 为 `FB-BEND-013`，目标 `premature_interior_trunk_entry_witnesses=0`；`mux_15` 可整体下移 4.8332px，涉及 5 个节点、3 条 root/PLL 输入边，但 crossing pairs 不变。
- 下一轮围绕该案做最小因子邻域枚举，重点改变 late target 行、mux 偏移、声明顺序与第二公共根额外输出，寻找从“尾部弯折”转化为目标总线横穿/纵穿的合法组合。

## 2026-09-19 05:46：case-002 邻域代表切片命名错误

- 首次执行 12 个代表案时，PowerShell 格式串把 `case-{0:03d}` 误保留为 `case-03d`，全部在文件定位阶段失败，未进入 CLI/Oracle。
- 该失败属于执行脚本错误，不是产品结果；改用 `('{0:D3}' -f $i)` 后重跑同一代表集合。

## 2026-09-19 06:18：case-002 邻域代表切片文件名宽度二次校正

- 邻域生成器实际使用两位文件名（`case-00.json`），重跑命令对小于 100 的案使用三位文件名，导致前 9 个案在输入定位阶段失败；这仍是执行脚本错误，不是产品结果。
- 已完成的 `case-108/120/132` 双跑 SHA 一致；`case-120/132` Oracle 仅报告 `FB-BEND-013`，目标 witness 为 0。下一步按生成器实际两位命名补跑缺失案。

## 2026-09-19 07:12：case-002 邻域代表结果与进程归属核验

- 按实际两位文件名补跑的代表案 `case-00/12/24/36/48/60/72/84/96` 均公开 CLI 双跑 SHA 一致；Oracle 报告要么 `detected_issues=[]`，要么仅 `FB-BEND-013`，所有 `premature_interior_trunk_entry_witnesses=0`。
- 最后几个邻域案的工具会话句柄在轮询时失效；权威进程核验显示残留 Python 进程均属于另一项目 `trpg-hub`，不是 DrawClock 探针，未执行误杀或重复启动。
- 当前仍无可靠 `FB-ROUTE-023` 命中，`src/elk_layout.py` 继续冻结。

## 2026-09-19 07:28：共享公共根端口语义变体登记

- Oracle 目标代码要求同一 root/source port 至少 4 条分支，且远端垂直段跨过至少 2 个目标行；case-002 的第二公共根主要经过 gate/PLL，未满足该语义。
- 下一探针从 case-002 复制输入，仅把各 `reconvergent_mux_*` 的端口 `1` 合法改接 `public_root_b`，保留双 `from`、16 行结构和所有节点类型；目标是形成真实共享公共根总线后再由独立 Oracle 判定。

## 2026-09-19 07:42：共享端口探针 JSON 写入失败

- 首次写入共享端口变体时再次产生字面量 `\\n`，`json.load` 可验证报 `Extra data: line 870 column 2`，尚未进入 CLI/Oracle。
- 该次归类为探针写入错误；下一步使用真实换行写入并先解析校验，再执行公开双跑。

## 2026-09-19 08:18：共享公共根端口变体结果

- 修正 JSON 尾部后，case-002 的所有 `reconvergent_mux_*` 端口 `1` 改接 `public_root_b`；公开 CLI 两次均成功且 SHA 一致。
- 独立 Oracle 报告 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`，总 proper crossing events 仅 16；真实共享 root port 本身未形成目标远端横穿/纵穿。
- `src/elk_layout.py` 继续冻结，下一轮保持双公共根并探索不同端口直接连接与 PLL 交叉的组合。

## 2026-09-19 08:42：对称双公共根直接消费者变体登记

- 共享端口报告显示 `public_root_b` 长垂直段存在，但根锚点集中在单一中部 y，未跨越两条目标行；历史红灯需要更分散的根锚点/消费者行。
- 下一探针从 case-002 复制，令 `public_root_a` 与 `public_root_b` 对同一批 reconvergent mux 使用直接输入端口，保持双 `from` 和合法 mux3 拓扑，观察对称双根是否形成目标远端跨行段。

## 2026-09-19 09:02：对称双根变体被注释放置门禁拒绝

- 对称直接消费者输入在公开 CLI 阶段可验证失败：`annotation placement has no collision-free candidate: mux_15`，未生成 SVG，故没有 Oracle 结论。
- 该输入失败来自 case-002 的 late-target 描述压力与新几何冲突，不是目标红灯；下一步移除仅用于压力测试的 `description` 字段，保留拓扑和双公共根语义后重试。

## 2026-09-19 09:16：对称双根清洁输入生成命令失败

- 移除注释压力的重试命令因 PowerShell 内联多行转义错误而未生成输入，随后文件读取失败；没有进入 CLI/Oracle。
- 该次归类为探针脚本错误；改用独立临时 Python 生成器写入并立即 `json.load` 校验。

## 2026-09-19 09:31：对称双根清洁输入仍被注释放置门禁拒绝

- 独立生成器创建的输入已通过 JSON/五件套校验，但公开 CLI 仍报告 `annotation placement has no collision-free candidate: mux_15`，未生成 SVG/Oracle 证据。
- 下一步移除全输入所有 `description` 字段，保持节点、边、类型和双公共根不变；若仍拒绝，则将该拓扑分类为生产端前置门禁不可运行，而非目标红灯。

## 2026-09-19 09:48：公共根物理列约束变体登记

- 全量去注释后，对称双根输入成功生成确定性 SVG，但 Oracle 命中非目标 `FB-ROOT-016`：`public_root_b` 16 条直连被渲染为 16 个 physical facilities，形成总线碎片化。
- 下一轮仅为 `public_root_a/public_root_b` 添加同列、相邻列和远列 `layout_column` 约束，尝试恢复单一公共根物理 facility，再检查目标 `FB-ROUTE-023`。

## 2026-09-19 10:18：公共根物理列变体结果

- 同列（1/1）、相邻列（1/2）和远列（1/4）三种合法输入均公开 CLI 双跑成功、SVG SHA 一致。
- 三案 Oracle 均报告非目标 `FB-ROOT-016`，目标 `premature_interior_trunk_entry_witnesses=0`；显式 `layout_column` 未消除第二公共根 16 个 physical facilities 的碎片化。
- 下一步回到历史红灯差异：两个公共根都保持单一渲染 facility，通过中间 gate/PLL 向多行消费者展开，而不是直接连接 16 个 reconvergent mux。

## 2026-09-19 10:34：双公共根单一共享 gate 变体登记

- 从 case-002 复制，新增 `public_root_a_shared_gate` 与 `public_root_b_shared_gate`，每个公共根仅直接驱动一个 gate；所有 reconvergent mux 的端口 0/1 改接对应共享 gate。
- 该输入保持双 `from`、16 行 reconvergent mux、PLL 支路和合法拓扑，目标是消除 `FB-ROOT-016` 的多 physical facility 碎片化后检查 `FB-ROUTE-023`。

## 2026-09-19 10:58：双公共根单一共享 gate 结果

- 共享 gate 输入公开 CLI 两次成功，SVG SHA 一致；独立 Oracle 观察 704 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`。
- 单一 physical root facility 已恢复，仍未形成目标反事实；下一轮扩大共享 gate 到不同目标带的直接消费者跨度，保持双公共根与 gate 中间层。

## 2026-09-19 11:16：共享 gate 未覆盖 PLL/普通 gate 的根引用

- `shared-gate-roots` 路由报告显示 `public_root_a` 仍有 33 个 rendered copies、`public_root_b` 1 个 root copy；原因是只改了 reconvergent mux，`a_gate/b_gate` 与 `a_pll/b_pll` 仍直接引用公共根。
- 下一探针将所有下游 `source=public_root_a/b` 引用统一改为对应共享 gate，确保每个公共根只有一个直接消费者，再执行公开双跑和 Oracle。

## 2026-09-19 11:32：统一 root 引用探针误改共享 gate 形成环路

- 首次统一替换时连新建的 `public_root_a_shared_gate/public_root_b_shared_gate` 自身也被重写，公开 CLI 可验证报 `clock-tree 包含环路`，未生成 SVG/Oracle 证据。
- 该次归类为探针拓扑生成错误；修正为跳过共享 gate 节点，仅替换其余下游引用后重跑。

## 2026-09-19 12:18：全量 root 引用收敛结果

- 修正环路生成错误后，将所有 PLL、普通 gate、mux 字典端口的公共根引用统一收敛到共享 gate；公开 CLI 两次成功且 SVG SHA 一致。
- Oracle 报告两个公共根均为单一 rendered copy，观察 813 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`。
- “单一 root facility + 中间 gate”必要条件已验证，仍未形成目标反事实；继续改变消费者行跨距与目标排列，`src/elk_layout.py` 保持冻结。

## 2026-09-19 12:42：历史四根轮转压缩为双公共根变体登记

- 对比历史自然红灯与当前 clean：历史 16 个 reconvergent 行的端口 1 按四个 root 轮转，每个 root 约 9 条直接边；case-002 仅在最后一个 late row 让第二公共根直接接入，语义差异过大。
- 下一探针从原始历史 corpus 复制，仅将 16 个 `select_reconvergent_*` 端口 1 的四-root 轮转映射压缩为两个公共 `from` 根（偶数行 root-a、奇数行 root-b），其余节点、PLL、布局字段保持不变。

## 2026-09-19 13:02：历史轮转案残留 root-2/root-3 引用

- 历史轮转压缩案双跑成功，但 Oracle 命中非目标 `FB-ROOT-010`/`FB-ROOT-016`；报告显示 root-3 仍有 5 个 rendered copies、4 个 physical facilities，说明仅改 reconvergent 端口不足以形成 exact-set 双公共根。
- 下一探针把所有配置中对 root-2 的引用映射到 root-0、root-3 的引用映射到 root-1，并将 root-2/root-3 保持为 `source`，确保只有 root-0/root-1 是公共 `from`。

## 2026-09-19 13:46：历史轮转 exact-set 双公共根结果

- 将原始历史 corpus 中所有 root-2 引用映射到 root-0、root-3 引用映射到 root-1 后，exact-set 公共 `from` 仅为 root-0/root-1，两个根均 1 个 rendered copy。
- 公开 CLI 两次成功且 SVG SHA 一致；独立 Oracle 观察 1,349 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`。
- 残留第三/第四公共根引用已排除，`src/elk_layout.py` 继续冻结。

## 2026-09-19 14:02：历史轮转压缩相位变体登记

- exact-set 双根路由已出现多分支、多垂直段，但 Oracle 反事实仍未改善；历史端口 1 序列为 `root-2,root-3,root-0,root-1` 周期，上一轮简单按偶/奇行压缩可能破坏相位。
- 下一轮枚举 root-2/root-3 到两个公共根的另一种二值映射，保持所有节点、PLL、布局字段和 exact-set 双 `from` 不变，比较是否形成 `FB-ROUTE-023`。

## 2026-09-19 14:36：历史轮转压缩相位结果

- phase-a 与 phase-b 两种二值相位映射均公开 CLI 双跑成功、SVG SHA 一致。
- phase-a Oracle：1,349 crossing events，`detected_issues=[]`，目标 witness 0；phase-b Oracle：1,301 crossing events，`detected_issues=[]`，目标 witness 0。
- 四根轮转压缩的二值相位变量已排除，`src/elk_layout.py` 继续冻结；下一步转向 root 端口顺序与物理 y 锚点交互。

## 2026-09-19 15:02：纠正 exact-set 公共根语义

- 复核发现此前 `historical-rotating-exact-dual` 实际为 root-0=`from`、root-1=`source`，并非双公共 `from`；此前结果不能作为目标的双公共根证据。
- 下一探针仅把 root-1 改为第二个 `from`，保留历史四根轮转压缩映射、节点、PLL 和布局字段不变，重新执行公开 CLI 双跑与独立 Oracle。

## 2026-09-19 15:34：真正双 from 历史轮转复验结果

- 将历史轮转 exact-dual 输入的 root-1 明确改为第二个 `from` 后，Oracle 根摘要确认 `from/from`。
- 公开 CLI 两次成功且 SVG SHA 一致；独立 Oracle 观察 1,349 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`。
- 此前 from/source 语义误判已纠正，当前双公共根证据有效但仍未命中目标；`src/elk_layout.py` 继续冻结。

## 2026-09-19 15:52：公共根内部走廊偏移变体登记

- 真正 from/from 历史轮转仍 clean；下一轮保持所有 root/PLL/端口语义不变，只对少量 reconvergent target rows 添加合法 `layout_column` 偏移，制造内部走廊与公共根远端垂直段交互。
- 每个偏移案仍必须公开 CLI 双跑、SHA 一致和独立 Oracle 文件报告；命中前不修改布局器。

## 2026-09-19 16:22：公共根连续分组消费者变体登记

- late/middle/split 三组 `layout_column` 目标偏移均与基线同构（1349 crossings、目标 witness 0），确认该字段在当前结构中不改变路由。
- 几何统计显示两个 root 的远端垂直段已跨 2–3 个目标行，但全局反事实未改善；下一探针改用连续四行块 root 分配（0–3/8–11 给 root-0，其余给 root-1），保持真正双 `from` 和历史 PLL 结构。

## 2026-09-19 17:12：公共根连续分组结果

- 连续四行块分组（0–3/8–11 给 root-0，其余给 root-1）的真正双 `from` 输入公开 CLI 两次成功、SVG SHA 一致。
- 独立 Oracle 观察 1,363 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`；连续消费者分组未形成目标反事实。
- `src/elk_layout.py` 继续冻结，后续需转向目标端口顺序/边界 lane，而非继续 root 行分组。

## 2026-09-19 17:28：目标 edge-013 几何相位登记

- 历史红灯的 edge-013 在中部横段后向下纵穿（目标 y≈3149→3959），而 true-dual 当前 edge-013 被排到最下方（y≈4794→4173），因此反事实不改善。
- 下一探针把历史轮转 phase-b 也纠正为真正 `from/from`，使 edge-013 落到另一公共根相位，直接验证目标行/垂直方向是否恢复。

## 2026-09-19 18:12：phase-b 真正双 from 结果

- phase-b 轮转输入将 root-1 明确改为第二个 `from` 后，公开 CLI 双跑成功且 SVG SHA 一致。
- Oracle 观察 1,301 crossing events，`detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`；edge-013 相位改变仍未形成目标反事实。
- `src/elk_layout.py` 继续冻结，下一步转向历史目标端口顺序与边界 lane 组合。

## 2026-09-19 18:32：原始 root 顺序双公共根变体登记

- 真正 from/from phase-b 已排除；下一探针保持原始四根端口轮转和全部节点/PLL/布局字段，仅把 root-3 改为第二个 `from`（root-0/root-3 exact-set），验证历史根物理顺序是否是关键变量。

## 2026-09-19 19:02：原始 root-0/root-3 双公共根结果

- root-0/root-3 exact-set 双 `from` 输入公开 CLI 两次成功且 SVG SHA 一致；Oracle 确认根类型 `from/from`。
- Oracle 观察 1,417 crossing events，但 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`；原始根物理顺序未触发目标。
- 下一步补齐 root-0/root-1、root-0/root-2 原始顺序组合，完成根位置变量穷举。

## 2026-09-19 19:18：原始 root-0/root-1、root-0/root-2 变体登记

- 将分别构造 root-0/root-1 与 root-0/root-2 exact-set 双 `from` 输入，保留原始四根轮转、PLL、布局字段和所有节点顺序；每案公开 CLI 双跑并由文件 Oracle 判定。

## 2026-09-19 20:12：原始第二公共根位置穷举完成

- root-0/root-1 exact-set：公开 CLI 双跑 SHA 一致，Oracle 1,417 crossings，`detected_issues=[]`、目标 witness 0。
- root-0/root-2 exact-set：公开 CLI 双跑 SHA 一致，Oracle 1,417 crossings，`detected_issues=[]`、目标 witness 0。
- 加上已完成的 root-0/root-3，原始 corpus 的第二公共根位置变量已穷举；下一步转向 root `source_port` 与目标端口顺序交互，`src/elk_layout.py` 继续冻结。

## 2026-09-19 20:20：reconvergent source port 排列探针登记

- 原始 root-0/root-1、root-0/root-2、root-0/root-3 exact-set 双 `from` 均 clean，下一合法变量限定为 reconvergent mux 的 source port 排列。
- 保持每条边的逻辑来源不变，仅交换 `source["1"]` 与 `source["2"]`，分别覆盖全量与交替行，检验根总线横段与 PLL 纵段的端口锚点交互；每案继续要求公开 CLI 双跑、SHA 一致及独立 SVG Oracle。

## 2026-09-19 20:42：reconvergent source port 排列结果

- 全量、偶数行、奇数行及中部连续行四种交换案均公开 CLI 双跑成功，四案 SVG SHA 一致。
- 独立 SVG Oracle 四案均 `detected_issues=[]`、`premature_interior_trunk_entry_witnesses=0`；仅交换 source port 不足以复现自然红灯。
- source port 变量族已排除，下一步转向目标 mux 输出端口/声明顺序交互；`src/elk_layout.py` 继续冻结。

## 2026-09-19 21:08：配置声明顺序探针结果

- 对 root-0/root-1 双 `from` 输入执行配置整体 reverse、整体 rotate 两种声明顺序变体；两案公开 CLI 双跑成功且 SVG SHA 一致。
- 独立 SVG Oracle 两案均 `detected_issues=[]`、目标 witness 0；声明顺序目前未触发自然红灯。
- 后续继续聚焦目标 mux 的端口几何/输出角色组合，布局器保持冻结。

## 2026-09-19 21:15：目标 mux 输入端口排列探针登记

- 声明顺序 reverse/rotate 均 clean；下一变量保持每条来源边不变，仅轮换 reconvergent mux 的逻辑输入键 `in0/in1/in2`。
- 该变体直接改变目标 mux 的垂直输入锚点，仍属于公开 JSON 合法生成式输入；每个排列继续要求 CLI 双跑、SHA 一致和独立 SVG Oracle。

## 2026-09-19 22:02：目标 mux 输入端口排列部分结果

- 已完成 `012`、`021`、`102` 三种全量输入键排列；三案公开 CLI 双跑 SHA 一致，独立 Oracle 均 clean、目标 witness 0。
- 剩余 `120`、`201`、`210` 仍需补齐，当前尚未将输入端口排列变量族判定为完全排除；布局器继续冻结。

## 2026-09-19 22:24：目标 mux 输入端口排列完成

- `120`、`201`、`210` 三种剩余全量排列均公开 CLI 双跑 SHA 一致。
- 六种全量 `in0/in1/in2` 排列的独立 SVG Oracle 全部 `detected_issues=[]`、目标 witness 0；全量输入键排列族已排除。
- 下一探针改为逐行混合输入键排列，保持合法拓扑但引入局部端口相位差；`src/elk_layout.py` 继续冻结。

## 2026-09-19 22:46：逐行混合输入键排列初步结果

- `alternate-021` 与 `alternate-102` 两种交替行输入键排列均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 两种连续块混合案尚未执行完，当前保留为进行中的局部相位探针，不提前下结论。

## 2026-09-19 23:10：逐行混合输入键排列完成并迁移历史 corpus

- `blocks-012-210`、`blocks-021-120` 两种连续块排列均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0；raw root-0/root-1 corpus 的局部输入相位矩阵已完成。
- 为覆盖更接近历史自然红灯的几何，下一轮把相同局部输入端口相位迁移到 historical rotating true-dual-from corpus，保持双 `from` 语义和原始 PLL 轮转不变。

## 2026-09-19 23:36：历史 corpus 局部相位迁移初步结果

- historical rotating true-dual-from 的 `alternate-021` 变体已公开 CLI 双跑、SHA 一致，独立 Oracle clean、目标 witness 0。
- `alternate-102` 及两种 block 相位案因单案运行耗时尚未形成完整回执，不能提前判定；当前仍保持进行中。

## 2026-09-20 00:18：历史 corpus 局部相位迁移继续结果

- `alternate-102` 已补齐：公开 CLI 双跑 SHA 一致，Oracle clean、目标 witness 0。
- `blocks-012-210` 已补齐：公开 CLI 双跑 SHA 一致，Oracle clean、目标 witness 0。
- `blocks-021-120` 仍待执行；历史 corpus 的局部相位探针尚未完全收敛，布局器继续冻结。

## 2026-09-20 00:46：双根映射相位扩展探针登记

- 历史红灯的 reconvergent 公共根序列为四相 `2,3,0,1`，此前仅验证了压缩后的两种交替相位；最后一个 block 案已 clean。
- 下一轮在 exact-set root-0/root-1 双 `from` 基础上枚举常量、四行块、八行块及反相块的公共根目标序列，保持每条边和 PLL 结构合法不变，继续要求 CLI 双跑与独立 Oracle。

## 2026-09-20 01:14：历史局部相位矩阵与根映射结果

- historical `blocks-021-120` 已补齐：公开 CLI 双跑 SHA 一致，Oracle clean、目标 witness 0；历史局部输入端口相位矩阵全部 clean。
- 新增 root-phase `blocks4` 案已公开 CLI 双跑 SHA 一致，Oracle clean、目标 witness 0；该案采用 root-0/root-1 四行块交替映射。
- 常量、八行块及反相块映射仍待执行；`src/elk_layout.py` 继续冻结。

## 2026-09-20 01:42：root-phase 映射矩阵完成

- 常量 root-0、常量 root-1、blocks8、reverse-blocks4 四案均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0；连同 blocks4，公共根相位映射变量族已排除。
- 下一步转向历史红灯的公共根直接扇出边集合：比较 root→PLL、root→reconvergent mux 及 root→普通 mux 的混合扇出结构，保持 exact-set 双 `from` 并验证更接近原始自然输入。

## 2026-09-20 02:18：混合 PLL 公共根扇出探针结果

- 构造 `mixed-pll-dual`：保留历史四相 reconvergent 行序列，同时将历史 PLL root-2/root-3 引用分别映射到第二公共 root-0/root-1，形成 root→PLL 与 root→reconvergent 的混合扇出，exact-set 仍为双 `from`。
- 公开 CLI 双跑 SHA 一致，独立 Oracle `detected_issues=[]`、目标 witness 0；混合 PLL 扇出仍未复现自然红灯。
- 下一步继续在 root→普通 mux/primary mux 的直接扇出集合上做结构保持的组合探针，`src/elk_layout.py` 继续冻结。

## 2026-09-20 02:52：primary mux 公共根扇出探针登记

- 基于 mixed-pll-dual，新增 primary mux 的公共根来源分配：alternate、blocks4、blocks8 与 primary/reconvergent offset 四案。
- `primary-recon-offset` 已完成公开 CLI 双跑并确认 SHA 一致；独立 Oracle clean、目标 witness 0。
- alternate、blocks4、blocks8 仍待形成完整 Oracle 回执，当前不提前判定；`src/elk_layout.py` 继续冻结。

## 2026-09-20 03:28：primary mux 公共根扇出矩阵完成

- alternate、blocks4、blocks8 三案均补齐公开 CLI 双跑，SHA 一致，独立 Oracle clean、目标 witness 0；连同 primary-recon-offset，primary 来源相位变量已排除。
- 下一探针改为直接公共根边的稀疏/密集混合：部分 primary 行保留公共根直连，其余使用私有 source，保持 exact-set 双 `from`，验证公共根远端纵向段是否跨越目标行。

## 2026-09-20 04:22：稀疏 primary 公共根扇出结果

- even、blocks、edge 三种稀疏 primary 扇出均已补齐公开 CLI 双跑且 SHA 一致；独立 Oracle 全部 clean、目标 witness 0。
- 直接公共根边数量与分布的稀疏/密集变量已排除；下一步转向 root→普通 mux 的直接扇出与 reconvergent 行混合，继续保持 exact-set 双 `from`。

## 2026-09-20 04:46：普通消费者占用公共根走廊探针登记

- 当前 corpus 没有独立普通 mux，普通消费者由 gate/cell 链组成；下一合法探针在 exact-set 双 `from` 基础上新增少量 root→gate→clock 直接扇出。
- 分别把新增消费者插入配置行首、行中、行尾，保持原有节点与 PLL/reconvergent 结构不变，继续执行公开 CLI 双跑和独立 SVG Oracle。

## 2026-09-20 05:18：普通消费者中部插入结果

- middle 变体已完成：新增 root→gate→clock 直接消费者插入配置中部，公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- head/tail 变体批处理未产出完整 SVG/Oracle，不能判定为 clean；下一轮按单案补齐，布局器继续冻结。

## 2026-09-20 06:02：普通消费者占用公共根走廊完成

- head 与 tail 变体均已补齐公开 CLI 双跑，SHA 一致，独立 Oracle clean、目标 witness 0；连同 middle，root→gate→clock 直接消费者插入位置变量已排除。
- 下一步转向增加普通消费者的多级 gate/clock 扇出密度，继续保持 exact-set 双 `from`，验证公共根走廊在更高普通流量下的反事实。

## 2026-09-20 06:18：多级普通消费者密度探针登记

- 保持 mixed-pll-dual 的双 `from`、PLL 与 reconvergent 结构不变，为两个公共根新增多级 gate→clock 链，分别覆盖低、中、高密度和交错根分配。
- 每个密度案继续要求公开 CLI 双跑、SHA 一致与独立 SVG Oracle，命中前不修改 `src/elk_layout.py`。

## 2026-09-20 07:02：多级普通消费者低中密度结果

- low（4 条三层 gate→clock 链）与 medium（12 条）均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- high（24 条）与 interleaved（20 条交错根分配）尚未执行完，当前不提前判定；布局器继续冻结。

## 2026-09-20 08:12：多级普通消费者密度矩阵完成

- high（24 条三层 gate→clock 链）与 interleaved（20 条交错根分配）均补齐公开 CLI 双跑，SHA 一致，独立 Oracle clean、目标 witness 0。
- 连同 low/medium，普通消费者密度与交错分配变量已排除；`src/elk_layout.py` 继续冻结。

## 2026-09-20 08:24：普通 mux 消费者探针登记

- gate→clock 密度矩阵已 clean；下一结构变量是真正的普通 `mux2` 消费者：每个 mux 汇合公共 root 与 PLL，再接 gate/clock。
- 保持 exact-set 双 `from`、原 PLL/reconvergent 结构和公开 CLI 双跑/独立 Oracle 门禁；命中前不修改布局器。

## 2026-09-20 09:02：普通 mux 消费者矩阵结果

- low、medium、high 三种普通 `mux2→gate→clock` 消费者数量均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- root→普通 mux→下游的数量变量已排除；下一步继续改变普通 mux 的 root/PLL 输入相位与 reconvergent 行相位组合，布局器保持冻结。

## 2026-09-20 09:18：普通 mux 输入相位探针登记

- 在普通 `mux2→gate→clock` 消费者基础上，分别交换 root 输入相位、PLL 输入相位及两者的块状分配；保持 exact-set 双 `from` 与 reconvergent 结构不变。
- 每案继续执行公开 CLI 双跑、SHA 一致和独立 SVG Oracle，命中前不修改 `src/elk_layout.py`。

## 2026-09-20 09:52：普通 mux 输入相位矩阵结果

- alternate、reverse、blocks 三种普通 mux root/PLL 输入相位变体均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 普通 mux 输入相位变量已排除；下一步转向普通 mux 输出接入位置与 reconvergent 目标行的交错组合，继续保持双 `from` 与布局器冻结。

## 2026-09-20 10:08：普通 mux 接入位置探针登记

- 保持普通 `mux2→gate→clock` 的来源与输出不变，仅改变这些消费者在配置中的声明位置：全部头部、逐行交错、全部尾部。
- 该变量直接影响布局声明/排序与 reconvergent 目标行的相对位置；每案继续执行公开 CLI 双跑、SHA 一致和独立 SVG Oracle。

## 2026-09-20 10:42：普通 mux 接入位置矩阵结果

- head、interleaved、tail 三种普通 mux 消费者声明位置均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 普通 mux 接入位置变量已排除；下一步转向普通 mux 输出接入不同下游 gate/cell 角色，继续验证公共根横穿与纵向穿越组合。

## 2026-09-20 10:58：普通 mux 下游角色探针登记

- 保持 ordinary mux 的 root/PLL 输入、数量与声明位置不变，分别测试 mux→clock、mux→gate→clock、mux→cell→clock 三类合法下游角色。
- 每案继续执行公开 CLI 双跑、SHA 一致和独立 SVG Oracle，命中前不修改 `src/elk_layout.py`。

## 2026-09-20 11:32：普通 mux 下游角色矩阵结果

- `mux→clock`、`mux→gate→clock`、`mux→cell→clock` 三类下游角色均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 普通 mux 下游角色变量已排除；下一步转向在同一 mux 上增加双输出/多下游扇出，验证输出端口共享是否产生公共根过早横穿。

## 2026-09-20 11:48：普通 mux 多下游扇出探针登记

- 在同一 `mux2` 输出上并行连接 gate→clock 与 cell→clock 两条合法下游，分别覆盖低、中、高 mux 数量。
- 该探针保持双 `from`、PLL/reconvergent 结构不变，要求公开 CLI 双跑、SHA 一致与独立 SVG Oracle。

## 2026-09-20 12:22：普通 mux 多下游扇出结果

- low、medium、high 三种共享 mux 输出扇出（并行 gate→clock 与 cell→clock）均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 普通 mux 多下游共享输出变量已排除；下一步继续增加多级共享下游与 reconvergent 目标行交错，布局器保持冻结。

## 2026-09-20 12:38：多级共享下游交错探针登记

- 在普通 mux 共享输出基础上，同时增加 gate→cell→clock 与 gate→clock 两条链，并按偶/奇、连续块、反相块三种目标行相位分配。
- 该组合覆盖多级共享输出与 reconvergent 行交错的未测结构，继续要求公开 CLI 双跑、SHA 一致和独立 SVG Oracle。

## 2026-09-20 13:18：多级共享下游交错结果

- alternate、blocks、reverse 三种多级共享下游相位案均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 多级共享输出与 reconvergent 行交错变量已排除；下一步继续探索普通 mux 输出接入不同布局列/目标带的组合，布局器保持冻结。

## 2026-09-20 13:32：普通 mux 布局列探针登记

- 保持普通 mux 及其多下游结构不变，仅为 mux/gate/cell/clock 链绑定左侧、中部、远端及交错 `layout_column`。
- 每案继续执行公开 CLI 双跑、SHA 一致和独立 SVG Oracle，命中前不修改布局器。

## 2026-09-20 14:18：普通 mux 布局列矩阵结果

- left、middle、far、staggered 四种 `layout_column` 绑定均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 普通 mux 布局列变量已排除；下一步转向目标带/late-target 绑定与公共根混合，继续保持布局器冻结。

## 2026-09-20 14:34：目标带与 late-target 组合探针登记

- 在多级共享 mux 输入基础上，分别将普通 mux 链绑定到目标中带/远端带，并对部分 reconvergent 行添加合法 description 压力。
- 覆盖 middle、far、late-target 三种组合；每案继续公开 CLI 双跑、SHA 一致和独立 SVG Oracle。

## 2026-09-20 15:18：目标带与 late-target 组合结果

- middle、far、late-target 三案均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 目标带/描述压力与普通 mux 混合变量已排除；下一步转向普通 mux 输出接入多目标 cell 类型与公共根远端设施组合，布局器继续冻结。

## 2026-09-20 15:32：普通 mux 多目标 cell 类型探针登记

- 库内合法 cell_kind 已确认包含 `occ_clk_cell`、`gen_cell`、`bist_clk_cell`；下一轮把普通 mux 输出分别接入三类 cell→clock 下游，保持双 `from` 与公共根结构不变。

## 2026-09-20 16:02：普通 mux 多目标 cell 类型结果

- `occ_clk_cell`、`gen_cell`、`bist_clk_cell` 三种普通 mux→cell→clock 变体均公开 CLI 双跑 SHA 一致，独立 Oracle clean、目标 witness 0。
- 下一步构造双公共根直接远端 cell facility，并绑定远端布局列，验证 distant facility 与公共根纵向穿越的组合。

## 2026-09-22 00:37：双公共根直连远端 facility 结果

- `occ_clk_cell`、`gen_cell`、`bist_clk_cell` 三种双公共根直连远端 facility 变体均完成公开 CLI 双跑，逐案 SHA 一致，独立 SVG Oracle clean、目标 witness 0。
- `src/elk_layout.py` 保持零差异；同类结构继续枚举的收益已不足，下一步转向 Oracle 前置条件与反事实候选的近失配分析，再据此收窄下一组合法生成式输入。
- 生成器首次运行因错误读取 `.reproduction/mixed-pll-dual.json` 触发 `FileNotFoundError`，未产生有效输入或产品结论；已改为读取 `.reproduction/receipts/mixed-pll-dual.json` 并完整重跑恢复，无残留交付影响。

## 2026-09-22 00:44：FB-ROUTE-023 近失配诊断

- 新增 `.reproduction/diagnose_premature_candidates.py`，复用独立 Oracle 的 SVG 解析和反事实函数，但只解释候选被拒原因，不修改判据或产品布局。
- 远端 `bist_clk_cell` 案有 16 条 root 路由满足点数、双纵向通道和通道分离前置条件；其中 `svg-edge-0189` 的 top 候选把全局交叉点 398→397、事件 1474→1473，唯一拒因是候选同网成环。
- 原始 `mixed-pll-dual` 的 `svg-edge-0163` 同样只差 `same_net_cycle`：交叉事件 1349→1330；下一步反查形成该环的最小同网 sibling 集合，再构造定向删减/重排输入。

## 2026-09-22 00:46：最小致环 sibling 定位

- 诊断器新增单边筛选与单/双 sibling cycle-breaker 搜索；`mixed-pll-dual` 的 `svg-edge-0163` top 候选仅需移除同网 `svg-edge-0005` 即可消除反事实环。
- `svg-edge-0005` 映射到 root0→`select_reconvergent_*_000` 的 mux3 端口 1。下一案仅把该端口来源切换为 root1，保持 mux3 三输入、双公共根和其余拓扑不变，用公开 CLI 双跑与未修改的独立 Oracle 验证。

## 2026-09-22 00:47：单端口 cycle-break 定向案登记

- 新增 `.reproduction/make_cycle_break_variant.py`：从 `mixed-pll-dual.json` 读取基线，带旧值断言地只替换 reconvergent mux 000 的端口 1 root0→root1，输出 `cycle-break-mux000-root1.json`。
- 生成器不接触产品布局或 Oracle；下一步生成输入并执行公开 CLI 双跑、SHA 确定性与 FB-ROUTE-023 专项 Oracle。

## 2026-09-22 00:52：单端口 cycle-break 定向案结果

- `cycle-break-mux000-root1` 已完成公开 CLI 双跑，SHA-256 均为 `4521B9B4606E67CB24988A597A2DDB41C38222E7560E0C22EA3FB7248A27FC9B`；专项 Oracle 明确 exit 1、目标 witness 0，不能声明复现。
- 自然重排后原 `svg-edge-0163` top 候选已消除 `same_net_cycle`，路由交叉事件 45→26、全局事件 1373→1354，但全局不同交叉点 395→396，当前唯一拒因变为 `global_points_nonincreasing`。
- 下一步比较该候选新增/消失的交叉坐标与 partner edge，定向消除新增的单个交叉点；布局器仍保持零差异。

## 2026-09-22 00:54：交叉点差分归因

- 诊断器新增反事实前后交叉坐标差分。`svg-edge-0163` top 候选在目标纵向通道 `x=2088.82` 新增 7 个不同交叉点、移除 6 个，解释了全局净增 1。
- 新增 partner 中 `svg-edge-0000`、`0110`、`0115` 均汇入 mux 000；下一定向案在已完成 root0→root1 cycle-break 的基础上，将 mux 000 合法降为 `mux2` 并移除 divide 输入，验证能否消掉一条新增横穿而保留其余近失配几何。

## 2026-09-22 00:55：mux2 cycle-break 案登记

- 扩展 cycle-break 生成器，新增 `cycle-break-mux000-mux2.json`：mux 000 使用合法 `mux2`，输入为 root1 与 `pll_dual_3[0]`，从而移除已归因的 divide→mux000 横穿。
- 下一步执行公开 CLI 双跑和未修改的 FB-ROUTE-023 Oracle；未命中前继续禁止改动 `src/elk_layout.py`。

## 2026-09-22 00:58：mux2 cycle-break 案结果

- `cycle-break-mux000-mux2` 公开 CLI 双跑 SHA-256 均为 `3E565257DD6BD9A48C70F1CE3BD1DF4E9DD861E7C6CBE354584EF99A5B566105`；专项 Oracle exit 1、目标 witness 0。
- 降低 mux 元数导致全图大幅重排，候选前置边由 16 降为 9，因此该方向不再继续删边。新布局中 `svg-edge-0168` top 反事实的全局交叉点 355→355、事件 1158→1156，其唯一拒因是 `box_hit`。
- 下一步定位命中的具体无关 box，并改用位置/声明顺序的轻量定向扰动移开障碍，不再改变 mux 元数。

## 2026-09-22 00:59：唯一 box_hit 障碍定位

- 诊断器新增候选命中 box 明细；`svg-edge-0168` top 候选仅穿过 `reference_clock_source_with_long_instance_name_1` 的两个可见副本，其他数值门全部通过。
- 两副本可见 x 范围均为 1831.09–2200.69，候选目标纵向通道为 x=2078.82。下一步用 root1 的合法 `layout_column` 0/1/2 做单跑 Oracle 筛选，只有自然红灯案再补第二跑 SHA 门。

## 2026-09-22 01:00：root1 布局列定向筛选登记

- cycle-break 生成器新增 root1 `layout_column` 0、1、2 三案，均基于同一 mux2 cycle-break 拓扑，只改变第二公共根列约束。
- 三案先执行一次公开 CLI 与未修改专项 Oracle；如命中 `FB-ROUTE-023`，立即补同输入第二跑和 SHA 一致性，未命中案不冒充完整复现证据。

## 2026-09-22 01:07：root1 布局列筛选结果

- root1 `layout_column` 0、1、2 三案均由公开 CLI 生成 SVG，专项 Oracle 均 exit 1、目标 witness 0；三案全局交叉点均为 406、事件均为 1245，最佳候选也同为 `svg-edge-0147` bottom，拒因为 `box_hit` 与未形成严格交叉改善。
- 三个列值没有形成有效布局区分，因此停止扩大相邻列枚举。下一步回到保留 mux3 的单端口 cycle-break 案，围绕净增的 7/6 交叉坐标做局部端口/声明顺序扰动，避免 mux2 引起全图重排。
- 五件套检查 PASS，`src/elk_layout.py` 保持零差异；自然红灯仍未命中，任务状态继续为 `reproduction_in_progress`。

## 2026-09-22 01:10：前三子系统局部行序筛选登记

- 保留 `cycle-break-mux000-root1` 的 mux3 节点和全部连线，只对前三个连续 8 项子系统块做 `021`、`201`、`120` 三种局部声明顺序置换。
- 当前目标边进入 002 行；`021` 预计让它越过 001 行并减少三条候选纵向横穿，`201` 将目标行置顶，`120` 提供另一侧对照。三案先单跑公开 CLI + 专项 Oracle，命中后补第二跑 SHA 门。

## 2026-09-22 01:17：前三行 021/201/120 筛选结果

- 三案专项 Oracle 均 exit 1、目标 witness 0。`021` 的 002 top 候选只差严格改善：全局交叉点 390→390、事件 1342→1342，其余约束全通过；`120` 的最佳候选同样仅缺严格改善。
- `201` 最佳候选只差全局不同交叉点非增（392→394，事件 1356→1355）。当前六排列仅余 `102`、`210`，下一步补齐后即穷尽前三行局部排列变量。

## 2026-09-22 01:18：前三行剩余排列登记

- 生成器补充 `102` 与 `210`，与原始 `012` 及已跑 `021`、`201`、`120` 共同覆盖前三子系统块的全部六种排列。
- 两案继续采用单跑公开 CLI + 未修改专项 Oracle 筛选；任一真红再补第二跑确定性门。

## 2026-09-22 01:25：前三行全排列结果与跨行支路转向

- `102` 与 `210` 均专项 Oracle exit 1；至此原始 `012` 加五个变体已穷尽前三子系统全部六排列。`102` 仍只差严格改善（374→374 点、1323→1323 事件），`210` 只差不同交叉点非增（392→394）。
- `021` 的 002 top 候选实际路线已经位于上侧边界 y=266，反事实与现状交叉集合完全相同，不代表过早进入内侧，因此停止行序变量。
- 回到原 mux3 单端口案：目标内侧横段为 y=1629、x=416→2088。下一步把后续 mux 005/006/007 的 divide 输入分别单点改接 divide 000，诱导中间列跨行纵段穿过该内侧横段，同时让其目标端水平段落在外侧候选终点 y=994 下方。

## 2026-09-22 01:26：divide 跨行支路筛选登记

- 生成器新增 005、006、007 三案；每案只把对应 reconvergent mux 的端口 0 从同号 divide 改为 divide 000，带旧值断言，节点数、边数、mux3 元数及双公共根保持不变。
- 三案先单跑公开 CLI + 专项 Oracle，目标是让新增跨行纵段只穿过 y=1629 的现有内侧横段，从而把反事实的全局交叉事件严格降低。

## 2026-09-22 01:34：单锚改源结果与双锚 mux 转向

- 005、006、007 三案均专项 Oracle exit 1。目标 002 候选分别至少还差不同交叉点非增/局部交叉点非增，未形成预期的单一严格改善。
- SVG 实测 005 新边 `divide000→mux005` 仅有 91px 纵段：ELK 将目标 mux 拉到 divide000 所在行，未纵穿 y=1629，单锚改源假设被证伪。
- 下一步不再改原有 mux 输入，而在单端口 cycle-break 基线上新增合法双锚 `mux2→clock`：分别接 divide000 与 divide005/009/015，利用两个既有远距锚点迫使真实跨行通道，并继续由专项 Oracle 判断是否只穿现有内侧路径。

## 2026-09-22 01:35：双锚 mux2 支路筛选登记

- 生成器新增 anchor 005、009、015 三案；每案只在末尾追加一个合法 `mux2`（输入为 divide000 与对应远端 divide）及一个下游 clock，不修改任何既有节点或边。
- 三案先单跑公开 CLI + 专项 Oracle；同时核对新增两条 mux 输入边的实际纵向跨度，防止把“远端来源”误当成“已产生纵穿”。

## 2026-09-22 01:50：双锚案收敛与正式生成器覆盖审计

- anchor 005、009、015 三案的专项 Oracle 均 exit 1、目标 witness 0；新增支路实测最大纵向跨度分别只达到约 305px/119px，ELK 仍把远距来源吸收到局部几何中，没有形成所需的真实纵穿。该一次性局部假设停止扩展。
- 对照任务交接、质量闭环 skill 与正式回执后确认：`tools/search_dual_public_bus_coverage.py` 当前 23 个 case、1035 个覆盖单元与 `.reproduction/receipts/pairwise-full/coverage-receipt.json` 完全相同，直接重跑不会增加任何组合覆盖。
- 正式模型缺少“两个公共根在多个重汇聚 mux 行上直接、重复入端”的独立因子；这是用户结构与 `mixed-pll-dual` 近失配之间尚未系统覆盖的空白，下一步在正式生成器中加入该因子和高风险场景，而不是继续追加一次性手工图。
- 同时发现正式 runner 的 `--expect reproduced` 会把目标指标 `premature_interior_trunk_entry` 自身当作普通质量失败，从而拒绝合法的目标红灯。下一步补充“有 witness 且失败指标恰好只有目标指标”的精确分类与测试；`src/elk_layout.py` 继续冻结。

## 2026-09-22 01:57：正式双根重复直入因子与精确红灯合同落地

- `tools/search_dual_public_bus_coverage.py` 新增 `public_root_entry=branch-only/repeated-direct`，并加入 `dual-public-repeated-direct-reconvergent` 高风险场景；重复直入模式让两个公共根在多个合法 `mux4` 重汇聚节点直接入端，同时保留原有分支与 PLL 路径。
- runner 新增可审计的目标 witness、语义前置条件与 `target_reproduced` 字段；只有“witness 非空、双根重复直入前置条件成立、失败指标恰好为 `premature_interior_trunk_entry`”才算自然复现。
- 新增命名场景入口，仍执行同一公开 CLI 双跑、SHA 一致性与完整质量指标合同，但回执明确标注 `named-scenario`，不冒充全域 pairwise 覆盖。
- 回归测试已补充重复直入结构、完整 pairwise 闭包和目标红灯精确分类；下一步先执行静态/单测门，再运行新命名场景。产品布局器未修改。

## 2026-09-22 01:58：首次结构单测捕获旧端口覆写

- 定向单测 1 passed / 1 failed：重复直入场景的 peer mux 保留双根直入，但主 `reconvergent_mux_00` 在后置 PLL weave 阶段仍按旧 mux3 合同覆写 `source[2]`，导致第二公共根被替换。
- 五件套检查仍 PASS，语法编译及 `git diff --check` 无新增错误，`src/elk_layout.py` 零差异。下一步让 PLL weave 对 repeated-direct 的 mux4 保留 `source[1:2]` 双根与 `source[3]` PLL，再重跑相同门禁。

## 2026-09-22 01:59：mux4 PLL 端口合同修正

- repeated-direct 模式的后置 PLL weave 现改写 `source[3]`，branch-only 旧 mux3 仍改写 `source[2]`；因此主重汇聚 mux 的 `source[1:2]` 双公共根不再被后处理破坏。
- 修正只作用于正式输入生成器，未修改产品布局器；下一步重跑结构、覆盖闭包、公开 CLI 质量控制测试。

## 2026-09-22 02:00：正式生成器定向门通过

- `py_compile` 通过；`test_dual_public_root_generator*` 共 2 passed，覆盖了既有公开 CLI + 29 指标控制案、双根重复直入结构、完整 pairwise 闭包与目标红灯精确合同。
- 五件套 PASS，`git diff --check` 仅报告既有 LF/CRLF 提示，`src/elk_layout.py` 仍零差异。
- 下一步用正式 runner 的 `dual-public-repeated-direct-reconvergent` 命名场景执行公开 CLI 双跑、SHA 确定性、完整 29 指标和独立 Oracle；回执明确为 named-scenario，不声明全域覆盖。

## 2026-09-22 02:06：16 行重复直入场景达到有界超时

- 首次正式命名场景从 02:01 运行至 02:06，约 5 分钟后仍只有 24,031-byte `input.json`，第一遍公开 CLI 未生成 `first.svg`；父 runner CPU 近零，子 CLI 仍存活。已向 runner 发送 Ctrl-C，并核对命令行后停止本轮启动的残留 PID 23780。
- 失败环节是 16 行、paired consumer、dense downstream 组合的首遍 ELK 渲染，尚未进入双跑 SHA、29 指标或 Oracle，因此对是否存在 `FB-ROUTE-023` 没有结论，也不得声明复现。
- 替代方案是在同一正式 `public_root_entry=repeated-direct` 因子内缩减为 8 行、单消费者、无额外障碍，保留两个公共根在多个重汇聚 mux 直接入端与右移目标；渲染闭合后再逐项恢复压力变量。恢复原规模需要明确的渲染性能预算或进一步拆分压力因子。

## 2026-09-22 02:07：8 行渐进重复直入场景登记

- 正式高风险场景收缩为 8 行、单消费者、无额外障碍；仍保留 `pll-reconvergent-mux3`、mirror PLL weave、目标 mux 右移 4 列、gate-div 深度、交错声明及多个第二根输出。
- 每行的重汇聚节点仍为合法 mux4，直接包含两个公共根、主分支与 PLL 输入，语义前置条件不降级。下一步重跑定向测试和正式 named-scenario 双跑门。

## 2026-09-22 02:09：8 行重复直入正式反例闭合

- 定向结构/红灯合同测试 2 passed；正式 named-scenario 完成公开 CLI 双跑，两份 SVG SHA-256 均为 `305A50432DB006330C90F339BBE41EDE53CBC86D3568532E1044E54EAEEB244D`。
- 回执 schema v2、named-scenario 覆盖缺口 0；29 指标失败 0、独立 Oracle issue 0、目标 witness 0，且 `semantic_preconditions_met=true`。因此本案是有效干净反例，`--expect reproduced` 按合同 exit 1，不能声明复现。
- 下一步对该 SVG 运行候选拒因诊断，再依据最近缺口一次只恢复 paired consumer、dense downstream 或 16 行规模中的一个压力变量；布局器继续冻结。

## 2026-09-22 02:11：干净反例候选拒因归纳

- 独立候选诊断识别 8 条 eligible route / 16 个边界反事实；16/16 均失败于路线与全局交叉非增以及严格改善，14/16 还存在 same-net cycle。
- 最接近者 `svg-edge-0080 → reconvergent_mux_00` top 不含 cycle 拒因，但反事实会使路线交叉点 10→12、事件 19→21，全局交叉点 35→36、事件 384→386；现状确实更优，不是被单个门误拦的症状。
- 因此不做局部端口投机。下一步新增两个单变量正式场景：基于已闭合 8 行案分别只启用 paired consumer、只启用 dense downstream，继续双跑/29 指标/Oracle。

## 2026-09-22 02:12：paired/dense 单变量场景登记

- 正式生成器新增 `dual-public-repeated-direct-paired` 与 `dual-public-repeated-direct-dense`；二者均从已闭合的 8 行 repeated-direct 控制案派生，分别只改变 `ladder_consumers: one→paired`、`obstacle_pattern: none→dense-downstream`。
- 两案保持同一双根直入、PLL weave、目标右移、声明顺序与根输出合同。下一步先重跑结构闭包测试，再分别执行正式 named-scenario 门。

## 2026-09-22 02:22：paired/dense 两案均为正式干净反例

- 定向测试再次 2 passed。paired 与 dense 两案均完成公开 CLI 双跑、SHA 一致性、29 指标和独立 Oracle；覆盖缺口 0、语义前置条件 true、失败指标/issue/witness 均为 0，正式 runner 按 `--expect reproduced` 各自 exit 1。
- paired SVG SHA-256 为 `87977AA7994491A5B1D2762B8B2A6A96155467961FCB233D4BDC1477B302D669`；dense 为 `DCFB572A6595D13C170C76FC08DD5314C2B971E5C35AFCAC7F9079A99FF77235`。paired 增加计算成本但未制造目标症状，dense 也未改变结论。
- 辅助候选对比运行 3 分钟仍未返回，已按上限 Ctrl-C；它不影响两份正式绿灯回执。下一步不重复该高成本诊断，新增 16 行、单消费者、无障碍场景，只隔离 `row_count` 规模变量。

## 2026-09-22 02:23：16 行单变量规模场景登记

- 正式生成器新增 `dual-public-repeated-direct-sixteen-rows`：相对 8 行控制案只将 `row_count: 8→16`，继续使用单消费者和无障碍模式，避免重现此前 paired+dense 三压力叠加的首遍渲染超时。
- 下一步执行该 named-scenario 的公开 CLI 双跑、SHA、29 指标与独立 Oracle；仍以有限等待窗口管理高成本渲染。

## 2026-09-22 02:26：16 行规模变量正式排除

- 16 行单消费者无障碍案完成公开 CLI 双跑，SVG SHA-256 均为 `8B837537A810E6ECC6E5073479098059AFD4E2CD4F53B96479BD419205D3AB9F`；named-scenario 覆盖缺口 0。
- `semantic_preconditions_met=true`，29 指标失败 0、Oracle issue/witness 0，故 `--expect reproduced` 正确 exit 1。单独增加行数没有产生目标症状。
- 下一步维持 8 行/单消费者/无障碍，分别隔离 `pll_weave=aligned/rotate` 和 `target_band=external-lower` 几何变量；不再重复 mirror+lower 的已绿组合。

## 2026-09-22 02:27：三项单变量几何场景登记

- 正式生成器新增 repeated-direct 的 aligned、rotate、external-lower 三个命名场景；相对 8 行 mirror+lower 控制案，各案只改变一个覆盖因子。
- 下一步顺序执行三案的公开 CLI 双跑、SHA、29 指标与独立 Oracle，并分别保存回执；任一精确目标红灯将立即停止扩展并解锁产品修复阶段。

## 2026-09-22 02:31：三项几何变量排除与剩余 pairwise 规划

- aligned、rotate、external-lower 三案均完成公开 CLI 双跑；SHA 分别为 `4801142C…C4BE6`、`48F6B916…93808`、`4E607401…A3AF4`，且三案均语义成立、覆盖缺口 0、29 指标/Oracle 全绿、目标 witness 0。
- 扩展后的完整 pairwise 域为 29 cases / 1129 units，其中 repeated-direct 共 15 案；已有 7 个命名 repeated-direct 案闭合，剩余 8 个由 greedy closure 生成，位于 suite index 11、12、13、16、18、26、27、28。
- 现有 `--scenario` 只能执行命名案。下一步给正式 runner 增加互斥的 `--case-index` 单案入口，回执明确标注 `pairwise-case-index` 且只声明该案覆盖单元，用同一双跑/29 指标/Oracle 合同逐案完成剩余新覆盖。

## 2026-09-22 02:31：正式 pairwise 单案入口落地

- runner 新增与 `--scenario` 互斥的 `--case-index`，边界检查基于当前确定性 `covering_suite()`；单案仍执行公开 CLI 双跑、SHA、完整指标与 Oracle。
- 单案回执使用 `coverage_scope=pairwise-case-index:N`，required/missing 只针对选中 case 的覆盖单元，不冒充 29 案全域完成。下一步验证 CLI/闭包后执行 8 个尚未闭合的 repeated-direct index。

## 2026-09-22 02:40：剩余 repeated-direct pairwise 结果与目标列语义逃逸

- 语法、定向测试 2 passed、五件套 PASS；index 11、13、18、26、28、12、27、16 八案均完成公开 CLI 双跑与完整回执，全部 `target_witnesses=0`，未命中 FB-ROUTE-023。
- index 13 失败 `shared_root_single_bus,mergeable_root_facility`，index 26 失败 `shared_root_single_bus`，index 16 同时失败前两项；这些是诚实的非目标质量红灯，不能冒充目标复现。其余五案全绿。
- 审计生成器发现 `mux_offset` 在 complex row 仅施加给前级 `mux_i`，而 repeated-direct 的两个公共根实际进入 `reconvergent_mux_i`；真正目标未右移，导致“右侧重汇聚目标”因素名实不符。
- 下一步补断言并让 late complex row 的 reconvergent（含 serial terminal）获得与 offset 对应的明确 layout column，再重跑核心代表案。该修正仍只改变正式输入生成器，产品布局器继续冻结。

## 2026-09-22 02:41：真实重汇聚目标列约束修正

- complex late row 现把 `mux_offset` 同时落实到真正接收双根的 base reconvergent（列 `6+offset`）；serial-remerge terminal 使用列 `7+offset`，external target-ladder 的 reconvergent 也使用列 `6+offset`。
- 回归断言明确 8 行 lower/offset4 案的前级 `mux_07` 为列 9、真实 `reconvergent_mux_07` 为列 10，防止再次只移动前级节点却宣称目标右移。
- 下一步先跑结构/闭包测试，再用原核心命名场景生成新几何并执行完整红灯合同。

## 2026-09-22 02:43：显式目标列未改变自然几何

- 定向测试 2 passed；核心命名场景新输入确含 `reconvergent_mux_07.layout_column=10`，输入 SHA 已变化，但双跑 SVG SHA 仍与修正前完全相同：`305A50432DB006330C90F339BBE41EDE53CBC86D3568532E1044E54EAEEB244D`。
- 29 指标/Oracle 仍全绿、目标 witness 0；说明 ELK 原本就在等效列，单独补显式 reconvergent 列约束不形成新的几何压力。
- 下一步隔离 `root_bus_position=second-branch-axis`：让第二公共根位于内部 branch axis，同时保留 8 行 repeated-direct、右侧重汇聚目标与其余控制变量。

## 2026-09-22 02:44：第二公共根内部轴场景登记

- 新增 `dual-public-repeated-direct-second-axis`，仅将核心控制案的 `root_bus_position` 从 `left-axis` 改为 `second-branch-axis`；第二公共根获得 `layout_column=2`。
- 下一步执行同一正式双跑/SHA/29 指标/Oracle 合同，验证内部根列是否诱发公共总线过早横穿与随后纵穿。

## 2026-09-22 02:45：内部根列无几何区分并发现直入端口覆盖缺口

- second-axis 案完成双跑且 29 指标/Oracle 全绿，输入 SHA 改变但 SVG SHA 再次为 `305A50432DB006330C90F339BBE41EDE53CBC86D3568532E1044E54EAEEB244D`；第二根列约束在该拓扑中与自然布局等效。
- 进一步审计发现现有 `port_permutation` 只交换前级 branch mux 的两个输入；repeated-direct 的 `reconvergent mux4` 始终固定 `public_root_a→port1`、`public_root_b→port2`，双公共根直入端口顺序从未覆盖。
- 下一步新增独立 `direct_root_port_order` 因子与反向命名场景，并在结构测试中断言根端口交换；产品代码仍冻结。

## 2026-09-22 02:46：双根直入端口顺序因子落地

- 正式覆盖模型新增两值 `direct_root_port_order`，所有既有命名场景显式/默认采用原顺序，新 `dual-public-repeated-direct-port-swap` 使用反向顺序。
- `reconvergent_item` 现按该因子交换 mux4 上的 public_root_a/public_root_b 直入端口，测试补充 port1/port2 的具体反向断言；pairwise required units 将据此扩展。
- 下一步先把因子值命名收敛为与 mux 元数无关的 before/after 语义，使 simple mux4 的 port2/3 也能真实表达同一顺序维度，再运行结构闭包。

## 2026-09-22 02:48：跨 mux 元数的直入顺序语义收敛

- 因子值改为 `a-before-b/b-before-a`：complex reconvergent mux4 对应交换 port1/2，simple mux4 对应交换 port2/3；因此同一覆盖因子在两类拓扑都实际改变输入顺序，不再产生“值已覆盖但图未变化”的假覆盖。
- 反向命名场景同步为 `b-before-a`，既有场景默认 `a-before-b`。下一步执行结构、pairwise 闭包测试和反向端口正式双跑。

## 2026-09-22 02:50：反向直入端口产生真实近失配几何

- 定向测试 2 passed；port-swap 正式双跑 SVG SHA-256 均为 `D6BC6201592796FDF297CA7D10CF08EDC518B47E552E8E1F020E61CDDEFF1A75`，与控制案不同，证明端口顺序因子真实改变几何。
- 该案 29 指标/Oracle 仍全绿、目标 witness 0。候选诊断中最佳 `svg-edge-0023→reconvergent_mux_00` top 已不含 same-net cycle，反事实全局交叉点 32→32，但路线交叉 10→13、全局事件 164→167，仍没有严格改善。
- 相比控制案最佳的全局点 35→36，反向端口已消掉一个主要拒因并形成更近反例。下一步分别叠加 paired consumer 与 dense downstream，验证是否只增加现状内侧路线交叉而不增加边界反事实。

## 2026-09-22 02:51：port-swap 二阶压力场景登记

- 新增 `port-swap-paired` 与 `port-swap-dense` 两案；均以已确认改变几何的 b-before-a 案为基线，分别只叠加 paired consumer 或 dense downstream。
- 下一步两案各自执行正式双跑/29 指标/Oracle；paired 采用有界等待，避免重复此前大图无限计算问题。

## 2026-09-22 02:57：port-swap paired/dense 二阶组合均未命中

- 两案均完成公开 CLI 双跑、29 指标和 Oracle，语义前置条件 true、失败指标/issue/witness 均为 0；paired SHA `012720C5…5FBF`，dense SHA `637166D8…A0E8`。
- dense 候选诊断最佳全局点可持平 30→30，但仍为路线交叉 11→14、事件 168→171，且带 same-net cycle；另一个无 cycle 候选为全局点 30→32。dense 没有向严格改善推进。
- port-swap 控制案的无 cycle 近失配仍优于 dense。下一步固定 b-before-a 与其他变量，分别只把声明顺序从 interleaved 改为 forward/reverse，验证行顺序是否让现状内侧段承担更多交叉。

## 2026-09-22 02:58：port-swap 声明顺序场景登记

- 新增 b-before-a 的 forward 与 reverse 两案；相对 port-swap 控制案仅改变 `declaration_order`，保留 8 行、单消费者、无障碍和 mirror weave。
- 下一步执行两案正式双跑门；命中精确目标红灯即停止搜索，否则比较回执并收敛该变量。

## 2026-09-22 03:01：声明顺序变量未改善近失配

- forward/reverse 两案均双跑确定、29 指标/Oracle 全绿、目标 witness 0；两案 SVG 不同，但最佳候选数值完全相同：路线交叉 10→13、全局点 32→32、事件 164→167，均缺路线/事件非增和严格改善。
- 声明顺序只把最佳目标从 `reconvergent_mux_00` 换到 `_07`，没有使现状内侧路线更差，因此收敛该变量。
- 下一步固定 port-swap 控制案，分别只启用 `interleaved-public` 与 `reverse-private`；这两类障碍直接向 mux 区引入额外支路，比 dense downstream 更可能形成“现状横段被纵穿、边界反事实避开”的差异。

## 2026-09-22 03:02：port-swap mux 区障碍场景登记

- 新增 `port-swap-interleaved-public` 与 `port-swap-reverse-private` 两案，分别引入第三公共根支路或反序私有根支路；其余变量与 b-before-a 控制案一致。
- 下一步执行正式双跑/29 指标/Oracle，并对任何非目标质量红灯单独记录，不把它计作 FB-ROUTE-023 复现。

## 2026-09-22 03:08：interleaved-public 近失配实为已在边界的等价路线

- interleaved-public 与 reverse-private 两案均双跑确定、29 指标/Oracle 全绿、目标 witness 0。前者最佳候选仅剩 `global_crossing_strictly_improved`，计数全部持平；后者仍是路线 10→13、事件 +3 的旧近失配。
- 单边解析确认 `svg-edge-0022` 现状点列已经从 x177.66 沿 y=52 上边界横到 x851.86，再下行到目标；top 反事实与现状逐点相同，所以不是过早内侧横穿。Oracle 严格改善门正确拒绝该伪近失配。
- 下一步固定 b-before-a + interleaved-public，分别把 `root_kinds` 改为 `from/from` 与 `source/from`，改变第二根的布局角色，验证能否让公共根横段自然落到内侧而非上边界。

## 2026-09-22 03:09：port-swap 根类型角色场景登记

- 新增 `port-swap-both-from` 与 `port-swap-source-from`；相对 from/source 案只改变公共根 glyph 类型顺序，继续保留 interleaved-public 障碍与其余控制变量。
- 下一步执行两案正式双跑门，并检查目标边现状横段是否离开 y=52 边界。

## 2026-09-22 03:16：根 glyph 角色排除与跨行公共障碍缺口

- both-from/source-from 两案均完成双跑、29 指标/Oracle 全绿、目标 witness 0；坐标审计表明除 glyph 起点宽度外，双根进入 reconvergent 的主干点列相同，根 kind 没有改变所需几何。
- 内侧候选 `svg-edge-0087 public_root_a→reconvergent_mux_00` 的现状横段位于 y=436.3164；top 反事实移除 2 个交叉但新增 4 个，路线 9→12、全局点 89→91，仍是现状更优。
- 现有 `interleaved-public` 只把第三公共根 gate 接入同号行，未系统产生跨行纵向支路。下一步新增正式 `reverse-interleaved-public` 障碍值：gate i 接入 mux N−1−i，并用结构测试断言倒序映射，以覆盖“内侧横段随后被纵穿”的缺失交互。

## 2026-09-22 03:17：倒序跨行第三公共根障碍落地

- `obstacle_pattern` 新增 `reverse-interleaved-public` 正式取值；生成器仍创建同一第三公共根及逐行 gate，但把 gate i 接入倒序 mux N−1−i，形成合法、可扩展的跨行纵向公共支路。
- 新增 b-before-a 命名场景及结构断言：8 行案 `obstacle_gate_00→mux_07.port3`、`obstacle_gate_07→mux_00.port3`。下一步先过结构/pairwise 闭包，再执行正式双跑红灯门。

## 2026-09-22 03:22：倒序跨行案近失配与顶行不对称因子归纳

- 结构/pairwise 测试 2 passed；倒序跨行案双跑 SHA `AAC37083…BBD3C`，29 指标/Oracle 全绿、目标 witness 0。
- 候选 `public_root_b→reconvergent_mux_07` top 已做到路线交叉点 6→6、事件 42→36，但仍有 same-net cycle 与全局点 89→91；诊断给出的唯一单边 cycle breaker 是 `public_root_b→reconvergent_mux_00`。
- 将该结构归纳为正式 `direct_entry_pattern=all/top-main-omit-b`：仅顶行主重汇聚省略 B 直入，其他行继续双根重复直入，表达合法的不对称行输入而非手改 SVG。下一步加入结构断言并运行目标合同。

## 2026-09-22 03:24：顶行省略 B 的正式输入模式落地

- 覆盖模型新增 `direct_entry_pattern=all/top-main-omit-b`；complex 拓扑把顶行主 reconvergent 合法降为 mux3（primary、root A、PLL），simple 拓扑也把顶行合法降为含两个 branch 与 root A 的 mux3，其余行保持双根直入。
- 新命名场景组合 b-before-a、top-main-omit-b 与 reverse-interleaved-public；测试断言顶行不含 root B、下一行仍同时包含 A/B，确保语义仍是“重复双根 + 单行不对称”。
- 下一步执行结构/pairwise 闭包与正式双跑目标门。

## 2026-09-22 03:26：公开 CLI 捕获 staggered mux3 后置端口错误

- 结构/pairwise 测试 2 passed，但正式场景首遍公开 CLI exit 1，错误指向 `reconvergent_mux_00` 的非法 port3 映射；没有生成 SVG，不能解释为布局红灯。
- 根因是后置 PLL weave 仍按全局 `repeated_direct` 选择 port3，而顶行已由 staggered 模式降为 mux3，应继续使用 port2。下一步改为按目标节点实际 kind 选端口（mux4→3、mux3→2）并重跑。
- 该失败发生在输入生成器/校验阶段，对产品布局器无影响；`src/elk_layout.py` 仍冻结。

## 2026-09-22 03:26：PLL weave 改按节点实际元数写端口

- 后置 PLL weave 现读取每个 `reconvergent_mux_i.kind`：mux4 写 port3，mux3 写 port2，不再由全局 repeated-direct 标志推断。
- 下一步补充顶行 mux3 端口集合必须恰为 0/1/2 的回归断言，再执行公开 CLI 与完整红灯合同。

## 2026-09-22 03:27：staggered mux3 端口集合回归门补齐

- 测试现断言顶行 `reconvergent_mux_00` 的 source key 恰为 `{0,1,2}`，并继续断言不含 root B；这会直接捕获此前多写 port3 的生成器回归。
- 下一步重跑定向测试与同一正式场景，只有通过公开 CLI 双跑后才进入 Oracle 结论。

## 2026-09-22 03:31：8 行 staggered 倒序跨行案推进到点数双拒因

- 定向测试 2 passed，修正后公开 CLI 双跑及 29 指标/Oracle 完成；SVG SHA `69C888A6…6997`，语义前置条件 true、质量失败/issue/witness 均为 0，尚未命中目标。
- 最佳候选 `public_root_a→reconvergent_mux_06` bottom 的事件已严格改善：路线事件 20→16、全局事件 237→233；无 same-net cycle/box hit，只剩路线不同交叉点 5→8、全局点 47→52 两项拒因。
- 下一步只把同一正式模式 `row_count: 8→16`，维持单消费者，利用翻倍的倒序跨行公共支路验证现状内侧段能否增加至少 3 个不同纵穿点；采用有界渲染等待。

## 2026-09-22 03:32：16 行 staggered 倒序跨行场景登记

- 新命名场景相对 8 行案仅把 row_count 改为 16，其他根类型、端口顺序、不对称模式、倒序公共障碍、消费者数与目标偏移保持一致。
- 下一步执行正式双跑/29 指标/Oracle；首遍或次遍渲染按产物进展与有限窗口管理。

## 2026-09-22 03:38：16 行案在第二遍被有界中止

- 运行约 4.5 分钟时最后一次检查仍只见 input，随后发出 Ctrl-C；事后核对发现 `first.svg` 实际已于 03:37:02 落盘，中止时残留命令行正在生成 `second.svg`。已按精确命令行清理本轮 PID 24380/13624。
- 该案只有第一遍 195,069-byte SVG，没有第二遍 SHA 与 Oracle 回执，不能声明复现或反例；部分产物仅用于性能记录，不复用为完整门禁证据。
- 下一步把 12 行加入正式 row_count 域，运行同一 staggered 倒序跨行模式的完整双遍；若命中再停止搜索，否则据点数差决定是否值得完整重跑 16 行。

## 2026-09-22 03:40：12 行中间规模纳入正式域

- `row_count` 正式域从 4/8/16 扩为 4/8/12/16，并新增 12 行 staggered + reverse-interleaved-public 命名场景；其他变量与 8/16 行案完全一致。
- 这会扩展 pairwise required units，结构闭包测试必须重新通过；随后执行 12 行公开 CLI 双跑、SHA、29 指标与 Oracle。

## 2026-09-22 03:50：12 行案只剩全局不同点拒因

- 扩展闭包测试 2 passed；12 行案完成公开 CLI 双跑，SVG SHA `A80AC5C0…ACD6`，29 指标/Oracle 全绿、目标 witness 0，是正式干净反例。
- 最佳候选 `public_root_a→reconvergent_mux_10` bottom 仅剩 `global_points_nonincreasing`：路线不同点 14→9、事件 40→20，全局事件 542→522，严格改善等其余门均通过；唯独全局不同点 74→80。
- 共享 obstacle root 使大量现状事件堆叠在较少坐标。下一步新增正式 `reverse-interleaved-private`：每行独立 obstacle root/gate，仍倒序接 mux，以分散纵向通道 x 并增加现状不同交叉点。12 行趋势已足够，不再完整重跑更昂贵的 16 行共享根案。

## 2026-09-22 03:52：倒序独立根障碍模式落地

- `obstacle_pattern` 新增 `reverse-interleaved-private`：每行创建独立 `obstacle_root_i→obstacle_gate_i`，并倒序接入 mux N−1−i；与共享第三公共根模式相比，纵向通道具备独立布局来源。
- 新增同一 12 行 staggered 场景与结构断言：gate00/gate01 分属 root00/root01，gate00 接 mux11.port3。下一步重跑结构/pairwise 闭包及正式双跑红灯门。

## 2026-09-22 04:03：独立根方案证伪与全局点差归因

- 结构/pairwise 测试 2 passed；12 行独立根案双跑 SHA `4ACFD358…CE36`，29 指标/Oracle 全绿、witness 0。候选质量显著退化并大量 box hit，全局不同点仅 35，说明拆散共享根破坏了所需总线几何。
- 回到共享根 12 行最佳边 `svg-edge-0203`：bottom 反事实在目标纵通道 x=951.86 新增 7 个不同 y 交叉、源通道新增 1 个堆叠点，同时移除 2 个旧点，净增 6，精确解释全局点 74→80。
- 最佳目标是倒数第二行 `reconvergent_mux_10`，而 `target_band=lower` 的 offset 只作用最后一行 11。下一步新增正式 `penultimate` 目标带，让 offset 作用倒数第二行并验证目标纵通道右移是否避开新增点。

## 2026-09-22 04:04：倒数第二行目标带落地

- `target_band` 正式域新增 `penultimate`，映射 `max(0,row_count-2)`；新 12 行共享根场景把 offset4 施加到 `reconvergent_mux_10`。
- 回归断言要求 mux10 layout column=10、mux11 无显式列，防止 offset 再次落错目标。下一步重跑结构/pairwise 闭包及正式双跑红灯门。

## 2026-09-22 04:14：penultimate offset4 缩小全局点差但新增路线点拒因

- 结构/pairwise 测试 2 passed；penultimate offset4 案双跑 SHA `7DB27239…73DA`，29 指标/Oracle 全绿、witness 0。
- 最佳 mux10 bottom 候选事件微幅改善（路线 7→6、全局 530→529），全局点差由 lower 案 +6 缩到 +3（76→79），但路线不同点由 lower 案 14→9 退化为 3→6，因此新增 `route_points_nonincreasing` 拒因。
- 下一步在同一 penultimate 带补跑现有 mux_offset 0/2，完成 0/2/4 梯度；目标是同时保留路线点改善并把全局点差压到非增，不扩展新因素。

## 2026-09-22 04:15：penultimate offset0/2 梯度场景登记

- 新增 12 行 penultimate 的 offset0 与 offset2 两个命名场景；除 mux_offset 外与 offset4 案完全一致。
- 下一步顺序执行两案正式双跑/29 指标/Oracle；任一精确红灯会停止后续案，否则比较三档候选差值后收敛列偏移变量。

## 2026-09-22 04:26：penultimate offset 0/2/4 三档几何完全等价

- offset0 与 offset2 两案均完成公开 CLI 双跑、29 指标/Oracle，全绿且 witness 0；三档输入 SHA 各异，但 SVG SHA 全部为 `7DB272396E9CCC0B7E209EB7C77F35DA04B1C1212806EEC908CF61965B8473DA`。
- 因此 mux_offset 在该 penultimate 拓扑中不产生几何区分，列偏移变量收敛，不再重复。
- 下一步新增共享根 `rotate-interleaved-public`：gate i 接入 `(i+N/2) mod N` 行 mux，打破 full reverse 对称堆叠但保留跨行纵向公共支路，验证能否把现状事件分散为更多不同点。

## 2026-09-22 04:28：半圈 rotate 跨行公共障碍落地

- `obstacle_pattern` 新增 `rotate-interleaved-public`，共享第三公共根的 gate i 接入 `(i+N/2) mod N` mux；12 行断言 gate00→mux06、gate06→mux00。
- 新场景沿用 12 行 lower 单拒因基线的 b-before-a、top-main-omit-b 与其余变量，只替换 reverse→rotate 映射。下一步重跑结构/pairwise 闭包及正式双跑门。

## 2026-09-22 04:38：rotate 映射未改变近失配数值

- 结构/pairwise 测试 2 passed；rotate 案双跑 SHA `24010AE5…EA97`，29 指标/Oracle 全绿、witness 0。虽然 SVG 与 reverse 不同，最佳候选数值完全相同：路线 14→9/40→20、全局 74→80/542→522，仅 `global_points_nonincreasing` 拒绝。
- 共享根 cross-row 映射方式没有改变该目标边的全局点差，收敛 reverse/rotate 方向。
- 下一步新增 `direct_entry_pattern=penultimate-main-omit-a`：仅倒数第二行主 reconvergent 省略 A，最后一行仍双根直入；移除当前 mux10 问题边并检验最下行短 bottom 边界候选。

## 2026-09-22 04:39：倒数第二行省略 A 模式落地

- `direct_entry_pattern` 新增 `penultimate-main-omit-a`；complex/simple 拓扑均只在 `row_count-2` 主 mux 省略 A 直入并合法降为 mux3，其他行保持双根直入。
- 新 12 行共享根 reverse 场景及断言要求 mux10 不含 A、mux11 仍同时含 A/B。下一步重跑结构/pairwise 闭包与正式双跑目标门。

## 2026-09-22 04:51：penultimate 省略 A 证伪并转对称省略 B

- 结构/pairwise 测试 2 passed；省略 A 案双跑 SHA `81CED85D…CB42`，29 指标/Oracle 全绿、witness 0。
- 该不对称使全局点基线上升到 112，但最佳边已是与边界完全等价的 mux00 top，仅缺严格改善。mux10 剩余 B 路线事件 20→16、全局点 112→113，却仍有 cycle 和路线点 4→5。
- 下一步补对称 `penultimate-main-omit-b`：保留 A、移除 B，验证能否同时保留原 A 路线 14→9 的改善与重排后的高全局点基线。

## 2026-09-22 04:52：倒数第二行省略 B 模式落地

- `direct_entry_pattern` 新增 `penultimate-main-omit-b`；在倒数第二行合法 mux3 中保留 primary、root A 与 PLL，移除 root B，其余行仍双根直入。
- 新 12 行共享根 reverse 场景与回归断言已补齐。下一步执行结构/pairwise 闭包及正式双跑目标门。

## 2026-09-22 05:02：penultimate 省略 B 证伪并回归原近失配

- 结构/pairwise 测试 2 passed；省略 B 案双跑 SHA `4B0AD34C…312E`，29 指标/Oracle 全绿、witness 0。
- mux10 保留的 A 路线反事实显著恶化为路线点 14→26、事件 37→55，全局 84→105/514→532；最佳仍是与边界等价的 mux00。倒数第二行省略 A/B 两方向均收敛。
- 回到 `top-main-omit-b + reverse-interleaved-public` 的 12 行单拒因基线。下一步只把已有 `port_permutation` 从 a-1-b-0 改为 a-0-b-1，重排前级 branch 路线，观察全局点基线是否改变而保留 direct 候选。

## 2026-09-22 05:03：前级 branch 端口交换场景登记

- 新 12 行命名场景沿用单拒因基线，仅将 `port_permutation` 改为 `a-0-b-1`；reconvergent 的 direct root 顺序仍为 b-before-a。
- 下一步执行正式双跑/29 指标/Oracle；该场景不引入新因子实现，因此直接验证现有覆盖值组合。

## 2026-09-22 05:13：branch 端口交换把单拒因点差缩到 +4

- branch-swap 案双跑 SHA `836D2EF4…9142`，29 指标/Oracle 全绿、witness 0。
- 最佳 mux10 bottom 候选仍只失败 `global_points_nonincreasing`；路线 17→8 点、77→55 事件，全局事件 672→650，严格改善充分，全局不同点 54→58，点差从原基线 +6 缩到 +4。
- 下一步固定该组合，只把既有 `pll_weave` 从 mirror 改为 rotate；目标是用邻行 weave 分散现状交叉坐标，同时减少边界纵通道新增点，不扩展新因子。

## 2026-09-22 05:16：branch-swap + rotate 正式场景登记

- 新增 12 行命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-rotate-twelve`；相对当前 +4 单拒因基线只把既有 `pll_weave` 从 `mirror` 改为 `rotate`，其余生成因子完全固定。
- 下一步经公开 CLI 双跑、SHA 一致性、完整 29 指标与独立 SVG Oracle 验证；只有失败指标精确为 `premature_interior_trunk_entry` 且语义前置条件、自然 witness 同时成立，才解冻 `src/elk_layout.py`。

## 2026-09-22 05:23：branch-swap + rotate 正式门全绿但未命中

- 正式公开 CLI 双跑完成，两份 SVG 一致，SHA-256 `E54690E7…0C92`；语义前置条件成立，命名单案覆盖 190/190 单元，29 指标与独立 Oracle 均无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 因未命中按契约退出 1，不是运行故障；`src/elk_layout.py` 继续冻结。下一步只读运行候选反事实诊断，量化 rotate 相对 mirror 的全局不同点差。

## 2026-09-22 05:27：rotate 与 mirror 候选数值等价

- 16 条合格路线的边界反事实诊断完成；最佳仍是 `svg-edge-0203 public_root_a→reconvergent_mux_10 bottom`，仅拒因 `global_points_nonincreasing`。
- 数值与 mirror 完全相同：路线不同点 17→8、事件 77→55，全局不同点 54→58、事件 672→650，故 rotate 没有缩小 +4 缺口。
- 下一步保持 branch-swap 单拒因组合不变，仅测试正式因素域中尚未用于该组合的 `pll_weave=aligned`；若仍等价则收敛整个 weave 轴。

## 2026-09-22 05:28：branch-swap + aligned 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-aligned-twelve`；它与 +4 单拒因 mirror 基线只在既有 `pll_weave=aligned` 上不同。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；若未精确命中，再依据候选差值决定是否关闭 weave 轴。

## 2026-09-22 05:34：branch-swap + aligned 正式门全绿但未命中

- 两次公开 CLI 渲染一致，SVG SHA-256 `06257327…0FE6`；语义前置条件成立，覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 按未命中契约退出 1；该 SVG 与 mirror/rotate 哈希不同，证明 aligned 产生了不同几何，但尚不能据此判断候选方向。下一步运行该轴最后一次候选诊断。

## 2026-09-22 05:38：aligned 缩小全局点差但破坏路线点，weave 轴收敛

- aligned 最佳候选改为 `svg-edge-0157 public_root_a→reconvergent_mux_09 bottom`：全局不同点 54→57（+3）与事件 608→607，但路线不同点 5→8，故同时失败 `route_points_nonincreasing` 与 `global_points_nonincreasing`。
- mirror/rotate 均为原 mux10 单拒因 +4，aligned 为 mux09 双拒因 +3；`pll_weave` 的 aligned/mirror/rotate 三值已完整覆盖并收敛。
- 下一步回到 mirror + branch-swap 单拒因基线，仅把已有 `second_root_extra_output` 从 `multiple` 降为 `one-direct`，移除 B 根额外 gate 链但保留其额外直接消费者，检验全局点基线能否改变而不破坏 A 目标路线改善。

## 2026-09-22 05:39：branch-swap + one-direct 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-one-direct-twelve`；相对 mirror + branch-swap 单拒因基线仅将 `second_root_extra_output` 从 `multiple` 改为 `one-direct`。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；仍以目标指标单红、语义前置条件和自然 witness 三者同时成立作为产品代码解冻条件。

## 2026-09-22 05:47：branch-swap + one-direct 正式门全绿但未命中

- 两次公开 CLI 渲染一致，SVG SHA-256 `487A0D3A…6572`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 按未命中契约退出 1；删除 B 根额外 gate 链确实改变了几何，但尚未形成自然红灯。下一步运行候选反事实诊断，决定是否继续同轴的 `none` 或切换其他既有因素。

## 2026-09-22 05:51：one-direct 破坏单拒因结构，停止向 none 递减

- one-direct 的合格路线由 16 增至 20，但原 mux10 bottom 单拒因候选消失；最佳三条均只取得路线事件减 1，并同时失败 same-net cycle 与全局点非增，全局点 71→73。
- extra-output 从 multiple 向 one-direct 的最小递减已使近失配退化，因此不继续同向测试 none。
- 下一步回到 multiple + mirror + branch-swap 单拒因基线，使用已有 `annotation_pressure=row-band` 给各行 mux 增加合法公开 description 压力；该变量不改变双公共根直入语义，检验盒宽/行带压力是否提高现状交叉基线并消除 +4。

## 2026-09-22 05:52：branch-swap + row-band 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-row-band-twelve`；相对 +4 单拒因基线仅启用已有 `annotation_pressure=row-band`，为 12 个行 mux 添加公开 schema 支持的 description。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；description 只作为合法布局压力，不改变目标复现的语义门槛。

## 2026-09-22 05:58：branch-swap + row-band 正式门全绿但未命中

- 两次公开 CLI 渲染一致，SVG SHA-256 `C8C16240…3865`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 按未命中契约退出 1；row-band 合法改变了 SVG 几何但没有直接形成自然红灯。下一步运行候选反事实诊断，判断 description 压力是缩小 +4 还是破坏近失配。

## 2026-09-22 06:02：row-band 不改变路由候选，annotation 轴收敛

- row-band 的最佳候选仍为 `svg-edge-0203 public_root_a→reconvergent_mux_10 bottom`，路线 17→8/77→55、全局 54→58/672→650，与无 annotation 的 +4 单拒因基线完全一致。
- SVG 哈希变化来自 description 表面，路由几何与拒因不变；不再测试更弱的 late-target annotation。
- 下一步固定其余近失配因子，仅将已有 `declaration_order` 从 `interleaved` 改为 `forward`，验证行声明顺序是否改变公共根总线的通道占用并保留目标路线改善。

## 2026-09-22 06:03：branch-swap + forward 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-forward-twelve`；相对 +4 单拒因基线仅将已有 `declaration_order` 改为 `forward`。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle，再以候选诊断决定是否有必要补对称 reverse。

## 2026-09-22 06:09：branch-swap + forward 正式门全绿但未命中

- 两次公开 CLI 渲染一致，SVG SHA-256 `C7FA6FB1…2207`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 按未命中契约退出 1；forward 改变了输出哈希但没有直接产生目标红灯。下一步运行候选诊断，若差值无改善则不补对称 reverse。

## 2026-09-22 06:13：forward 仅重编号等价候选，声明顺序轴收敛

- forward 最佳候选仍为 public_root_a 的 bottom 反事实，路线 17→8/77→55、全局 54→58/672→650，与 interleaved 完全一致；仅目标从 mux10 映射到 mux05。
- 声明顺序没有产生数值梯度，不补 reverse。
- 下一步在 +4 单拒因基线上启用已有 `root_bus_position=second-branch-axis`，仅给 public_root_b 设置 layout_column=2；目标是改变 B 根水平轴对 A 根目标通道的占用，同时保持双根直入语义。

## 2026-09-22 06:14：branch-swap + second-axis 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-second-axis-twelve`；相对 +4 单拒因基线仅将 public_root_b 放到已有的第二分支轴（layout_column=2）。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle，并用候选差值判断根轴方向是否有效。

## 2026-09-22 06:20：second-axis 与原 +4 基线 SVG 完全等价

- 两次公开 CLI 渲染一致，语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- second-axis 的输入不同，但 SVG SHA-256 为 `836D2EF4…9142`，与原 branch-swap + mirror 单拒因基线逐字节一致；B 根 layout_column=2 在该拓扑中不产生几何差异，根轴方向收敛，无需重复候选诊断。
- 下一步运行生成器结构/pairwise 回归、五件套门禁及 `src/elk_layout.py` 冻结检查，确认本轮生产端覆盖扩展自身完整。

## 2026-09-22 06:30：本轮生成覆盖回归通过，门禁耗时升至九分钟

- 生成器可编译、五件套门禁 PASS、`src/elk_layout.py` 冻结检查 PASS；结构/公开 CLI/pairwise 相关筛选回归 `3 passed, 84 deselected`。
- 回归实际耗时 541.51 秒（9:01），相较此前约 52 秒显著增长；原因是筛选表达式命中真实公开 CLI/Oracle 路径并随命名场景扩展重复高成本渲染。结果完整通过，不是卡死，但机器门禁需要后续拆分“快速结构闭包”和“高成本真实双跑”层，仍须保证后者在正式收敛点强制执行。
- 本轮 rotate、aligned、one-direct、row-band、forward、second-axis 均完成合法生成输入的公开 CLI 双跑/独立 Oracle 或等价性收敛，尚未出现精确 `FB-ROUTE-023` 单红；目标保持 active，产品实现不解冻。下一搜索轴优先评估已有 `second_path` 或 paired ladder 对 +4 单拒因基线的最小扰动。

## 2026-09-22 06:32：选择 second_path=gate 作为下一最小扰动

- 实现审计确认 `second_path` 只控制非 late 行的 B 支路深度：`gate-div` 为 gate→div，`gate` 仅保留 gate；late 行仍由 `late_target_depth=gate-div` 控制，双公共根对 reconvergent mux 的直接输入不变。
- 相比给每一行新增 reconvergent peer 的 paired ladder，`second_path=gate` 扰动更小且归因清晰。下一步在 +4 单拒因基线上只切换该现有因素并执行正式双跑/Oracle。

## 2026-09-22 06:33：branch-swap + second-gate 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-second-gate-twelve`；相对 +4 单拒因基线只把非 late 行 B 支路从 gate→div 缩短为 gate。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；目标判定仍要求精确单红、语义前置条件和自然 witness 同时成立。

## 2026-09-22 06:39：branch-swap + second-gate 正式门全绿但未命中

- 两次公开 CLI 渲染一致，SVG SHA-256 `10C572E1…3D52`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- `--expect reproduced` 按未命中契约退出 1；缩短 11 条非 late B 支路改变了几何但没有直接形成目标红灯。下一步运行候选反事实诊断，量化它相对 +4 基线的变化。

## 2026-09-22 06:42：second-gate 缩小全局点差但新增路线点拒因

- 最佳仍为 `public_root_a→reconvergent_mux_10 bottom`，全局不同点 53→56（+3）、事件 411→410，但路线不同点 4→7，仅路线事件 19→18；同时失败 `route_points_nonincreasing` 与 `global_points_nonincreasing`。
- 缩短 B 支路破坏了原目标路线 17→8 的强改善，不继续该方向。
- 下一步回到原 +4 单拒因基线，仅将已有 `ladder_consumers` 从 one 改为 paired；新增 reconvergent peer 旨在提高现状全局交叉基线，同时检验原目标路线改善是否保留。

## 2026-09-22 06:43：branch-swap + paired 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-paired-twelve`；相对 +4 单拒因基线只将每行 reconvergent 消费者从 one 扩为 paired。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；该场景规模更大，保留原进程直到完整回执，避免再次产生不完整证据。

## 2026-09-22 06:59：branch-swap + paired 正式门全绿但未命中

- paired 两次公开 CLI 渲染均完整落盘并一致，SVG SHA-256 `6F971FE1…ABA4`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- 单次渲染约 5 分钟，双跑约 10 分钟，随后 Oracle 约 2 分钟；`--expect reproduced` 按未命中契约退出 1，没有中断或工具失败。
- 下一步运行 paired 候选反事实诊断，判断新增 reconvergent peer 是否提高了现状全局基线并保留目标路线改善；在量化前不继续扩大到 triple。

## 2026-09-22 07:19：paired 保留单拒因并把全局点差缩到 +3

- paired 候选诊断完整运行约 15 分钟，29 条路线可评估；进程持续占用 CPU并正常结束，没有超时或中断。
- 最佳 `svg-edge-0187 public_root_a→reconvergent_mux_01 bottom` 仍只失败 `global_points_nonincreasing`：路线不同点 7→7、事件 60→55，全局不同点 107→110、事件 907→902，无 cycle/box/overlap 拒因。
- 相比 one 消费者基线的 +4，paired 将唯一全局点差缩到 +3且未新增路线拒因，形成正向梯度。下一步沿同一正式因素轴测试 `ladder_consumers=triple`；若命中精确单红即解冻产品修复阶段，否则据差值收敛该轴。

## 2026-09-22 07:20：branch-swap + triple 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-twelve`；相对 paired 只再为每行增加第二个 reconvergent peer，其他因素完全固定。
- 下一步执行公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle。该图预计比 paired 更慢，必须保持同一进程到完整回执，不以单份 SVG 或阶段产物替代正式结果。

## 2026-09-22 09:41：branch-swap + triple 正式门完整全绿但未命中

- 两份公开 CLI SVG 均完整落盘且一致（224286 bytes），SHA-256 `5F7A89C7…269D`；语义前置条件成立、覆盖 190/190，29 指标与独立 Oracle 无失败，目标 witness 0、`target_reproduced=false`。
- 时间戳给出的真实阶段耗时：第一轮约 33:57、第二轮约 32:54、Oracle/回执约 11:30，总计约 78 分钟；此前轮询体感估时偏低，正式记录以文件时间戳为准。`--expect reproduced` 按未命中契约退出 1，没有不完整证据。
- paired 全量候选诊断已耗约 15 分钟，triple 候选规模更大。下一步先审计只读诊断器是否可在计算前按 source/target 预筛；正式 29 指标/Oracle 不裁剪，只优化方向选择用的辅助诊断，避免无意义的全边组合爆炸。

## 2026-09-22 10:03：triple 已跨过点/事件门，仅剩一个 peer-clock 重叠

- 辅助诊断器原生支持 `--edge` 计算前预筛，无需修改工具。按 paired 最优目标定向诊断 triple 的 `svg-edge-0207 public_root_a→reconvergent_mux_01` 仅耗约 14 秒。
- bottom 反事实已通过路线/全局点与事件门：路线点 9→7、事件 75→67，全局点 185→183、事件 2748→2740，无 box/cycle；唯一拒因是 route/global overlap 各自派生自同一个新增重叠。
- 重叠精确为目标纵段 x=1467.78 与 `svg-edge-0044 reconvergent_mux_01_peer_1→clock_01_peer_1` 的纵段，长度 260.003。生成器中 peer 列为 `6 + mux_offset + peer`；下一步把已有 `mux_offset` 从 4 降到 2，尝试移开 peer-clock 纵通道且保留已达成的改善。

## 2026-09-22 10:12：triple + offset2 正式场景登记

- 新增命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-offset2-twelve`；相对 triple 仅将 `mux_offset` 从 4 降为 2，peer layout_column 随之左移两列。
- 下一步执行完整公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle。尽管预计约小时级，仍以正式全量回执为唯一解冻依据；定向诊断只用于事后解释。

## 2026-09-22 11:47：offset2 与 offset4 完全等价，转正式 peer 输出形态因素

- offset2 完整双跑/Oracle 结束：两份 SVG 224286 bytes，SHA-256 `5F7A89C7…269D`，与 offset4 triple 逐字节相同；语义前置条件成立、覆盖 190/190、29 指标全绿、witness 0。阶段时间约 34:02 + 34:26 + 11:30，总计约 80 分钟。
- 因输入不同而 SVG 完全相同，peer 的 layout_column 提示被 ELK 归一，offset 轴收敛。
- 生成器审计确认命名场景可通过统一默认值补齐新因素。下一步新增正式 `peer_output_shape = direct-clock | gate-clock` pairwise 因素；gate-clock 在 peer 与 clock 之间插入公开 schema 支持的 gate，直接扰动造成唯一重叠的 peer 输出路径，而不是一次性改 SVG。

## 2026-09-22 11:51：peer_output_shape 正式因素与 gate-clock 场景落地

- 正式因素域新增 `peer_output_shape = direct-clock | gate-clock`，所有既有命名场景默认 direct-clock；普通行和 external-lower peer 输出共用同一构造函数，避免只修一个路径。
- gate-clock 形态为每个 reconvergent peer 生成 `peer→gate→clock`，全部使用公开 schema 节点；新命名场景在 triple +4 基线上仅切换该因素。
- 下一步先执行编译、结构断言与 pairwise 覆盖闭包；通过后再承担完整双跑/Oracle 的小时级成本。

## 2026-09-22 12:02：gate-clock 结构与 pairwise 闭包预检通过

- 生成器编译通过；直接构图确认 `reconvergent_mux_01_peer_1→clock_01_peer_1_gate→clock_01_peer_1`，并确认 direct-clock 默认结构未改变。
- 新增因素后的贪心 pairwise suite 为 77 案、required units 1814，实际覆盖集合与 required units 完全相等。
- 正式 pytest 结构测试补充 direct/gated peer 输出断言。下一步运行该目标测试；通过后启动 gate-clock 正式双跑。

## 2026-09-22 12:04：gate-clock 正式结构测试通过

- `test_dual_public_root_generator_models_repeated_direct_reconvergence` 通过（1 passed in 52.93s），覆盖 direct-clock 默认结构、gate-clock 新结构与完整 pairwise 闭包。
- 下一步启动 triple gate-clock 正式公开 CLI 双跑/29 指标/独立 Oracle；预计小时级，保持同一进程直到完整回执。

## 2026-09-22 12:39：gate-clock 正式门全绿未命中，原单重叠消失但 mux01 点门退化

- gate-clock 两份 SVG 均为 243937 bytes、SHA-256 `FE4568A5…1E4D`；语义前置条件成立、命名单案覆盖 210/210，29 指标/独立 Oracle 全绿、witness 0。实际阶段约 12:05 + 12:09 + 8:30，总计约 32:44。
- mux01 对应边变为 `svg-edge-0234`。定向 bottom 反事实无 overlap/cycle/box，说明目标单重叠已消除；但路线点 5→8、全局点 202→205，同时失败 route/global points，事件仍改善 69→68、1313→1312。
- 新 gate 可能重排真实最佳目标，不能只按 mux01 收敛。下一步运行全量候选诊断，确认是否有其他单拒因或精确近失配。

## 2026-09-22 13:59：gate-clock 全量辅助诊断超过一小时后有界终止

- 学习目标：为 gate-clock 正式 SVG 对全部合格边排序，判断 mux01 之外是否存在更接近 `FB-ROUTE-023` 的反事实。
- 失败环节与可验证错误：`.reproduction/diagnose_premature_candidates.py` 全量模式从 12:40:36 持续运行超过一小时，子进程 CPU 累计至少 3907.75 秒且无任何输出；达到本轮实用上限后发送 Ctrl-C，进程退出码 1、输出为空。
- 实际影响：仅缺少全边候选排序；gate-clock 的公开 CLI 双跑、SHA、29 指标和独立 Oracle 正式回执均已完整，不受影响，也不改变“尚未复现”的结论。
- 替代方案：利用诊断器已有 `--edge` 预筛，先只枚举 `public_root_a` 且具备候选折线形态的边，逐边有界诊断并汇总；mux01 定向结果已在约 11 秒完成。
- 恢复条件/下一步：若未来必须恢复全量模式，需要在诊断器中缓存 candidate-independent crossing 数据或增加 source/target 预筛与进度输出；当前不再无限等待全量无进度输出。

## 2026-09-22 14:03：逐边预筛证伪 all-gate，转 first-peer 局部形态

- 有界替代方案约 83 秒完成：先列出 9 条合格 `public_root_a` 边，mux01 已定向诊断，其余 8 条逐边 `--edge` 诊断并统一排序。
- gate-clock 没有隐藏单拒因；最佳候选至少同时失败 route/global points。all-gate 虽消除 direct triple 的单重叠，但全局布局扰动过大，方向收敛。
- 下一步扩展同一正式因素为 `first-gate-clock`：只对每行 peer_1 插入 gate，peer_2 保持 direct。该组合直接打断致因 peer_1→clock 纵段，同时只增加 12 个 gate，介于 direct 与 all-gate 之间；不做 row01 特判。

## 2026-09-22 14:05：first-gate-clock 正式域与场景落地，实时日志门成功拦截漏记

- `peer_output_shape` 正式域扩为 direct-clock / first-gate-clock / gate-clock；构造函数新增 peer_index，仅在 first-gate-clock 且 peer_index=1 时插入 gate。新 triple 命名场景其余因素与 direct 近失配完全固定。
- 随后尝试补测试时，PreToolUse hook 因“上一笔项目修改尚未实时写入 worklog/INDEX”拒绝 apply_patch；测试文件未被部分修改。当前先完成本条实时记录与 INDEX 同步，再重试测试补丁。
- 该拦截无交付损失，验证了强制日志机器门实际有效；下一步补 peer1 gated / peer2 direct 结构断言并运行正式结构门。

## 2026-09-22 14:07：first-gate-clock 结构回归断言补齐

- 正式测试新增 first-gate-clock 断言：peer_1 必须生成 gate→clock，peer_2 必须保持 direct-clock 且不得生成 gate；同时保留 direct-clock 与 all-gate 的既有断言。
- 下一步运行生成器编译与该正式结构/pairwise 测试，通过后启动完整 first-gate-clock 双跑。

## 2026-09-22 14:09：first-gate-clock 正式结构门通过

- 生成器编译与目标结构/pairwise pytest 通过（1 passed in 53.82s）；first-gate-clock 第三因素值已纳入完整覆盖闭包。
- 下一步启动完整公开 CLI 双跑、SHA、29 指标和独立 Oracle；保持产品实现冻结，只有精确目标单红才转修复。

## 2026-09-22 15:19：first-gate-clock 正式门全绿未命中

- 命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-first-gate-clock-twelve` 完成两次公开 CLI 渲染；`first.svg` 与 `second.svg` 均为 234342 bytes，SHA-256 均为 `0F7B95BA…C1F97`，确定性成立。
- 时间戳给出的真实阶段耗时：第一轮 14:10:15→14:38:52（约 28:37），第二轮 14:38:52→15:07:52（约 29:00），Oracle/回执至 15:18:58（约 11:06），总计约 68:43。
- 正式回执 schema v2：语义前置条件成立、命名单案覆盖 210/210，29 指标全部通过，`detected_issues=[]`、目标 witness 0、`target_reproduced=false`；`--expect reproduced` 因未命中精确目标契约按设计退出 1，不是工具故障。
- 运行中曾将 CIM 的 100 ns CPU 计数误换算为约 4.17 小时；立即用 `Get-Process.TotalProcessorTime.TotalSeconds` 复核为约 25 分钟，并采样到 10 秒墙钟内增加 10.05 秒 CPU，未据误判中断进程。完整回执证明证据链未受影响。
- 结论：仅 gate peer_1 也会把 direct triple 的目标近失配变为全绿，不能解冻产品修复。下一步先对 mux01 目标边做有界反事实诊断；若仍非单拒因，再枚举 9 条合格 `public_root_a` 边逐边诊断，不恢复超过一小时的全量模式。

## 2026-09-22 15:28：first-gate-clock 有界逐边诊断收敛

- 只读定位脚本第一次沿用旧 `bind_routes(routes, logical)` 调用，因当前 API 需要 `boxes` 参数而以 `TypeError` 退出；按实际签名改为 `bind_routes(routes, boxes, logical)` 后成功定位 mux01 为 `svg-edge-0215`，未修改文件或正式证据。
- mux01 bottom 反事实从路线点 6→8、全局点 196→198，路线/全局事件均持平，且交叉点净增 2；同时失败 route points、global points、strict crossing improvement，不是 direct triple 的单拒因形态。
- 本图共有 10 条合格 `public_root_a` 边。批量摘要器第一次因 PowerShell `foreach` 后直接管道触发 `An empty pipe element is not allowed`，在任何子诊断启动前退出；改为数组收集后，剩余 9 条逐边诊断约 168 秒完整结束。
- 全部 10 条边均无精确命中或隐藏单拒因；最接近的 top 候选仍至少同时失败 same-net cycle、route points、global points，bottom 候选通常失败更多。first-gate-clock 方向关闭。
- 下一步增加正式 `second-gate-clock` 因素值：只 gate peer_2、保留原致因 peer_1 direct，区分“任意局部 gate 引发整体重排”与“必须直接切断 peer_1 纵段”；先补结构断言和 pairwise 闭包，再决定是否承担完整双跑。

## 2026-09-22 15:30：second-gate-clock 正式因素与结构断言落地

- `peer_output_shape` 正式域扩为 direct / first-gate / second-gate / all-gate；统一构造函数仅在 second-gate 且 `peer_index == 2` 时插入 gate，没有 row01 或目标边特判。
- 新增 triple second-gate-clock 命名场景，其他因素与 direct triple 单拒因基线完全相同；测试同时断言 peer_1 保持 direct、peer_2 必须 gate→clock。
- 下一步执行生成器编译、目标结构测试与 pairwise 完整闭包；通过前不启动小时级正式双跑。

## 2026-09-22 15:32：second-gate-clock 结构与 pairwise 门通过

- 生成器 `py_compile` 通过；目标结构/pairwise pytest 通过（1 passed, 86 deselected in 52.11s）。
- peer_1 direct、peer_2 gate→clock 的对称结构已被正式断言，扩展后的四值因素域覆盖集合与 required units 完全相等。
- 下一步启动完整公开 CLI 双跑、SHA 一致性、29 指标与独立 Oracle；只有精确目标单红才允许修改产品 owner。

## 2026-09-22 16:04：second-gate-clock 正式门全绿，进入定向诊断

- 既有后台任务正常完成，三个已登记 PID 均已退出；没有重启、终止或覆盖运行中的任务。`input.json`、`first.svg`、`second.svg` 与正式收据完整存在。
- 两次公开 CLI SVG 均为 234432 bytes，SHA-256 均为 `EBCB0D9C…6342E`；文件时间为 15:33:07 输入、15:43:19 第一轮、15:53:32 第二轮、16:02:58 Oracle/收据，阶段约 10:12 + 10:13 + 9:26，总计约 29:51。
- 正式 schema v2 收据满足语义前置条件与 210/210 coverage exact-set，29 项指标全部通过；`failed_metric_ids=[]`、`detected_issues=[]`、`target_witnesses=[]`、`target_reproduced=false`。`--expect reproduced` 的非零结果表示精确目标合同未满足，不是 CLI、依赖或 Oracle 故障。
- 该结果证明仅 gate peer_2 也会引发整体重排；它不构成自然红灯，`src/elk_layout.py` 继续冻结。下一步定位 `public_root_a→reconvergent_mux_01` 的 SVG edge ID，只运行该边的反事实诊断；若没有精确或单拒因，再逐条检查其余合格 `public_root_a` 边。

## 2026-09-22 16:09：second-gate-clock 逐边诊断收敛

- `public_root_a→reconvergent_mux_01` 绑定为 `svg-edge-0055`，当前路线仅 2 个点，定向诊断按“至少 6 点且至少两条异轴纵段”的语义前置条件返回 `eligible_route_count=0`；原 direct triple 的 mux01 近失配在本布局中已不再存在。
- 只读枚举得到 7 条合格 `public_root_a` 边。逐边 `--edge` 共检查 14 个 top/bottom 反事实，约 86 秒完整结束；没有启动无筛选全量诊断，也没有进程、依赖或工具错误。
- 14 个候选均至少失败 4 项。最接近的是 `svg-edge-0288 public_root_a→reconvergent_mux_11 top`：路线交叉点 6→7、事件 22→19、重叠 0→3，全局交叉点 185→186、事件 1161→1158；同时失败路线点、路线重叠、全局点和全局重叠非增。
- first/second/all-gate 与 direct 已覆盖两个 peer 的四种 gate 组合；三个 gate 方向都让原单重叠近失配转为不同的整体布局，peer 输出形态轴关闭。下一步审计现有生成因素和剩余结构缺口，选择能保留 direct triple 点/事件改善、同时移动 peer_1 纵段的通用公开拓扑因素。

## 2026-09-22 16:12：peer clock 扇出正式因素落地

- 新增 `peer_clock_fanout = single / first-double / second-double / both-double`。额外 clock 与原 clock 共享 peer 输出或 gate 后输出，不增加中间层；统一用于普通 complex row 与 external row，没有目标行、实例名或 edge ID 分支。
- 新命名场景在 direct triple 单重叠基线上只把 peer_1 改为双 direct clock，保留 peer_2 单 clock、双公共根直入、12 行 triple peer 与其余近失配因素。
- 正式结构测试新增 peer_1 extra clock 的 source 断言、peer_2 无 extra clock 的反例，并继续以完整 pairwise exact-set 检查四值因素域。下一步先运行编译与结构门；通过后才启动公开 CLI 双跑和独立 Oracle。

## 2026-09-22 16:15：peer clock 扇出结构门通过

- 生成器与目标测试文件 `py_compile` 通过；`test_dual_public_root_generator_models_repeated_direct_reconvergence` 通过（1 passed, 86 deselected in 65.38s）。
- first-double 的 peer_1 extra clock、peer_2 单 clock 结构断言成立；新增四值因素后的 pairwise coverage 集合与 required units 完全相等。五件套检查 PASS，`src/elk_layout.py` 仍无 diff。
- 下一步启动命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-first-double-clock-twelve` 的完整公开 CLI 双跑、SHA 一致性、29 指标和独立 Oracle。

## 2026-09-22 16:58：first-double 正式任务运行中

- 正式命令已于 16:16:08 启动，统一 exec session 为 `72905`；根 PowerShell PID `24068`、包装 Python PID `34228`、实际 runner PID `32392`、首轮公开 CLI PID `23796`、实际分析 Python PID `12656`。
- `case-000/input.json` 已生成，22796 bytes，时间 16:16:08；截至 16:58 首轮仍在运行，尚未生成 `first.svg`。实际分析进程持续响应，CPU 从约 212 秒增长到 2282 秒以上，没有错误输出或失活证据。
- first-double 比 direct triple 增加 12 个公开 clock 扇出，搜索耗时超过历史约 34 分钟基线不单独构成失败。不要重启、终止或并行重复该场景；继续轮询 session `72905`、上述 PID 与同目录正式收据。

## 2026-09-22 17:35：first-double 首轮完成并进入第二轮

- `first.svg` 于 17:31:28 完整生成，241311 bytes；相对 16:16:08 输入时间，首轮约 75:20。原实际分析 PID `12656` 在完成前持续响应并累计约 4435 秒以上 CPU，没有超时或错误。
- runner 自动进入第二次公开 CLI 渲染：wrapper PID `28604`、实际分析 PID `26920`，命令明确写向同一 case 的 `second.svg`；17:35 采样 CPU 约 244.5 秒并增长。
- 保持 session `72905` 与 runner PID `32392`，不要重启或并行重复。第二轮完成后必须比较两份 SHA-256，再等待独立 Oracle 与正式收据。

## 2026-09-22 18:55：first-double 正式门全绿但未触发目标

- 两份公开 CLI SVG 均为 241311 bytes，SHA-256 均为 `3BC6D5D1…A6D2B`，确定性成立。阶段时间为 16:16:08→17:31:28（约 75:20）、17:31:28→18:44:55（约 73:27）、Oracle/收据至 18:54:28（约 9:33），总计约 2:38:20。
- 正式 schema v2 收据满足语义前置条件与 231/231 coverage exact-set；29 项指标全部通过，`failed_metric_ids=[]`、`detected_issues=[]`、`target_witnesses=[]`、`target_reproduced=false`。`--expect reproduced` 的 gate failed 是精确合同未满足，不是 CLI、Oracle、依赖或服务故障。
- 给每行 peer_1 增加第二个 direct clock 没有自然产生 `premature_interior_trunk_entry`，`src/elk_layout.py` 继续冻结。下一步只读定位 `public_root_a→reconvergent_mux_01`；若不是精确或单拒因，再枚举合格 `public_root_a` 边逐边诊断，量化扇出是否保留 direct triple 的近失配。

## 2026-09-22 19:05：first-double 有界逐边诊断收敛

- 目标 `public_root_a→reconvergent_mux_01` 绑定为 `svg-edge-0201`。bottom 反事实路线交叉点 5→8、事件 69→69，全局点 252→255、事件 4487→4487，同时失败路线点、全局点和严格交叉改善；原 direct triple 的单重叠形态已消失。
- 本图共有 15 条合格 `public_root_a` 边。目标边约 19 秒完成，其余 14 条逐边 `--edge` 约 5 分钟完成；没有启动无筛选全量诊断，也没有子进程或依赖失败。
- 所有候选至少失败 2 项。最佳一组 bottom 候选同时失败 same-net cycle 与 global points；其中 `svg-edge-0193→reconvergent_mux_10_peer_2` 路线点 62→13、事件 214→76，全局点 252→259、事件 4487→4349，诊断器列出 1 条单边 cycle breaker，但全局点仍增加 7。
- first-double 提高了全局交叉密度并把单重叠近失配改为同网环与全局点双拒因，不继续增加 peer_1 扇出。下一步测试同一正式因素的对称 `second-double`：保留致因 peer_1 单 clock，只扰动 peer_2 输出通道；仍须完整双跑与独立 Oracle 才能解冻产品 owner。

## 2026-09-22 19:05：second-double 命名场景与结构断言落地

- 新命名场景沿用 direct triple 单重叠基线，仅设置既有正式因素 `peer_clock_fanout=second-double`；peer_1 保持单 direct clock，peer_2 增加第二个 direct clock，没有新增生成语法。
- 结构测试同时断言 peer_1 无 extra clock、peer_2 extra clock 直接连接对应 reconvergent peer，并继续执行四值因素完整 pairwise exact-set。
- 下一步运行编译、目标结构测试和五件套检查；全部通过后启动完整 second-double 公开 CLI 双跑与独立 Oracle。

## 2026-09-22 19:08：second-double 结构门通过

- 生成器与目标测试文件 `py_compile` 通过；目标结构/pairwise pytest 通过（1 passed, 86 deselected in 64.46s）。
- second-double 的 peer_1 单 clock、peer_2 extra clock 断言成立；四值 `peer_clock_fanout` 因素的 coverage 集合与 required units 完全相等。五件套检查 PASS，`src/elk_layout.py` 仍无 diff。
- 下一步启动命名场景 `dual-public-repeated-direct-port-swap-staggered-branch-port-swap-triple-second-double-clock-twelve` 的完整公开 CLI 双跑、SHA 一致性、29 指标和独立 Oracle。

## 2026-09-22 19:12：second-double 正式任务运行中

- 正式命令已于 19:08:49 启动，统一 exec session 为 `33747`；根 PowerShell PID `25184`、包装 Python PID `27156`、实际 runner PID `39664`、首轮公开 CLI wrapper PID `37716`、实际分析 Python PID `39924`。
- `case-000/input.json` 已于 19:08:50 生成，22796 bytes；19:11 采样时进程链完整、首轮仍在计算且尚未生成 `first.svg`，没有错误输出或失活证据。
- first-double 同规模首轮约 75 分钟，当前静默不构成失败。保留 session `33747`，不要重启、终止或并行重复；首轮完成后记录文件大小、时间和第二轮 PID，再比较双 SHA 并等待独立 Oracle 收据。

## 2026-09-22 19:23：second-double 首轮完成并进入第二轮

- `first.svg` 于 19:22:30 完整生成，234880 bytes；相对 19:08:50 输入时间，首轮约 13:40。首轮实际分析 PID `39924` 在完成前持续响应并增长 CPU，没有错误或超时。
- runner 已自动进入第二次公开 CLI 渲染：wrapper PID `2268`、实际分析 PID `25176`，创建于 19:22:30，命令明确写向同一 case 的 `second.svg`。
- 保持 session `33747` 与 runner PID `39664`，不要重启或并行重复。第二轮完成后比较两份 SHA-256，再等待独立 Oracle 与正式收据。

## 2026-09-22 19:37：second-double 双跑确定性门通过，Oracle 运行中

- `second.svg` 于 19:35:43 完整生成，234880 bytes；第二轮相对 19:22:30 启动约 13:14。
- 两份 SVG 的 SHA-256 均为 `BB08F1B7AACCDECF685C0D045DC23BA0731CA9A1799A919EB91C804B48C9DF95`，双跑确定性成立。
- 两个渲染子进程均已正常退出，runner PID `39664` 仍存活并进入独立最终 SVG Oracle/收据阶段。继续轮询 session `33747`，正式收据前不解冻产品 owner。

## 2026-09-22 19:51：用户规模与一分钟生成预算纳入复现约束

- 用户明确实际输入不会很大，单次生成不应超过 1 分钟。对 `.reproduction/receipts/**/input.json` 只读统计组件数、source 叶连接数、JSON 字节数及 `input→first.svg` / `first→second.svg` 文件时间。
- 现有 12 行 triple 族为 187–211 个组件、327–351 条连接、21.6–23.8 KB，单次生成约 10:12 至 75:20；它们虽可用于压力探索，但不再代表用户规模，也不应继续作为后续正式自然复现方向。
- 最小的已知超一分钟案例已降到 102 个组件、164 条连接、约 11.0 KB（约 89–91 秒）；139 个组件、207 条连接的多个 12 行案例约 60–83 秒。后续新增候选必须先做单次公开 CLI 预检并硬性要求 `<=60s`，否则不得承担正式双跑。
- 当前 second-double 两次生成已在用户补充约束前完成，独立 Oracle 只读阶段仍运行，保留以闭合既有证据；其收据无论结果如何，都不能覆盖新的用户规模/性能约束。后续从小型既有案例或缩减行数构造自然复现，不再启动新的大规模 triple 场景。

## 2026-09-22 19:54：second-double 正式收据关闭大场景方向

- 正式收据于 19:51:10 落盘，Oracle 阶段约 15:26；两张 234880-byte SVG 的 SHA-256 均为 `BB08F1B7…C9DF95`，231/231 coverage exact-set 与语义前置条件成立。
- 唯一失败指标是 `crossing_treatment`，不是目标 `premature_interior_trunk_entry`；`detected_issues=[]`、`target_witnesses=[]`、`target_reproduced=false`。因此该场景不满足精确单红合同，产品 owner 继续冻结。
- 结合用户补充的实际规模/一分钟预算，second-double 与整个 12 行 triple 压力方向正式关闭。下一步先从已有 `<=60s` 输入中筛选同时具备双公共根、重复 direct、跨行纵向结构的最小语义候选，再按缩减行数做单次公开 CLI 预检；任何超过 60 秒的候选立即淘汰，不进入双跑。

## 2026-09-22 20:04：4 行一分钟内候选出现精确单拒因近失配

- 从已有正式收据筛选出 `dual-public-pairwise-case-28`：4 行、7711-byte 输入，63 个逻辑组件、111 条边；两次公开 CLI 各约 45.7 秒，语义前置条件成立且 29 指标全绿，符合用户新增的一分钟生成预算。
- 该案例同时具备 repeated-direct、triple consumers、interleaved-public 与端口 `a-0-b-1`。独立 Oracle 完整报告约 15.87 秒，确认 22 条 `public_root_a` 出边和 96 个全局交叉点，不是因图过小而缺少跨行结构。
- 新增 `work/diagnose_premature_candidates.py` 作为只读解释器：复用独立 Oracle 的公开 SVG 解析/几何函数，逐候选列出 eligibility 与每个严格合同检查，不修改生产布局或正式质量判定。
- 20 条合格根边、40 个 top/bottom 反事实中有三项单拒因近失配。最佳 `svg-edge-0063 public_root_a→reconvergent_mux_03_peer_2 top` 仅失败 `same_net_acyclic`；路线事件 9→5、全局事件 551→547，路线/全局点数与重叠均不增。另两项只失败 strict crossing improvement，但没有任何几何改善。
- 下一步以 case-28 为基线，仅把通用 `direct_entry_pattern` 从 all 改为 `top-main-omit-b`，目标是移除同网闭环而保留事件改善；先补命名场景与结构断言，再做一次公开 CLI 预检，必须 `<=60s` 才允许双跑。首次场景补丁因本条记录尚未同步被 worklog 硬门完整拒绝，无部分修改。

## 2026-09-22 20:06：4 行 staggered 单因素场景与结构合同落地

- 新增命名场景 `dual-public-small-staggered-triple-four`，完整继承 pairwise case-28 的 4 行 triple/serial-remerge/row-band/interleaved-public 结构，只把 `direct_entry_pattern` 从 all 改为 `top-main-omit-b`；未增加新的因素语法或目标行特判。
- 结构测试断言 row 00 的主 reconvergent mux 不再直入 `public_root_b`、row 01 仍同时直入两公共根、row 03 的两个 peer 保留，且正式语义前置条件成立。
- 下一步执行生成器/诊断脚本编译、目标结构/pairwise exact-set 测试与五件套门；全部通过后只做一次公开 CLI 性能预检，不先启动双跑。

## 2026-09-22 20:08：4 行 staggered 结构门通过

- 生成器、只读诊断脚本与测试文件 `py_compile` 通过；目标结构/pairwise exact-set pytest 通过（1 passed, 86 deselected in 74.66s）。测试耗时来自组合闭包计算，不是 SVG 生成时间。
- 五件套检查 PASS，`src/elk_layout.py` 仍无 diff。下一步只生成该命名场景的公开 JSON，并执行一次公开 CLI；用墙钟硬门验证单次 `<=60s`，超时即停止且不进入双跑。

## 2026-09-22 20:11：首次一分钟预检在注释放置阶段可验证失败

- 生成的命名场景输入为 7682 bytes。第一次使用 60 秒 `Start-Process` 硬门，进程在 47.523 秒自行退出、exit 1、无 SVG；该包装未捕获 stderr，因此没有把它误判为通过。
- 用 `ProcessStartInfo.ArgumentList`、stdout/stderr 捕获和同一 60 秒进程树硬门有界重试一次；47.755 秒自行退出，stderr 精确为 `annotation placement has no collision-free candidate: mux_03`，仍无 SVG。
- 失败发生在 case-28 原有 `annotation_pressure=row-band` 与新增 staggered 直入形态组合，不是网络、依赖、权限或超时问题。它不产生可供布局 Oracle 判定的用户制品，因此本候选形态不能进入双跑。
- 注释压力不是用户报告症状的必要结构。下一步把该小型场景的通用 `annotation_pressure` 改为 `none`，保留 4 行、triple、interleaved-public、serial-remerge 与 staggered 主结构；结构门后再次执行一次 60 秒公开 CLI 预检。

## 2026-09-22 20:12：小型场景移除非必要注释压力

- 命名场景仅将 `annotation_pressure` 从 row-band 改为 none；4 行、双公共根、repeated-direct、staggered、triple、serial-remerge、interleaved-public 和端口交换均保持不变。
- 结构测试增加 none 断言，防止后续重新引入已验证不可放置的注释压力。下一步重跑编译/结构/五件套门，再重新生成 JSON 并执行一次 60 秒公开 CLI 预检。

## 2026-09-22 20:14：无注释压力结构门通过

- 生成器与测试文件 `py_compile` 通过；目标结构/pairwise exact-set pytest 通过（1 passed, 86 deselected in 63.74s）；五件套检查 PASS。
- 产品 owner 仍无 diff。下一步覆盖预检目录中的生成式 input.json，并以捕获 stderr 的 60 秒进程树硬门执行一次公开 CLI。

## 2026-09-22 20:17：4 行一分钟内预检精确命中目标单红

- 无注释压力输入为 7302 bytes；公开 CLI 在 47.299 秒成功生成 70983-byte SVG，SHA-256 `740172F0…8AB259`，满足用户单次不超过一分钟约束。
- 独立 Oracle 与 29 指标约 48.25 秒完成。唯一失败指标精确为 `premature_interior_trunk_entry`，`detected_issues=["FB-ROUTE-023"]`，且目标 witness 非空。
- witness 为 `svg-edge-0088 public_root_a→reconvergent_mux_01`：公共根主干在 y=1893.3429 过早离开，优选离开 y=2245.3324；反事实使全局交叉点 98→96、全局事件 814→813、局部事件 32→31，折点保持 4，并列出四个跨越目标行坐标。
- 该结果只是一轮公开 CLI 预检，尚不满足正式双 SHA 与 schema v2 收据，因此 `src/elk_layout.py` 继续冻结。下一步对同一命名场景运行正式双跑；每一轮仍须独立小于 60 秒，随后验证 exact-set、语义前置、精确单红、非空 witness、target_reproduced 与 SHA 一致。

## 2026-09-22 20:21：4 行正式自然复现合同成立，产品 owner 解冻

- 正式首轮约 46.997 秒、第二轮约 46.955 秒，均小于一分钟；两张 SVG 均为 70983 bytes，SHA-256 均为 `740172F06F082F75F23690E796908DD9DCE8DBECDCC8062BD03DCD1C138AB259`。
- schema v2 收据覆盖 231/231 exact-set、missing 0、语义前置条件 true；`failed_metric_ids=["premature_interior_trunk_entry"]`、`detected_issues=["FB-ROUTE-023"]`、witness count 1、`target_reproduced=true`，且 `unexpected_quality_failure_cases=[]`。
- 正式 witness 与预检一致：`svg-edge-0088 public_root_a→reconvergent_mux_01`，过早离开 y=1893.3429，优选离开 y=2245.3324，全局点 98→96、全局事件 814→813、局部事件 32→31、折点 4→4。
- 正式证据路径为 `.reproduction/receipts/dual-public-small-staggered-triple-four/coverage-receipt.json`。至此首次满足全部解冻条件，允许定位并修改 `src/elk_layout.py` 的最早责任点；下一步先做源码责任链审计，不先试探性改写。

## 2026-09-22 20:27：最终 corridor owner 拦截分类

- 对同一 7302-byte 正式输入直接读取 `generate_elk_layout(..., include_statistics=True)` 的内部回执；本次布局耗时 47.132 秒，仍在用户一分钟预算内。
- 早期 boundary corridor 共尝试 1417 个候选、接受 7 次、移除 32 个 crossing events；最终 serialized boundary corridor 尝试 168 个候选但接受 0 次。
- 最终 pass 的拦截计数为 `logical-fanout-cycle=145`、`crossing=22`、`different-net-overlap=1`；这证明 owner 已枚举大量 corridor 候选，但尚需对具体 witness 做精确差分。
- 独立最终 SVG Oracle 对具体 `svg-edge-0088` 反事实已执行同网无环检查并通过。下一步在不改生产策略前，对该边的精确 logical index、候选坐标和两个 cycle 实现作差分诊断，确认是精度/切点语义不对称还是候选与 Oracle 不同。

## 2026-09-22 20:32：目标反事实不被 cycle 门拒绝

- 新增只读诊断 `work/diagnose_cycle_gate_difference.py`，它在完整公开输入布局后只复制几何，把正式 witness 坐标施加到唯一 `public_root_a→reconvergent_mux_01.1` 逻辑边，不修改产品源码或正式收据。
- 该边是逻辑 `e69`；原路径与正式 SVG witness 坐标完全一致。将离开 y 从 1893.3429 延后到 2245.3324 后，生产 `_logical_fanout_cycle_count` 为 0→0，独立 SVG `_same_net_cycle` 也为 false。
- 因此上一条中 145 个 cycle blocker 不能归因于这一目标候选；两个 cycle 实现在此反事实上一致。初版诊断误用 logical index 推导 SVG index，而 serializer 会重排路径；下一版改为按绑定后的 source/target/port 查找，并列出该反事实的全部生产安全门。
- 本条记录前尝试更新诊断脚本被 worklog 硬门完整拒绝，无部分修改；现已先同步记录与索引。

## 2026-09-22 20:35：诊断端口名规范化差异

- 全门诊断第一次在渲染后 witness 查找处以 `StopIteration` 退出；布局本身已成功，故障只在诊断脚本最后的身份匹配。
- 可验证原因：生产 `LogicalEdge.target_port` 为 `in1`，独立 SVG Oracle 公开 topology 规范化后为 `1`；source/target/source_port 均一致，候选 SVG 中唯一目标边是 `svg-edge-0087`。
- 修正诊断为按唯一 source/target 绑定，不把两个层的端口内部命名直接等同。该失败不影响已计算的生产门数据，但尚未打印，需有界重跑一次。

## 2026-09-22 20:38：最早责任点确认为 outward-lane 语义门

- 规范化后诊断在 48.793 秒布局上完整输出：正式 witness 反事实通过生产的 logical-fanout-cycle、node-overlap、edge-node、visible-overlap、visible-edge-node、endpoint、direction、different-net-overlap、bend 和 crossing 全部十个门。
- 生产评分与独立 Oracle 完全一致：distinct points 98→96、events 814→813、bends 226→226；候选最终 SVG 同网无环。因此不是交易门误拒，而是候选在交易前未被枚举。
- 源码责任点是 `_route_root_branches_through_boundary_corridors` 中 `outward_lane_values` 的开启条件：它用所有组件可视框中心当作“跨越行”，而目标语义是同一 root-port 网的 consumer 目标轴。本反例的远端纵段跨越 4 个 sibling target rows，却不满足“两个可视框中心”，使已存在的 sibling lane y=2245.3324 被排除。
- 最小修复将这一开启统计改为当前 `(logical.source, logical.source_port)` 的 sibling 终点 y；候选坐标、局部筛选、十个全图安全门和全局选优全部保持不变。

## 2026-09-22 20:43：首次候选语义修正未闭合目标

- `src/elk_layout.py` 已把 outward-lane 的 crossed-row 来源从所有可视框中心改为同一 root-port 网的 sibling 终点轴，未改任何安全门。`py_compile` 通过，修正后公开 CLI 约 42.3 秒生成 SVG，仍低于一分钟。
- 独立 29 项质量门仍精确只失败 `premature_interior_trunk_entry`；目标路线坐标未变。因此该修正尚未达标，不得宣称解决。
- 修正后内部统计显示 final serialized boundary 仍是 attempts 164、moves 0，而后续 source-lead 和 single-edge owner 也都 moves 0；排除“已接受后被后续 owner 改回”，候选仍没有进入全图交易。
- 下一步在只读诊断中对目标边复制 exact prefilter：输出 sibling crossed rows、lane 可见性、local overlap/crossing score 和 shortlist 条件，然后只修正真正阻断点。

## 2026-09-22 20:47：exact prefilter 确认缺少全图 route endpoint rows

- 只读 exact prefilter 在 46.346 秒布局上证明 y=2245.33245 已存在于 visibility lanes，水平通道不碰任何非端点组件，local overlap 0→0、crossing points 7→7、events 32→31，因而一旦被枚举就会进入 shortlist 并通过全图门。
- 目标远端纵段之间，同 root-port sibling 终点只有 y=1941.3454 一个；独立 Oracle 的 4 个 crossed rows 来自“全部 route 终点 + 组件中心”可见行，分别为 1910.0114、1938.3429、1941.3454、1945.0186。
- 因此上一次改为“仅 sibling 终点”是过窄假设，已被反例驳回。真正缺口是原生产只统计组件中心，漏掉其他路由的终点行；修正应使用“全部 route endpoints 与组件中心并集”，与最终 SVG 可见语义对齐。
- 下一步替换首次未达标修改，不叠加两套逻辑；仍保留原有候选、shortlist 和全图门。

## 2026-09-22 20:51：最小 owner 修正单跑全指标通过

- 已用“全部 route 终点轴 + 组件中心”并集替换首次过窄的 sibling-only 修改；产品 diff 仍只位于 `_route_root_branches_through_boundary_corridors` 的 crossed-row 语义，未放宽任何质量门。
- `py_compile` 通过；同一 7302-byte 正式输入通过公开 CLI 约 48.7 秒生成，仍小于一分钟。目标 `public_root_a→reconvergent_mux_01` 路线已从 y=1893.3429 延后到 y=2245.3324，与修复前独立 witness 坐标一致。
- 独立 `svg_quality_system.py` 执行完整 29/29 指标并 PASS，`failed=-`；原精确单红已在一次公开生成上闭合，且没有变成其他质量失败。
- 这仍是修复后单跑预检。下一步对同一命名场景运行正式 `--expect clean` 双跑，验证两轮均小于 60 秒、SHA 相等、231/231 exact-set、语义前置 true 和 target witness 清空。

## 2026-09-22 20:55：修复后正式双跑合同通过

- 正式命令 `search_dual_public_bus_coverage.py --scenario dual-public-small-staggered-triple-four --expect clean` 正常退出，收据为 `.reproduction/receipts/dual-public-small-staggered-triple-four-fixed/coverage-receipt.json`。
- 输入 7302 bytes；首轮从 input mtime 到 `first.svg` 约 56.86 秒，第二轮约 56.43 秒，两轮均低于用户的一分钟上限。两张 SVG 均为 70985 bytes，SHA-256 均为 `A28FC307465570A5B214CF647A3324B3E06772A3BC1D41C175092871AEE89A56`。
- schema v2 收据：231/231 exact-set、missing 0、semantic preconditions true、`failed_metric_ids=[]`、`detected_issues=[]`、`target_witnesses=[]`、`target_reproduced=false`、`unexpected_quality_failure_cases=[]`。修复前精确单红与修复后全绿已形成同输入成对证据。
- 下一步把该命名场景加入 current CLI 回归，然后运行目标/相邻测试、五件套、diff 审计和问题账本更新。Windows 旧制品血缘仍是独立 release 阻塞，不会被源码修复收据偷换为已发布。

## 2026-09-22 21:15：持久回归与相邻攻击闭环

- 新增 `test_current_cli_closes_small_staggered_dual_public_trunk`：每次从命名因素重建公开 JSON，调用正式 CLI 生成 SVG，再独立检查 `FB-ROUTE-023` 与 29 项 exact-set。该测试 1 passed、87 deselected，总时间 104.93 秒（含生成与两次独立几何分析）。
- 旧 `premature-interior-trunk-entry` 公开 CLI 回归、干净控制和 6 个错列 mux boundary attacks 共 8/8 通过，80 deselected，用时 824.34 秒。这些是重型相邻压力测试，不代表用户小输入的生成时间。
- 命名场景结构/pairwise exact-set 与目标单红合同测试 2/2 通过，86 deselected，用时 71.46 秒。JSON ledger 解析、相关 Python `py_compile`、`git diff --check` 和五件套检查均通过。
- 问题账本已写入修复前/后成对收据，状态为 `source_fix_verified_release_pending`。本轮算法目标已闭环；仍保留记录 active，因为真实 Windows 发布制品的可验证构建/血缘属于后续独立 release 任务。

## 2026-09-22 21:32：升级为正确性与真实规模性能双硬门

- 用户把后续交付口径升级为非补偿式双目标：历史错误在公开入口、同输入和独立终态 Oracle 下不可复现，既有正常功能及完整指标不得退化；只有这些正确性门全绿后，才允许接受运行时间改善。
- 性能口径按真实用户输入与压力输入分层。当前 7302-byte、63 组件、110 边的最小自然反例属于真实规模验收集，单次生成必须低于 60 秒；12 行、187–211 组件、327–351 边的大图只作为压力和瓶颈证据，不能代表用户 SLA，也不能拖慢日常门禁。
- 当前修复后正式双跑约 56.86/56.43 秒，虽通过一分钟上限但余量不足。下一步先用确定性 profiler 定位真实热点，再只做不改变候选集合、质量顺序和安全门语义的重复计算消除；优化前后使用同一输入、同一公开入口、双 SHA、231/231 exact-set、历史回归和相邻反例签收。
- 机器闭环将为正式 runner 增加可声明的单次渲染预算与逐轮耗时收据；超时、预算超限、产物缺失、双跑哈希不一致、指标集合缺失、目标 witness 残留或历史回归失败均非零退出。压力集保留独立预算，不用放宽用户规模门。
- 自主学习采用渐进披露：用户根 `clock-tree-layout` 承载领域路由，`agent-quality-workflow` 承载正确性优先的性能闭环，`case-generalization` 承载规模/时间分层；项目路径、具体 SHA 和耗时只留本记录。官方资料和 Find Skills 已完成有界检索，候选第三方 Skill 未安装，因为现有本地 owner 更窄且可直接验证。

## 2026-09-22 21:34：有效口径已同步

- 项目 changelog 顶部新增 2026-09-22 三条有效要求：正确性优先、真实规模一分钟门和强制收据闭环；没有改写既有历史决议。
- project-design-notes 的质量检查同步为当前态：公开 CLI 未插桩墙钟负责预算验收，profiler 只负责定位；同输入双跑、完整指标、历史故障和正常反例先于性能评价，压力集与用户 SLA 分离。
- 下一步进入只读剖析；剖析不会授权修改产品 owner，只有热点与等价优化边界明确后才提交最小补丁。

## 2026-09-22 21:40：真实规模热点已定位

- 对同一 7302-byte/63 组件/110 边案例执行一次 `cProfile`，成功生成与当前 70985-byte 结果同尺寸的 SVG；插桩总耗时约 175.3 秒、4.78 亿次调用，只用于热点定位，不作为一分钟预算证据。
- `_route_root_branches_through_boundary_corridors` 两次累计约 166.2 秒；其中 `_logical_fanout_cycle_count` 被调用 1780 次、累计约 89.0 秒。该函数每个候选都重建全部 source-port 网络，即使候选只改一条边，构成已验证的重复全图计算。
- 等价优化边界：候选只改变当前逻辑边所属的 `(source, source_port)` 网络；其它网络在 accepted/candidate 间字节级几何不变。因此“candidate 全图 cycle 数不大于 accepted 全图 cycle 数”等价于只比较受影响网络的 cycle 数。实现将给 cycle counter 增加显式网络过滤，并在两个单边交易 owner 中按受影响网络比较；不改变 cycle 算法、候选集合、评分或任何安全门。
- 同时把 accepted 侧的最终异网重叠与端点签名移到候选循环外复用；这些值在同一 accepted 状态和同一 edge 下不变。候选侧检查仍逐案完整执行。修改后先用作用域/全局差值等价测试校准，再跑同输入公开双跑和全指标回归。

## 2026-09-22 21:40：交付图像与正式目标追加

- 用户要求最终交付复现前与修改后的两张图；只有无法自然复现时才允许只交付正确图。本问题已有同一 7302-byte 输入的稳定自然红灯，因此必须交付修复前 `first.svg` 与修复后 `first.svg`，并在输出目录中使用清晰文件名，不能只给收据路径。
- 已创建正式目标，范围同时包含：历史问题不可复现、正常功能不退化、真实规模单次小于 60 秒并继续提速、强制机器门、用户根 Skill 渐进披露、同输入前后 SVG 与完整证据。
- 首次性能补丁调用因 `apply_patch` 不接受同一文件在一个补丁中的多个独立操作而在校验阶段整体拒绝，`src/elk_layout.py` 未产生任何部分修改。下一次将同一文件变更合并为单一更新块，不改变已审定优化边界。

## 2026-09-22 21:41：cycle 计数器增加显式网络作用域

- `_logical_fanout_cycle_count` 新增可选 `source_nets` 过滤；省略时仍遍历全部网络，保持所有既有调用的语义。指定时只跳过不在 exact-set 中的网络，受选网络的序列化、切段、交叉、union-find 和 cycle 判定代码完全复用。
- 这一步只提供等价计算能力，两个候选 owner 尚未切换到作用域调用；下一笔将逐 owner 替换并在替换后立即做全局/作用域差值测试。

## 2026-09-22 21:42：外侧 detour owner 切换为受影响网络比较

- `_restore_root_outer_detours` 不再为每个单边候选重算全部 source-port 网络；它在当前 edge 的 lane 搜索前计算该 edge 所属网络的 accepted cycle 值，并让每个 candidate 只计算同一网络。
- 该 owner 一次只改当前 edge waypoints，其余网络不变，故 scoped candidate/accepted 比较与原全图差值比较等价；接受条件名称与方向保持 `candidate <= accepted`，没有放宽门。
- 下一笔对耗时占比最高的 boundary corridor owner 做同样替换，并复用 accepted 侧不变量。

## 2026-09-22 21:44：boundary corridor 优化单跑保持字节一致

- boundary corridor 已切换为当前 `(source, source_port)` 网络的 cycle 比较；accepted 全图最终异网重叠按 while 状态计算一次，accepted 当前 edge 的端点签名按 edge 计算一次，candidate 侧仍逐案完整执行。
- `py_compile` 通过；同一正式输入经未插桩公开 CLI 在 42.691 秒完成，较修复后正式基线 56.86/56.43 秒缩短约 13.7 秒（约 24%），明显扩大一分钟余量。
- 新 SVG 为 70985 bytes，SHA-256 仍为 `A28FC307465570A5B214CF647A3324B3E06772A3BC1D41C175092871AEE89A56`，与优化前正确 SVG 字节级一致。这证明该案例的布局、候选选择、序列化和可见结果均未改变；仍需正式双跑、完整 Oracle 和相邻回归。
- 下一步把墙钟预算写入正式 coverage runner 和 receipt，使两轮各自超限都非零失败；之后再运行正式双跑，而不是依赖人工读时间戳。

## 2026-09-22 21:47：正式 runner 增加逐轮墙钟门

- `search_dual_public_bus_coverage.py` 新增 `--max-render-seconds`；每次公开 CLI 调用使用同一值作 subprocess 硬超时，并记录状态、墙钟秒数、预算、退出码、产物存在性和失败 stderr 尾部。
- 每个 case 在 Oracle 前先写 `render-receipt.json`。首轮失败不启动第二轮；任一轮超时、CLI 非零、缺产物或完成后超预算均抛出失败并阻止质量 clean。成功正式总收据把两轮 render 记录写进 case 行。
- 当前草案把总收据升级为 schema 3，并在函数签名用了 `float | None`；项目声明支持 Python 3.9，下一笔先把该注解改为兼容写法并审计现有消费者是否固定要求 schema 2，再决定保留升级或使用向后兼容的 schema 2 加字段，不能直接运行后才发现兼容问题。

## 2026-09-22 21:49：runner 保持 Python 3.9 与收据兼容

- 只读搜索未发现 dual-public coverage receipt 的固定 schema 2 消费者，但项目其它终态工具仍明确使用 schema 2；为避免无必要协议迁移，总收据保持 schema 2，仅向 case 行和顶层增加可选耗时字段。
- `_run` 的 `float | None` 已改为无 PEP 604 语法的默认参数，避免破坏 Python 3.9 解析；运行状态结构和预算语义不变。
- 下一步增加快速正反校准：伪造成功 subprocess 验证收据字段，伪造 `TimeoutExpired` 验证 timeout 状态与产物存在性；再运行真实 60 秒双跑。

## 2026-09-22 21:51：墙钟门正反测试已加入

- 新增 runner 单测，用隔离临时目录和替换后的 `subprocess.run` 校准 `_run`，不启动真实布局：成功分支必须把预算原样传给 subprocess、报告 `passed` 和产物存在；超时 mutant 必须报告 `timeout`、无退出码、无产物并保留 stderr 诊断。
- 该测试不会用 sleep 或真实 60 秒等待，适合日常快速门；正式命名场景仍负责真实墙钟、双 SHA 和完整 Oracle。
- 下一笔补 cycle 作用域分解测试，证明全图计数等于各 source-port 网络计数之和，从而锁定 scoped 差值等价关系。

## 2026-09-22 21:53：cycle 网络分解合同已加入

- `test_fanout_cycle_count_decomposes_by_source_port_network` 在双公共根四行阵列上从真实节点、逻辑边和生产布局构造全部 source-port 网络，断言全图 cycle 数严格等于逐网络 cycle 数之和。
- 该断言直接锁定本次优化依赖的可加性：单边候选只改变一个网络时，candidate 与 accepted 的全局差值等于该网络的 scoped 差值；若过滤错误漏算或重复分组，测试会失败。
- 下一步执行语法、两个新单测、双公共根正常结构测试和五件套；通过后运行带 `--max-render-seconds 60` 的正式同输入双跑。

## 2026-09-22 21:54：优化与预算聚焦门通过

- `elk_layout.py`、coverage runner 和两份测试文件均通过 `py_compile`。
- 双公共根正常结构、cycle 网络分解、runner 成功/超时 mutant 三项测试全部通过（3 passed in 0.67s）；不是只测新增函数，也保留既有双总线正常行为。
- 项目五件套 PASS，记录、索引、预加载与必需文件无缺失或断链。下一步运行正式命名场景：同一输入公开 CLI 双跑，每轮由 runner 硬限制 60 秒，随后执行完整 29 指标与 231 coverage units。

## 2026-09-22 21:57：正式 60 秒双跑与完整 Oracle 通过

- 正式命令带 `--max-render-seconds 60` 正常退出；收据为 `.reproduction/receipts/dual-public-small-staggered-triple-four-performance-gated/coverage-receipt.json`，schema 2 保持兼容并新增顶层预算与逐轮 render 记录。
- 两轮公开 CLI 分别为 42.817099 秒和 44.180046 秒，状态均为 `passed`，相较此前 56.86/56.43 秒分别缩短约 24.7% 和 21.7%，且各自距离一分钟还有 15.8–17.2 秒余量。
- 两张 SVG 均为 SHA-256 `A28FC307465570A5B214CF647A3324B3E06772A3BC1D41C175092871AEE89A56`，与优化前正确 SVG 完全一致；231/231 coverage units、missing 0、语义前置 true、29 指标无失败、无意外失败、无目标 witness、`target_reproduced=false`。
- 下一步运行历史红灯、正常控制、6 个相邻 mux boundary attacks 与当前具名回归；随后才更新用户根 Skills 和交付图像副本。

## 2026-09-22 22:11：历史与相邻重型回归全绿

- 同一受控 pytest 进程完成 9 个测试节点，`9 passed in 827.49s`：旧 `premature-interior-trunk-entry` 公开 CLI 回归、当前小型具名回归、干净控制和 6 个错列 mux boundary attacks 全部通过。
- 该组逐案真实生成 SVG 并执行独立终态分析，验证 scoped cycle 计算没有改变历史故障修复、正常功能或相邻列/端口/顺序组合；耗时属于测试生成与多轮 Oracle，不代表单次用户生成。
- 聚焦证据现为：快速语法/正反/分解 3/3、正式双跑 42.82/44.18 秒且 231/231×29 全绿、历史及相邻 9/9。下一步完成用户根 Skill 渐进披露、Skill 验证、项目全量测试和交付前后两张 SVG。

## 2026-09-22 22:18：用户根 Skill 渐进披露完成

- `clock-tree-layout` 根新增运行预算路由，详细 reference 覆盖布局规模分层、profile 定位、受影响网络等价缩域、双跑墙钟收据和前后图交付；`agent-quality-workflow` 根路由到正确性/用户延迟/验证成本三合同；`case-generalization` 根路由到规模与时间边界搜索。
- 三份新 reference 均一层可达，不含项目路径、用户名、项目哈希、具体项目名或一次性秒数；根文件只保留触发条件，没有复制正文。官方 `quick_validate.py` 对三项均输出 `Skill is valid!`，定向路由/存在/敏感 token 检查通过。
- Skill 校验第一次误用不存在的用户目录 venv，三项均未执行；第二次使用项目 venv到达脚本但因缺 `PyYAML` 报 `ModuleNotFoundError: yaml`。替代为本机已有 PyYAML 6.0.2 的 Python 后三项通过，未安装或改动项目依赖。
- 全目录隐私审计：`case-generalization` 通过；clock skill 因既有下载 HTML 的 parent-path 字符串与 4 个 PDF unknown 失败，quality skill 因既有测试邮箱与 9 个 `__pycache__` unknown 失败。审计器要求目录、不支持只审新文件；因此新增文件采用定向零命中检查，实际交付不受影响，但不能宣称两个既有目录全量隐私审计已绿。
- Find Skills 三组查询与 Python/pytest/xdist/NIST 官方资料检索均成功；候选第三方 Skill 未安装，因为现有本地 owner 已覆盖且安装会增加重复规则。下一步运行项目全量 pytest，任何失败都回到最早 owner 修复后重跑。

## 2026-09-22 22:46：全量门正确拒绝陈旧血缘

- 串行全量 pytest 运行到约 54% 时已出现 3 个失败；为避免继续消耗重型布局时间而不处理首错，主动中断后用聚焦文件重跑获得完整堆栈。中断轮不计全量结果。
- `tests/test_feedback_reproduction_gate.py` 聚焦结果为 3 failed、21 passed。第一项明确报告 `FB-ROOT-001: fix receipt source tree is stale` 和 runner/oracle lineage stale；另外两项由发布门拒绝仍为 `source_fix_verified_release_pending` 的 `FB-LINEAGE-024`。这不是产品布局回归，而是当前源码/runner 变化使旧签收据失效，且 Windows 实际制品血缘尚未闭合。
- 不修改 checker、不删测试、不伪造 closed。下一步按项目已有恢复路径：为最终源码重签全部 fix verification 与递归攻击；在 Windows 本机从当前工作树构建候选 EXE/ZIP，写入源码树身份和制品哈希，对同一小型正式输入执行 frozen CLI 双跑、60 秒预算、双 SHA 和独立 29 指标，再把 024 推进到有证据支持的状态。
- 若 PyInstaller/依赖不可用，保留精确错误并披露；不会以源码 CLI 结果替代 Windows 可执行制品结果。所有证据更新后从头重跑全量门。

## 2026-09-22 22:50：当前工作树 Windows 候选构建成功

- 本机 `.venv` 已有 PyInstaller 6.22.3；没有运行会先清空 `build/` 与 `dist/` 的 `tools/pack.bat`，而是用同一 `drawclock.spec` 在 `work/windows-candidate/{build,dist}` 隔离构建，保护用户既有发行物。
- PyInstaller 在约 8.7 秒成功生成 `work/windows-candidate/dist/drawclock.exe`，Python 3.11.9、Windows x64；构建退出码 0，无下载、登录或网络依赖。
- 下一步以该 EXE 对同一 7302-byte 正式输入执行两次真实 Windows 公开 CLI，每轮 60 秒进程硬门；随后对原始 SVG 执行独立 29 指标和目标 witness 检查，再生成绑定工作树源码哈希、EXE 哈希、输入/双 SVG 哈希与命令的 lineage manifest/receipt。

## 2026-09-22 22:53：Windows frozen 公开入口双跑通过

- 隔离候选 `drawclock.exe` 对同一 7302-byte 输入运行两次，均由 `.NET Process.WaitForExit(60000)` 做真实 60 秒硬门；两轮退出码均为 0、分别 42.134716 秒和 41.650782 秒。
- 两张 frozen SVG 均为 70985 bytes，SHA-256 均为 `A28FC307465570A5B214CF647A3324B3E06772A3BC1D41C175092871AEE89A56`，与优化前/后源码正确图完全一致；证明 Windows 可执行制品包含当前修复和性能优化，且不是仅源码解释器通过。
- 下一步对 frozen run-1/run-2 分别执行独立完整质量注册表和 FB-ROUTE-023 专项 Oracle；两轮全绿后才写 lineage receipt 并更新 024 状态。

## 2026-09-22 22:56：Windows frozen 两轮独立 Oracle 全绿

- 两张 frozen SVG 分别执行 `svg_quality_system.py`，均为 `PASS metrics=29 failed=-`；required/executed 各 29，失败指标为空。
- 两张 SVG 分别执行只读 `feedback_layout_reproduction_oracle.py --issue FB-ROUTE-023`，均以约定退出码 1 报告 `symptom not observed`，完整报告中 detected issues 为空、目标 witness 数为 0。这里的退出码 1 是专项 Oracle 的“症状未出现”合同，不是工具失败。
- 当前身份：source tree `737c8993…89e36`、library tree `363d0e89…98e32`、Windows EXE `1f558f3c…9fdd3`、输入 `2139fe15…7c28`、双 SVG `a28fc307…a56`。下一步写入机器可读 manifest/receipt，并由现有 lineage verifier 重验 artifact 哈希和工作树身份。

## 2026-09-22 23:00：Windows 血缘从本机证据升级为发行必需门

- 仅在 `work/` 中生成本机候选虽能证明当前 Windows EXE 正确，但不能阻止未来 GitHub Release 再次只发布 Linux。为闭合 `lineage_escape`，将增加通用 frozen runtime budget verifier，并把 Windows build/test/upload 作为 Release workflow 的必要前驱。
- 新 verifier 接收 frozen binary、输入、库、输出目录和单轮预算；双跑真实二进制、写逐轮耗时/退出码/产物哈希，要求双 SHA 一致，并对两张 SVG 执行独立 29 指标和 FB-ROUTE-023 witness 检查。任一超时、缺产物、非确定、指标失败或 witness 残留均非零。
- Windows CI 在 `windows-latest` 隔离构建 ZIP，运行既有 frozen 功能集和新增 60 秒具名回归，上传 ZIP 与 runtime receipt；publish job 同时依赖 Linux/Windows build 并下载两类资产。这样本机证据、CI 构建和发布资产形成同一强制 DAG。
- 下一步先实现 verifier 和工作流，运行本机候选签收及测试；最终源码稳定后再重签全部 fix/recursive receipts，避免证据刚生成又因代码变化失效。

## 2026-09-22 23:04：Windows frozen 运行预算门实跑通过

- 新增 `tools/verify_frozen_runtime_budget.py`：从正式具名场景生成 7302-byte 输入，隔离 PATH 后真实启动 frozen binary 两次，每轮 subprocess 硬超时 60 秒；任一超时、非零退出、缺 SVG、超预算、双 SHA 不同、29 项质量失败或 `premature_interior_trunk_entry` witness 均返回非零并保留机器收据。
- 本机构建的当前 Windows EXE 已通过该门：两轮 41.639596 秒、41.660429 秒，均为 70985 bytes，SHA-256 同为 `a28fc307…a56`，确定性 true，29 项 required/executed 完整且目标 witness 总数 0。
- Release workflow 已新增必需 `build-windows` job：构建并检查 Windows ZIP、运行既有完整 frozen 功能集、执行新增 60 秒真实规模门、上传 ZIP 与 receipt；publish 同时依赖 Linux 与 Windows 并下载两类资产，消除未来只验证 Linux 就发布 Windows 的逃逸路径。
- 下一步为 verifier 补超时 mutant 与 workflow DAG 测试，再更新 024 血缘证据；所有源码和门稳定后重签 fix/recursive receipts。

## 2026-09-22 23:06：运行预算门的反向校准与发行 DAG 已锁定

- `tests/test_release_lineage.py` 新增超时 mutant：替换真实进程为 `TimeoutExpired`，断言 verifier 返回 `timeout`、无退出码、无产物并保留 stderr；新增 workflow 静态合同，断言 Windows job、60 秒命令、上传物和 publish 三前驱同时存在。
- 聚焦文件 5/5 通过；新 verifier 通过 `py_compile`；Release YAML 用 PyYAML 成功解析。门禁不是只会通过当前好样本，也证明了预算越界会稳定拒绝。
- 下一步在正式 `.reproduction/receipts/windows-frozen-runtime` 路径重跑当前 Windows EXE，并用该收据补全 FB-LINEAGE-024；之后重签全部历史 fix 与递归攻击收据。

## 2026-09-22 23:10：Windows 制品血缘事件闭合

- 正式路径 `.reproduction/receipts/windows-frozen-runtime/receipt.json` 已由同一 Windows EXE 从头重跑并签收为 PASS；收据绑定 binary/input SHA、逐轮时限和耗时、双 SVG SHA、29 项 required/executed、失败集合、确定性与目标 witness 计数。
- `FB-LINEAGE-024` 已补全实际 public frozen command、输入、两张 SVG、收据、只读 Oracle 和新 attempt，并在 Windows 制品实跑 + 超时 mutant + Release 必需 DAG 三类证据齐备后从 `source_fix_verified_release_pending` 推进为 `closed`；未用源码 CLI 冒充 EXE，也未放宽 release checker。
- 下一步运行五件套后执行 `run_feedback_fix_verification.py` 重签当前源码树全部历史 fix 收据，再运行递归攻击。重签或攻击任一失败都会保持发布关闭。

## 2026-09-22 23:17：全部历史 fix 重放无失败

- 五件套 PASS；`run_feedback_fix_verification.py` 从当前源码树重放完成，verification group `20260922T151115Z-16999f44`，`failures=[]`。不是仅改哈希：每个绑定 case 的双运行、原始 SVG、生产日志、独立报告与 issue 日志均重新生成。
- 紧接着故意在尚未暂存新证据、尚未刷新递归攻击时运行 release checker，门正确返回非零：递归 source/oracle stale，且逐项列出新 fix evidence 尚未 Git-tracked。262 条大部分是同一新证据批次各文件的洁净 checkout 可达性，不是 262 个布局回归。
- 不放宽 `git ls-files` 检查。下一步生成当前树递归攻击收据，再仅把本轮机器证据纳入索引，随后重新运行 release gate；只有 clean checkout 可达性与新鲜度同时满足才计通过。

## 2026-09-22 23:32：七轮递归攻击从 R1 重启后全绿

- 当前最终源码与 Oracle 上的递归攻击 run `20260922T151801Z-5ba1e2a5` 明确退出：`status=clean`、`consecutive_clean_rounds=7`；覆盖 FB-ROUTE-002、FB-ROOT-003、FB-ROOT-016、FB-BEND-017、FB-ROOT-020、FB-ROUTE-023 和四类必需语义变体。
- 新 fix evidence 为 228 个文件、18,724,720 bytes；新 recursive evidence 为 324 个文件、4,896,123 bytes。两批均由当前运行生成，下一步精确 `git add -f` 这些新批次、对应 fix receipts、recursive receipt 与 Windows frozen receipt，使 release checker 能模拟洁净 checkout 可达性；不批量添加其它历史未跟踪诊断物。
- 暂存只用于机器门验证与交付边界，不提交、不推送、不覆盖用户已有文件；当前索引原先为空，因此不会混合未知既有 staged changes。

## 2026-09-22 23:34：发布反馈门完整通过

- 仅精确纳入本轮 fix evidence、recursive evidence、两类正式 receipt 以及本轮新增/修改的门文件；索引共 582 个路径，主要为上述机器证据，没有批量纳入其它未跟踪诊断物。
- `check_feedback_reproduction_gate.py --phase release` 当前明确 PASS，`issues=19`。此前 stale、024 未闭合和 clean-checkout 不可达三类错误均已消失，checker 本身未被放宽。
- 下一步从头运行完整 pytest。此前在 54% 主动中断的轮次作废，本轮必须获得最终退出码；若失败则聚焦最早失败、修复并从头重跑。

## 2026-09-23 00:33：完整套件发现旧发行 DAG 断言

- 从 0% 到 100% 的完整 pytest 明确收敛：656 passed、1 failed，耗时 3486.58 秒。唯一失败为 `test_release_workflow_cannot_build_or_publish_past_feedback_gate`，旧断言硬编码 publish 的 needs 只能是 `[feedback-reproduction-gate, build-linux-ubuntu16]`。
- 实际 workflow 现在正确要求 `[feedback-reproduction-gate, build-linux-ubuntu16, build-windows]`；这不是产品回归，而是历史测试合同漏表达 Windows 资产门。不能为消除失败而删 Windows 前驱，必须把旧测试升级为三前驱精确断言。
- 下一步只修改该历史断言，先定向运行发行 workflow 两组测试，再从 0% 重跑完整 657 项；第一轮失败结果保留为反例，不计最终通过。

## 2026-09-23 00:35：旧 Linux-only 断言已升级并定向转绿

- 历史 workflow 测试现在精确要求 feedback、Linux、Windows 三个 publish 前驱，与新增测试分别从旧门和新门两侧锁定同一 DAG；没有删除原有 feedback 顺序断言。
- 旧失败节点与新 frozen lineage 文件合计 6/6 通过，1.02 秒。下一步按约定从 0% 重跑完整套件；若无失败，才把 656/657 失败基线替换为最终结果。

## 2026-09-23 01:29：完整 657 项从头重跑通过

- 修改旧 DAG 断言后，从 0% 重新运行完整 pytest，最终明确退出码 0：`657 passed in 3350.65s (0:55:50)`。第一次 656/657 失败基线中的 workflow 错误已无法复现，且没有新增产品、Oracle、证据或发行测试失败。
- 该 55 分 50 秒是 657 项离线质检总时长，包含大量逐案真实布局与搜索，不是用户单次生成；用户正式 7302-byte/63-node/110-edge 输入的 frozen 双跑仍为约 41.6 秒/次并由 60 秒硬门约束。
- 下一步执行最终 feedback release、五件套、全公开 SVG 质量、语法/JSON/diff 检查；全部通过后复制修复前/后 SVG 到用户交付目录并核对哈希。

## 2026-09-23 01:38：全公开 SVG 门捕获 source 分区设施误报

- 最终 feedback release 与五件套再次 PASS，但 `check_all_svg_quality.py` 正确阻断：27 张公开图中 2 张被 `shared_root_single_bus` 拒绝，分别为 07 的 `xtal_1` 远距 8 设施和 26 的 `roots__common_source` 4 消费域设施。
- 根因不在本次 cycle 优化，而在此前为当前 source 根场景把该历史 `from` 单总线指标扩大到 `{from, source}`：指标注释本就说明任意远距分区由 facility split/merge dominance 管理；`source` 是可复制实体设施，扩大后把合法分区误当总线碎裂。当前具名修复由 `premature_interior_trunk_entry` 直接判定，不依赖该误扩大的指标。
- 修复限定为恢复 `shared_root_single_bus` 对逻辑引用型 `from` 的既有 owner，同时新增纯单元正反例：相同双设施结构下 `source` 不命中、`from` 必须命中。保留已知坏 `public_from` 制品测试，防止借消误报放走历史缺陷；随后重签因 Oracle 哈希变化而陈旧的全部证据并再次跑完整门。

## 2026-09-23 01:42：source 分区误报消失且 from 历史红灯保留

- 纯单元正反例与已知坏 artifact 注册表测试 2/2 通过：双物理设施 `source` 不生成 shared-bus witness，同结构 `from` 生成 1 个 `physical_facilities=2` witness；历史坏 `public_from` 仍在 29 项注册表中被拒绝。
- 全 27 张公开 SVG 已从输入重新生成并执行完整 29 指标，结果 `PASS 27/27`；此前失败的 07 与 26 均转绿，其他 25 张未退化。
- Oracle 文件哈希已改变，因此上一轮 fix/recursive 收据按设计会变 stale。下一步重跑全部 fix verification、七轮递归攻击和 Windows frozen 双跑，不能沿用旧收据。

## 2026-09-23 02:05：最终 Oracle 血缘三类收据全部重签

- 全部历史 fix verification 新批次 `20260922T174331Z-1559ee2f`，`failures=[]`；七轮递归攻击从 R1 重启，run `20260922T174910Z-723545dd`，`status=clean`、`consecutive_clean_rounds=7`。
- Windows frozen runtime 正式收据按最终 Oracle 重跑通过：两轮 42.48 秒与 41.71 秒，均小于 60 秒；SVG 均为 70985 bytes、SHA-256 `a28fc307…a56`，deterministic=true、29 指标无失败、目标 witness 总数 0。
- 下一步从索引撤下仅由本轮早期 Oracle 生成的旧两批证据（文件留在本机、不删除），精确纳入最终两批与最终 receipts；再跑 release gate。之后需按最终 Oracle 再跑完整 pytest，不能沿用 01:29 的 657/657。

## 2026-09-23 02:25：最终全量捕获 source 单设施双通道 mutant 回退

- 最终完整套件约 30% 出现 1 个失败后已主动中断，不计最终结果。定位到既有 `test_shared_bus_oracle_rejects_fragmented_public_source_mutant`：它要求 `source` 在同一物理设施发出两个首纵通道时仍被 shared-bus 指标拒绝。
- 前一版按 kind 整体排除 source 过宽。正确边界是“设施分区”而不是“kind 排除”：`source` 的多个远距物理设施可合法分区；但同一 source 设施的重复首纵通道仍是总线碎裂。`from` 继续严格要求单设施/单通道。
- 下一步恢复 source 分组，并仅在 `source` 的 bus routes 实际绑定多个物理设施时交给 facility split/merge 指标；同一设施多通道仍生成 witness。随后同时跑三项纯单元边界、全 27 SVG，再重签 Oracle 血缘。

## 2026-09-23 02:51：物理设施边界修正后的全套证据已重签

- 三项正反边界 3/3 通过；全公开 SVG 再次 `PASS 27/27`。最终规则同时保留 source 单设施双通道 mutant 红灯、from 多设施红灯，并允许 source 多设施远距分区。
- 最终历史 fix 批次 `20260922T182939Z-1d3acd3e`，`failures=[]`；最终递归 run `20260922T183524Z-e80ce0a2`，连续 7/7 clean。
- Windows frozen 最终双跑为 41.88 秒、41.82 秒，均 PASS、同 SHA、29 指标全绿且目标 witness 为 0。下一步切换索引到这两批最终证据，release/五件套通过后再次从 0% 运行完整 658 项；中断轮不计。

## 2026-09-23 03:48：最终完整质量闭环通过

- 最终代码、最终 Oracle、最终证据索引上从 0% 重跑完整 pytest，明确退出码 0：`658 passed in 3347.49s (0:55:47)`。source 单设施双通道 mutant、source 多设施合法分区、历史 from 碎裂红灯、具名修复、性能门、发行 DAG 与全部既有功能同轮通过。
- 用户规模冻结 EXE 两轮为 41.88/41.82 秒，较修复后未优化的 56.86/56.43 秒降低约 25.9%/25.9%，且输出与正确基线字节级一致；修复前症状图 SHA-256 `740172f0…b259`，修复后正确图 SHA-256 `a28fc307…a56`。
- 最终交付复制修复前自然复现 SVG 与 Windows frozen 修复后 SVG 到 Codex outputs；复制后只核对文件哈希，不改项目功能。最终 release gate、五件套、JSON、语法和 diff 门将在记录同步后再跑一次。

## 2026-09-23 10:11：补做自动发布闭环

- 用户指出项目已有“验收后自动发布”约定，而上一轮错误停在本地完成状态；因此记录重新置为 active，交付终点恢复为 commit、push、远端 Release 全绿、tag/附件核对与公开资产回下载 smoke。
- 上传前 fetch 证明 `main` 与 `origin/main` 为 0/0，没有远端分叉；GitHub CLI 可用，敏感配置路径未被 Git 跟踪或出现在历史中。
- 精确范围审计发现最终 fix/recursive 两组正式证据仍被旧 ignore 总规则命中，先前仅靠强制暂存；另有 177 个探索期根级 receipt 与 2 个本地 outer-goal receipt 不应进入发行提交。下一步用 `.gitignore` 明确白名单最终证据批次，并按探索命名空间排除临时回执，然后重建 staged 集合并执行上传门禁。
- `.gitignore` 已显式放行最终 fix 批次 `20260922T182939Z-1d3acd3e` 与 recursive 批次 `20260922T183524Z-e80ce0a2`，并排除 27 类探索命名空间及本地 outer-goal 收据；后续不再依赖 `git add -f`。下一步只暂存产品修复、测试/门禁、当前正式收据、发行 workflow 与项目决议记录。
- 首次普通暂存被 ignore 门拒绝，因为 Windows frozen 正式收据位于根级 receipt 规则下的子目录；未使用 `-f` 绕过。现同步把 `windows-frozen-runtime/**` 加入正式白名单后重试，确保所有发行证据都能由干净 checkout 正常取得。
- staged 上传扫描未发现密钥或冲突标记，但发现两条本机临时目录与一条邻仓进程绝对路径。保留审计事实和证据语义，将其分别脱敏为 `<local-temp>` 与 `<external-project>`；下一步重新解析 JSON、重暂存并复扫。
- 最终上传门通过：staged 593 路径，552 个为最终机器证据；未跟踪可见项为 0，敏感信息、本机/跨仓路径、父目录逃逸、冲突标记、超大 blob 与 whitespace 错误均为空。release gate `PASS issues=19`、五件套 PASS、官方 actionlint v1.7.12 PASS、JSON/YAML 解析 PASS；远端关系 0/0。下一步提交并非强推 `main`，随后值守 Release 到公开资产回下载验收。

## 2026-09-23 11:52：首轮远端发布与公开资产消费闭合

- 产品提交 `20f2f28cf0830f8fc93d22775ce22a3f10f997f2` 已正常推送到 `origin/main`；Release run `35810094595` 整体 success。反馈门 1h17m21s 全绿，Linux Ubuntu 16.04/staticx 2m16s 全绿，Windows PyInstaller/60 秒门 5m15s 全绿，publish 1m17s 全绿；无 skipped/cancelled job。
- `HEAD == origin/main == v1.0.0^{}` 均为 `20f2f28…997f2`。公开附件 Linux tar SHA-256 `f09ed1bd…0ffbf`、Windows ZIP `349d1f18…0a5a7`、Windows runtime receipt `8e75895d…849a2`，本机重新下载后的摘要与 GitHub asset digest 一致；两份归档表面检查 PASS。
- CI 已从公开 Release 回下载 Linux 包并跑 frozen smoke。本机另从全新临时目录解压公开 Windows ZIP，完整 frozen workflow PASS；同一下载 EXE 对 7302-byte、63 组件、110 边场景双跑 46.601097/45.201012 秒，均小于 60 秒，输出同为 70,985 bytes、SHA-256 `a28fc307…a56`，29/29 指标全绿、失败集合空、专项 witness 0、deterministic=true。
- 发布学习降级有两次可验证事件：Docker actionlint 因 `dockerDesktopLinuxEngine` 命名管道不存在失败；首次官方 Windows 二进制下载误用不存在的 `windows_x86_64` 资产名，校验条目缺失。随后查询官方 v1.7.12 资产清单，下载并校验 `windows_amd64` SHA-256 `6e7241b5…2f6e9`，actionlint PASS，因此未影响发布正确性。
- GitHub 仅产生未来维护告警：`ubuntu-latest` 将在 2026-10-19 起迁移 Ubuntu 26，且部分 action 的 Node 20 元数据被 runner 强制使用 Node 24；本次所有 job 成功，附件与下载消费均通过。记录现置为 done；状态提交后仍按常驻自动发布约定再次对齐 main/tag/附件。
