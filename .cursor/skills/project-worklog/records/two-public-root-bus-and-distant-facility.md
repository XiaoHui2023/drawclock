# 双公共根 MUX 总线与远距公共根设施

- status: active
- created: 2026-09-17 10:57 +08:00
- updated: 2026-09-17 15:10 +08:00
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
