# 双公共根 MUX 总线与远距公共根设施

- status: active
- created: 2026-09-17 10:57 +08:00
- updated: 2026-09-17 17:25 +08:00
- scene: two-public-root mux bus and distant facility

## 2026-09-17：冻结自然失败基线

- 用户新增两项不冲突要求：重复双输入 MUX 行中的两个公共零入度根都必须各自形成纵向总线；总线列可以依据完整端口/交叉几何错开。另一个公共根若同时服务相距很远的上、下带，拆分为同名显示设施能严格减少长主干时必须允许。
- 以未修改的当前生产 `generate_elk_layout` 构造 4 行 `public_from→gate→mux2` 与 `public_source→gate→mux2`。首次 Python 命令漏设 `PYTHONPATH=src`，报 `ModuleNotFoundError: auto_layout`，不作为复现。重跑后 `_regular_fanout_array_roots=[]`、`_shared_fanout_bus_roots=[]`；两个公共根均被渲染为 4 个同名设施，确认自然失败。
- 根因假设：规则阵列识别把另一路限定为逐行低扇出私人根，遗漏“另一个根也跨多行重复进入同一组 merge”的公共/公共关系；该遗漏令后续设施分区把二者拆散。生产修改前已新增定向红灯测试，当前断言稳定失败。
- 总线识别器现按“零入度根经单入单出支路到达的 merge 行集合”判断：一根的对应输入可以是逐行私有根，或与它共享至少两条相同 merge 行的第二公共根。定向红灯转绿，两个公共根均只保留一个物理设施；独立 `layout_quality` 对同一原始输入返回 `passed=true`、无 hard failure、无碎裂总线或规则阵列 witness。两次独立复核命令先后漏掉 `tests` Oracle 路径，均得到明确 `ModuleNotFoundError`，第三次以 `PYTHONPATH=src;tests` 成功；前两次不计验证成功。
- 远距分区探针使用同一双公共根、上/下两组 mux 行，并把下组完整物理带平移 1500px 后重新连接端口。它确认两根仍是规则总线根，但 `_replicate_dispersed_roots` 返回 candidate_roots=0、replicas=0；根因是该最早 owner 仍以 `root in structured_bus_roots` 无条件跳过。此前移除的是后段局部分区的同类跳过，未触及最早 owner。该探针是故障注入，不替代待完成的自然公开入口复现。
- 新增最窄 owner 红灯 `test_distant_structured_bus_roots_can_open_same_name_facilities`：上/下两组同一双公共根 mux 行保持规则总线身份，下组整体远移 1500px；当前仍只保留一个 `public_from` 设施，断言 `len(facilities)==2` 失败。该测试专门验证“总线语法不能成为几何支配分区的绝对禁令”。
- 取消最早 owner 的结构总线跳过后，夹具仍报告 candidate_roots=0。回读发现 `_forced_dispersed_root_layout` 只移动名称含 `_bottom_` 的对象，而新夹具名称为 `*_bottom`，没有实际远移。这是夹具语义错误，不能归因产品；下一步把上/下行命名改为 helper 的明确匹配形式后重新运行红灯。
- 夹具命名改为 `*_bottom_0` 后，真实远移 probe 转绿：两个公共根都从 1 个设施变为 2 个同名设施。独立 `layout_quality` 返回 `passed=true`、hard_failures=[]、rendering_replicas 为 `public_from:1/public_source:1`、fragmented_fanout_sources={}、split_rejoin_fanout_nets=[]。紧凑四行双公共根、既有紧凑公共根、复杂多 from 远距设施、现有分区精确 Oracle 共 6 项回归同时通过。

## 2026-09-17：相关全量回归否决初版泛化

- 随后运行 `tests/test_elk_layout.py` 与 `tests/test_feedback_layout_oracle.py` 的相关全量集；该长跑先出现多个失败并被中止，不能计作通过。使用 `-x` 收敛到首个稳定反例：`test_regular_common_array_generalizes_across_depth_size_and_order[6-0-True]`。它是既有的公共/私人六行数组，只改变声明顺序；输出把 `shared` 公共根渲染为 6 个副本，而 Oracle 要求 1 个。
- 根因尚未结论，但初版 `_regular_fanout_array_roots` 改写了既有公共/私人识别的遍历语义，而不是在保持原判定不变的前提下添加公共/公共关系。此为回归，前述局部六测通过不构成完成；下一次生产修改前必须先以该反例锁住兼容性，并验证最早设施 owner 的放宽不会重开该回归。
- 定位复核表明总线识别器对该反例实际仍返回 `{shared}`；六副本来自 `_replicate_dispersed_roots`。其普通相邻行的目标轴间距为约 177px，而可见设施成本为约 161.84px，纯 L1 减墨目标遂逐行拆分。规则阵列必须把这种均匀行距视为主干语法的一部分；只有显著大于全图标准行距的真实带间空洞才允许结构总线参与拆分。
- 追加结构间隙门后，早期 owner 正确拒绝紧凑 `shared`（`structured-bus-compact` blocker），但同一根仍被后段 `_split_root_rendering_anchors_by_local_rows` 逐行复制。这证明两个 facility owner 没有共同的结构所有权边界；修复应使早期全局分区成为结构总线唯一允许的拆分阶段，后段局部优化不得绕过该门。
- 恢复该所有权边界后，四组既有公共/私人 order/depth 参数、双公共根、远距 probe、紧凑反例、复杂 multi-from、分区精确 Oracle 共 10 项通过。联网查阅官方 ELK/yFiles 文档：ELK 将分层、交叉最小化、坐标和路由分为独立阶段；yFiles 把同一 source/target group 定义为共享段的 bus-style edge group。项目因此采用“拓扑确认共享网络，单一全局设施 owner 决定是否跨真实空带拆分，局部阶段不得反向破坏 bus”的职责分层，而非按名称或单个夹具修补。
- 全量 `pytest -q` 已通过技能结构检查，进度到 22% 后进入无输出长跑；追加两个 30 秒窗口和一个 60 秒窗口仍无新增输出，按有上限的运行策略发送 Ctrl-C 终止。没有完整退出码，不能把它记为全量通过或发布证据；后续必须使用 `-vv`/分文件运行找出可验证的耗时用例并恢复全量门。
- 可见 `-vv` 分段证实公共/私人参数组全绿，但 `test_premature_corridor_rejects_local_gain_that_worsens_global_crossings` 稳定红灯：反向声明 `pad-r08-s02` 的冻结 crossing oracle 从 16 变为 12。不得因数值变小就改写冻结 Oracle；该图是 direct collector bus，不是用户的新“每行经独立 branch 到 mux”的结构。根因是全体 `structured_bus_roots` 被开放给远距分区，范围越过了新增 repeated-mux grammar。下一步：仅对 `regular_array_roots` 开放结构总线的远距设施竞争，保留 direct collector bus 的既有保护；非结构根仍由原设施能力覆盖。
- Scope 修正后，`pad-r08-s02` 精确 Oracle 恢复，公共/私人四参数、双公共 mux、远距 repeated-mux probe、紧凑总线、multi-from、分区精确 Oracle 合计 11 项通过；五件套技能检查通过。全套 644 case 尚无完成退出收据，发布保持关闭。

## 2026-09-17：自然多端口 cohort 列对齐

- 新需求不是把所有 mux 硬拉到同列，而是在无 `layout_column` 用户约束时，识别同 kind、同 merge generation、同多输入/多输出端口角色、互不因果且 ASAP/ALAP 可行区间相交的多端口结构地标，软性偏好同一列；端口、交叉、障碍与显式列约束优先。
- 以五行双公共根自然输入复现：`public_from→gate→mux2` 与 `public_source→gate→div→mux2`，整体声明逆序，无显式列。当前生产结果五个 mux2 均为 `x=489.76`，独立 `layout_quality` 为 `passed=true`、hard_failures=[]。这证明现有 `_ranks` 的 structural cohort 机制命中该通用拓扑；仍需固化为明确回归，防止后续总线修复把它移除。
- 联网复核官方 ELK/yFiles：ELK 将 layer assignment、crossing minimization、node placement、edge routing 分相；yFiles 将 node type 作为不违背交叉和其它约束的次级优化。项目采用同样的软 cohort，而非基于命名或强制列的规则。
- 已加入 `test_similar_muxes_share_a_natural_column_with_asymmetric_inputs`：五行、两公共根、一侧多一层、整体声明逆序、无用户列提示；断言五个 mux 的精确 x 列相同并由独立质量 Oracle 通过。项目 hook 拒绝在测试修改后直接写技能文档，要求先同步此记录和 INDEX；该拒绝是有效流程门，不是产品失败。
- 当前树全量 `pytest -x -vv` 运行至 221 passed 后，在 `FeedbackReproductionGateTest.test_fix_receipts_bind_current_source_and_reject_stale_lineage` 失败；确定错误为 `FB-ROOT-001: fix receipt source tree is stale`。这是源码修改后的血缘保护正常触发，不是几何回归；旧 receipt 不能被改写或豁免，必须用 `tools/run_feedback_fix_verification.py` 在当前树重新签发完整修复组，然后重跑全量门。

## 2026-09-17：全量发布完整性缺口冻结

- 重新签发当前树的 fix verification 后，完整 `pytest -q` 终态为 `639 passed, 5 skipped, 1 failed in 3580.77s`。几何、拓扑和新增双公共根/mux cohort 用例均未失败。
- 唯一失败为 `FeedbackReproductionGateTest.test_release_gate_accepts_hash_bound_fix_receipts`：release checker 报 `recursive attack source tree is stale`，并列出 261 个 `.reproduction/fix-evidence/20260917T051659Z-e7aca1f8/**` 文件不在 Git index 中。该门禁要求干净 checkout 也能验证每个 SVG、日志和报告哈希；当前生成文件受忽略/未暂存状态影响，故不能发布。
- 这不是可用 `--no-verify`、修改 checker 或只暂存 manifest 绕开的失败。下一步先阅读 release checker 与重签发工具的证据跟踪契约，确定应当将哪一组可复现证据纳入 index、何时重签发 recursive receipt；随后以干净 index 重新执行 release gate 和全量测试。
- 当前 fix evidence 组已被显式加入 `.gitignore` 的有限 allow-list 并暂存；随后执行七轮 `defect-driven-adversarial-regression-loop`。回执 `20260917T063334Z-6f7a7a54` 返回 `status=clean`、`consecutive_clean_rounds=7`，没有复现目标问题或质量失败。该新 recursive evidence 组还未获 allow-list，项目 hook 因“新权威结果未写工作日志”先拦截修改；拦截有效，记录后才可继续。
- 当前 recursive 证据组也已显式 allow-list 并暂存；以 `python tools/check_feedback_reproduction_gate.py --phase release` 复核，结果为 `PASS issues=19`。前一次少传 `--phase` 的 argparse 退出不计为门禁失败；本次才是可用的发布完整性收据。

## 2026-09-17：发布边界穷举的完整反例

- 已提交的 `f5c0ecc` 远端 Release 在 `Exhaust boundary-trunk coverage directions` 运行 24m 后以 exit 1 失败。GitHub 公共页面只给出退出码；本地无认证 REST 因 `403 rate limit exceeded` 无法读取日志，故不将其表述为已查明。改以同一命令在受控后台重放，34/34 case 与 979 个覆盖单元均完成，收据精确复现 `clean coverage gate failed`。
- 收据只剩 `case-011` 的 `regular_array_single_facility` 失败：24 行 common/private mux4 阵列含外部 mux、额外公共消费者、双公共编织障碍。`common_from` 已被拓扑识别为 regular/shared bus root，但生成 SVG 中出现 24 个 `common_from` 设施；不存在提前主干切入或其它质量失败。
- 根因：远距设施放宽条件以全页 node 行距估算“结构空带”，一处局部列间间隔即可放行；随后通用 L1 分区器按每行墨水成本拆分整个规则阵列。该判断没有把“公共根自身重复 branch→merge 行”的间距作为唯一可拆分边界，导致总线语法被设施优化绕开。
- 下一步实现并验证：对 regular shared bus，仅以其自身 branch→merge cohort 的相邻行距定义真实空带；仅在此类空带处分区，并把非 cohort 输出归入最近结构带。这样紧凑/不规则页面行不会逐行裂解，而真实上、下远距 mux 带仍可形成两个同名设施。
- 已开始实施上述 owner 收敛：direct collector 仍无条件保护；regular bus 改从 root 的单入单出 branch→merge 输出收集结构行，并计划以其相邻间距的四倍作为唯一带间阈值。当前补丁尚待修正遍历索引并运行定向回归，不能记作修复完成。
- 首次定向回归在新路径发现 `NameError: incoming is not defined`；原因是 `_replicate_dispersed_roots` 仅建立了 `indegree` Counter，结构边识别却使用了未定义的同义映射。语法编译无法覆盖运行分支，故该失败被记录为必须补齐的运行时门禁；下一步建立共享入度表并重跑。
- 重跑后根因继续收敛为 `TypeError: object of type 'int' has no len()`：共享表是 `Counter`，结构识别错误地以列表 API 调用它。修正为直接的入度数值比较后，才可评价布局结果；此前两次失败均是实现运行时错误，不得作为质量通过。
- 同一最小回归随后发现 merge 入度处残留同一种 `len(Counter[name])` 误用。决定不保留无意义的 `incoming` 别名，直接复用 `indegree` 数值语义，并以两个 public-root 路径和远距分区路径共同覆盖该 helper。
- Counter 语义修正后，紧凑双公共根和不等深 natural mux cohort 均通过；远距双行 probe 仍为一设施。其唯一 structural delta 被同时当作基准行距，`4 * delta` 因而永远大于自己。两条结构行没有内部重复间距可估计，须回退到页面行距；三条及以上仍使用 cohort 本身的中位相邻间距。
- 双行回退实现仍未触发的直接原因已定位：`desired` 元组是 `(axis, edge_id)`，却以 `dict(desired)` 构建后按 `edge_id` 查询，导致所有 structure edge 被过滤。修正为 `{edge_id: axis}` 后，结构带检测才能观测到实际的 1500px 空带。
- 修正后定向三测全绿：紧凑双公共根总线、自然不等深 mux cohort、1500px 远距双行设施。先前失败的真实 `boundary-trunk` case-011 重新生成后，`common_from` 显示设施从 24 降至 1；以完整 `quality-metrics.json` 评估，`failed_metric_ids=[]`、规则阵列复制 witness=[]、共享总线碎裂 witness=[]。编码后台 Oracle 启动的首次 PowerShell 参数分词报 `SyntaxError`，第二次采用单参数编码入口后成功；前次未进入产品逻辑不计为结果。
- 下一步：再次执行 34 case/979 单元边界主干门禁，随后才可进入全量 pytest 与远端发布验证。单 case 成功不能替代方向覆盖。
- 修复后的完整 `search_boundary_trunk_coverage.py --expect clean` 已终态通过：34/34 case、979/979 coverage units、missing semantic directions=0、quality failure cases=0、first reproduction=null，stdout 为 `clean coverage complete cases=34 units=979`。这既是对远端 exit 1 的完整机器复现，也是修复后的同源验证；下一步仍必须执行全量 pytest、release gate、提交和远端发布回验。
- `check_five_piece.py` 通过。第一次后台完整 `pytest -q` 在约 29% 后非正常结束：stdout 无失败文本但没有 pytest 汇总，stderr 为空，父进程句柄消失且未留下退出码。这不是可用的门禁结论，也不能被解释为通过。下一步将以输出明确退出码的受控父进程重跑；若再发生，记录外部中断并按上限诊断。
- 带 `PYTEST_EXIT=<code>` 的受控父进程重跑也在约 22% 消失，stdout 同样没有 summary/exit 行，stderr 为空，pytest 子进程也不存在。这排除“普通 pytest 返回而缺少日志”的解释，表明该运行环境或解释器进程组在某个固定长例附近被终止。下一步以 `-vv` 获取最后实际测试名，再按分段全集验证；在得到每段明确退出码前，禁止发布。
- `-vv` 定位运行明确通过原 64-clock 疑点及其后所有到 27% 的用例，再次在约两分钟被外部终止，最后停在 `test_current_cli_closes_premature_interior_trunk_entry` 的输出行，无 pytest failure/summary/stderr。由于两种父包装都无法存活到单次全集终态，采用收集清单驱动的短分段执行：每一段要求明确 exit=0，所有已收集 node id 必须恰好被某一段覆盖；这保持全量范围而不依赖被环境回收的单长进程。
- 非长文件段以 `-x -vv` 收敛到首个真实失败：`FeedbackReproductionGateTest.test_fix_receipts_bind_current_source_and_reject_stale_lineage` 报 `FB-ROOT-001: fix receipt source tree is stale`，此前新增双公共根/远距设施源码修改使旧 fix receipt 哈希失效。前 138 项（含新 layout tests）通过；这是血缘保护正确拒绝陈旧证据，下一步重签当前 fix verification，不允许修改 checker 或豁免该门禁。
- 当前树 fix verification 已成功签发组 `20260917T090032Z-f9611418`，输出 `failures=[]`；22 个 baseline/current feedback artifact 目录均在组内。下一步重签递归攻击收据（旧 receipt 同样绑定旧 `src` 哈希），然后执行 release phase checker。
- 递归攻击已终态通过：`status=clean`、`consecutive_clean_rounds=7`、run `20260917T090757Z-8c29ddb5`；每个实际 case 都执行完整质量指标集。当前 fix 与 recursive evidence 组被 `.gitignore` 精确 allow-list，以便干净 checkout 能重验哈希；不扩大其它中间目录的跟踪范围。
