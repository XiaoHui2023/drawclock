# 用户反馈自然复现与防假完成门禁

- status: active
- created: 2026-09-03 13:32 +08:00
- updated: 2026-09-03 17:29 +08:00
- scene: 用户反馈自然复现与防假完成门禁

## 当前事实

- 用户指出上一轮没有完整复现六类布局问题，但 Agent 已声称完成并提交发布。
- 旧 `test_quality_oracle_rejects_same_root_split_rejoin_cycle` 先生成正常图，再手工重写航点；它是
  Oracle 变异自测，不是正常用户路径的 split-rejoin 复现。
- 旧的通过范围全部撤销。六个布局条目在取得公开 CLI 的两次自然红灯收据前保持 `reported`；
  对应 `src/**` 产品 owner 冻结。
- 本轮只允许修改项目账本、复现语料、只读 Oracle、门禁与项目 skill，不修改布局生产实现。

## 本轮目标

- 项目问题账本逐条保留独立问题与直接 Oracle；测试载体采用多对多语料模型，同一个自然输入可同时为多条问题提供证据，一条问题也可由多个输入共同覆盖。
- 结构门、修复授权门、完成门具有不同退出语义；结构正确不等于允许修复。
- 人工改图、故障注入、monkeypatch、测试专用入口和自报状态不能签发自然复现收据。
- 未复现时机器返回非零，commit/push/release 不得扩大为布局问题已解决。

## 15:18 多对多语料与独立 SVG Oracle 起点

- 新增 `tools/feedback_layout_reproduction_oracle.py` 初版，只读取 JSON 与最终 SVG，不导入 `src`；统计前消除重复点与共线点，区分异网内部正交交叉、异网重叠、折点、曼哈顿长度和同源网络拓扑。
- 当前初版在 current 与冻结 `6c9f9f4` 上均可绑定 example 25 的 69 个逻辑节点、66 条逻辑边和 75 个显示节点；冻结基线直接观察到 4 个异网交叉事件、2 个交叉坐标，并命中混合根语料和公共根/低复用根交叉症状。
- `19/20/23/25` 冻结基线首轮扫描尚未覆盖 split-rejoin、可避免折点、低复用根中间列和固定端口逆序；这些条目保持 `reported`，不解锁 `src/**`。
- 第一次冻结目录准备因命令包含递归删除临时目录被宿主安全策略拒绝，0.6 秒后改为全新 GUID 临时目录，无删除操作；第二次 6.3 秒成功生成冻结产物。
- 初版尚需 Oracle 自测、折点反事实候选和大语料 runner；当前统计结果只作为探索证据，不签发复现收据。
- Oracle 的折点判定已扩展为反事实支配：同轴边尝试零折点直线，三折点以上边尝试保持两端水平引出的 H-V-H 候选；候选只有在障碍、异网交叉、异网重叠、长度均不变差且折点严格减少时才成为证据。
- 新增 Oracle 单元测试，分别锁定内部交叉/端点接触/共线重叠、重复与共线航点归一、同源树与 split-rejoin 环、公开 CLI 最终 SVG 全边绑定和未命中问题非零退出；人工几何只属于 Oracle 自测，不计自然复现。
- 设计三类确定性正常输入生成器：多输入 mux 行、三输入 pad 交错和非对称双支路；每类交叉组合 4/8/12 行与四种插入顺序，共 36 个 JSON。因子表独立声明根类型、复用度、固定端口、链深、消费带间隔和输入顺序，测试与问题采用多对多映射。
- 36 个 JSON 在冻结 `6c9f9f4` 上全部经公开 CLI 成功，批量生成与独立统计耗时 17.894 秒。聚合命中 `FB-ROOT-001/002/003` 与 `FB-BEND-005`；其中 split-rejoin 由 5 个 pad 组合自然触发，可避免折点由 10 个 pad 组合自然触发。
- `FB-ROOT-004` 与 `FB-PORT-006` 尚未命中，当前覆盖率 4/6；下一轮扩大低复用根可行列、公共根跨层连接、端口排列与输入插入顺序的交叉组合，不修改产品实现。
- 第二轮增加 `middle` 族：公共根因独立深链被固定在早期列，单用根直连后层 mux，形成合法的中间列可行区间；三输入端口按行轮换，并继续交叉根类型、行数和插入顺序。端口逆序比较改用实际输出端点 y，而非器件外框中心。
- 第三轮增加 `port` 族：成批双输入目标、上下语义相反的实例名、端口映射轮换、三种零入度器件与输入插入顺序交叉；用于冻结端口纵序修复前的公开版本并寻找自然交叉。
- 历史版本分支试跑暴露入口与依赖差异：`3378c1b` 已使用无子命令入口，修正命令后 12 个 `middle` 用例 6.075 秒全部运行，但未命中首列低复用根症状；`06c4c6c` 的 `draw` 入口在导入 `configlib.loading` 时失败，当前环境中的 configlib 版本不兼容，尚不能作为端口逆序复现证据。
- 前一次把两个版本统一按 `draw` 调用导致 24 个产物均未生成，耗时 9.727 秒；Oracle 对缺失 SVG 全部 fail closed，未把该批计入复现。下一步优先在可运行冻结版本扩展正常语料；旧依赖环境只作为有界备选。
- `FB-ROOT-004` 不再依赖“恰好位于全图第一列”的表面阈值。独立 Oracle 对每个单用根构造消费者前的连续可行位置，平移完整根外框并重算路线；只有节点不重叠、障碍不穿越、异网重叠不增加，且交叉和长度同时严格下降才判定被支配。
- 上述 Oracle 修改已同步到本记录与索引，后续批跑将只写系统临时目录。
- 多对多分析文档已同步，当前继续冻结基线统计重算。
- 连续拒绝根因是旧试跑把产物写入含 `.cursor` 的冻结快照，使快照被识别为第二项目且产生独立待记账状态；主项目状态文件实际为 `pending_record=false`。重新以只读快照加外置 artifacts 运行后不再触发该问题。
- 更新后的根平移反事实在 `3378c1b` 的 12 个 middle 用例上 6.303 秒完成，仍未找到交叉与长度同时下降的单用根候选；`FB-ROOT-004` 继续未复现，表明现有 middle 结构已经把单用根置于中间列，需扩大影响其纵序和路线的交叉特征。
- 为端口纵序修复前的 `06c4c6c` 建立一次性临时 venv，并按该 revision 的 `pyproject.toml` 安装 `config-library[json5,toml,yaml]==0.18.1`；安装首次成功，耗时 28.3 秒，主要包来自本机缓存，仅 regex 元数据/轮包经网络下载。环境与 artifacts 均位于系统临时目录，不进入源码或发行包。
- `06c4c6c` 的 12 个 port 用例均由公开 CLI 生成，耗时 7.584 秒；旧 SVG 使用 `foreignObject` 且没有 `data-node-id/component-graphic`，初版 Oracle 因无法绑定节点逐张 fail closed。现增加兼容读取：只接受 foreignObject 文本中与输入 JSON 精确匹配且唯一的实例名，并取其公开 SVG 外框；不读取器件类别或生产内部状态。
- 兼容层对既有 12 张端口用例重算 2.278 秒、全边绑定成功，但这些断开的小双输入组均为零交叉，未触发端口逆序；这证明简单样本不足。下一轮加入共享上下游、非对称链深和相邻组排序耦合，不把“修复前版本”本身当作失败证据。
- 端口修复前的 example 18 经公开 CLI 与独立 Oracle 生成 50 节点、56 边、28 个异网交叉事件，但直接 mux 输入线均按端口纵序直连；交叉来自两个高复用根的长分发线，不能冒充 `FB-PORT-006`。该结果缩小规律：端口逆序需要不同层/链深或相邻排序约束共同作用。
- 端口修复前的 example 20 自然生成 9 节点、8 边、1 个明确交叉：`gate_a→sel.0` 的起点 y=166、终点 y=90，`div_b→sel.1` 的起点 y=110、终点 y=146，两条输入支路纵序反转。其唯一根祖先 `from_a/from_b` 均只连接一个下级；Oracle 因而改为沿 DAG 回溯唯一根祖先，验证完整独占支路相对固定端口的次序，而不限于根直连目标。
- 更新后的 Oracle 对 example 20 的 `FB-PORT-006` 返回 0；5 项 Oracle 自测继续全部通过，耗时 2.33 秒。聚合自然复现覆盖达到 5/6，仅 `FB-ROOT-004` 未命中；尚未签发正式双运行收据，也未解锁产品源码。
- `6c9f9f4` 新只读快照对 example 25 加 12 个 middle 用例重跑 6.724 秒；所有输出均未出现交叉和长度同时下降的单用根平移候选。该 revision 不能作为 `FB-ROOT-004` 失败基线；下一步核对用户实际看到的当前提交是否发生回归，并据实调整该问题的冻结 revision，不强套旧 revision。
- 当前提交的 example 25 在 0.202 秒独立统计中仍有两个单用根直线各穿过两条公共根纵线。首次连续位置反事实误用目标外框左边界计算候选，导致源外框与目标外框重叠而被拒绝；正确几何应以实际目标端点 x 和源输出端点在外框内的偏移计算 24px 引线净空。该修正只改变 Oracle 坐标公式，不改变判定阈值或产品几何。
- 修正后 example 25 的两个单用根均得到完整反事实：x 从 100.06 移至 179.72/185.72，交叉各从 2 降至 0，线长从 103.66/109.66 降至 24，且没有节点重叠、障碍穿越或异网重叠。因此 `FB-ROOT-004` 已在当前冻结候选上自然命中，聚合探索覆盖达到 6/6；下一步仍需正式双运行、哈希绑定收据，探索命中本身不解锁源码。
- 新增正式 many-to-many corpus 合同与 runner：三个冻结 case 分别承载当前混合根、6c9 pad 交错和 06c 非对称端口；每个 case 两次公开 CLI，产物写到 `.reproduction/evidence`，逐问题执行直接 Oracle，并绑定 revision、命令、输入、runner、Oracle、产物和只读前后哈希。
- 六条问题已从 `reported` 进入 `reproduction_in_progress`；这只表示正在签发正式证据，状态仍不允许修改 `src/**`。
- `FB-ROOT-001` 已绑定当前失败提交的完整哈希，并固定无圆弧的公开 SVG 入口；其余条目继续逐项同步。
- `FB-ROOT-003/004` 同步到当前 example 25，`FB-ROUTE-002/BEND-005` 同步到 6c9 pad 组合，`FB-PORT-006` 同步到 06c draw 子命令；仅剩 route 条目的短 revision 待规范为完整哈希。
- 所有问题现已使用完整 40 位 baseline commit；正式 runner 的 case、问题账本入口和 Oracle 参数一致，可以开始双运行。
- 正式 corpus `20260903T073830Z-da6179b8` 双运行通过，耗时 16.711 秒，`missing_issues=[]`。mixed-roots-current 两次均命中 ROOT-001/003/004；pad-weave-baseline 两次均命中 ROOT-001/ROUTE-002/ROOT-003/ROOT-004/BEND-005；asymmetric-port-baseline 两次均命中 PORT-006。
- 两次统计逐 case 完全一致：69/66 图为 4 个交叉事件、6 折点、6090.116px；43/48 图为 87 个交叉事件、46 折点、12440.1454px；9/8 图为 1 个交叉事件、8 折点、828.056px。每条证据均绑定原始 SVG、日志、报告及只读前后哈希。
- 六条问题均已升级为 `reproduced`；该状态只解除“允许开始修复”的前置条件，不满足 `fixed_verified/closed`，因此发布门仍应失败。
- 首次双门验签 0.686 秒失败：pad case 的报告额外命中 ROOT-001/003，runner 将其作为四次尝试写入这两条收据，但后两次 baseline 为 6c9、与问题合同的 2925 不同，并破坏确定产物一致性。修正为报告继续披露全部 observed IDs，收据只消费 corpus 合同中 baseline 匹配的显式 issue 映射；pad case 只为 ROUTE-002/BEND-005 签名。
- 修正后的正式 corpus 重跑 13.397 秒通过；六条问题各恰有两次合格尝试，`missing_issues=[]`，收据不再跨 baseline 混用。旧的失败证据目录保留为审计记录，最新 per-issue receipt 指向新 run。
- 用户根 validator 与项目自包含 checker 均以 `--phase solve` 验签通过，合计耗时 0.659 秒；这证明六条自然复现证据闭合，只解锁后续问题分析/修复，不代表布局已经修复，也不解除 release 阻断。
- 问题账本逐条追加正式成功尝试：每条均写明触发结构、两次公开入口观测、几何判据、规律分析和收据；早期失败尝试原样保留，避免用最终成功覆盖探索历史。
- 用户根 `agent-quality-workflow` 新增多对多复现 corpus 专题，`clock-tree-layout` 新增最终 SVG 几何 Oracle 专题；项目可发布的 `clock-layout-algorithms` skill 同步增加精简专题和路由。规则明确“问题判据逐项、测试载体多对多”，并规定搜索语料、证据语料、规律分析与综合样例的先后关系。
- 用户根 validator 对声明 `many_to_many` 的收据新增 `corpus_id/case_id/observed_issue_ids` 一致性检查；项目自包含 release checker 强制使用该模型并逐尝试确认当前 issue 被直接观测。Oracle 报告路径改为脱敏文件名，待重跑正式收据后生效。
- 项目门测试已从旧的“六项仍 reported”断言迁移为：solve 阶段必须通过、每条收据必须是无故障注入的多对多直接观测、聚合 corpus 必须无缺口且至少存在一个多问题 case；release 仍逐项失败。
- 新增自包含 corpus checker：验证 5 类 × 3 规模 × 4 顺序的 60 个有效 DAG、七项特征维度、正式问题映射全集和真实多问题 case；反例测试删除一条 issue 映射或把模型降成 one-to-one 时必须失败。Oracle 自测新增源码独立性 AST 检查和交叉谓词的参数换序/平移变形关系。
- 三组专项测试共 19 项通过，pytest 耗时 1.83 秒；corpus 独立门与 solve 门随后均通过，整组命令墙钟 4.00 秒。
- 综合 example 生成器已加入通用结构组合：三类零入度根、交错三输入汇聚、公共/低复用根、固定端口、非对称链深和末端时钟；所有节点仅使用公开 JSON 字段，通过命名空间合并且把组件引用一起重写，不含样例坐标或产品特判。待实际生成并跨冻结版本统计。
- `26-feedback-reproduction-combined.json` 已由生成器在 0.305 秒内生成，共 121 节点、22 个末端 clock；其余既有压力 example 同轮再生且无额外工作树差异。
- 综合 example 在当前版本绘制 0.510 秒、独立统计 0.268 秒，121 节点/122 边全部绑定，观测 88 次交叉、52 折点并直接命中 ROOT-001/ROUTE-002/ROOT-003/ROOT-004/BEND-005。相同 JSON 在冻结 `06c4c6c` 的公开 draw 入口绘制 0.659 秒、统计 0.262 秒，观测 154 次交叉、72 折点并额外命中 PORT-006；同一复杂 example 跨两条真实历史实现的观测并集覆盖六项，没有故障注入。
- 项目目标、设计笔记、changelog 与根因分析已同步当前事实。分析表逐项记录触发结构、直接几何观测、版本边界以及未命中反例；明确这些是复现规律，不冒充尚未审计的生产代码根因。
- 脱敏 Oracle 后正式 corpus `20260903T080236Z-e3579c26` 重签成功，耗时 13.472 秒；六项各有两次命中，统计与前两轮逐项一致，`missing_issues=[]`。报告只保留输入/产物文件名，不再写本机绝对路径。
- 入库预检发现 producer stdout 仍可能回显公开 CLI 的本机输出路径；runner 改为捕获原始 stdout/stderr 后，以 `{project}/{snapshot}/{trial}` 令牌替换两种路径拼写再落盘。该改动改变 runner 哈希，必须再做最后一次正式重签。
- 最终正式 corpus `20260903T080439Z-6666bbd3` 在 13.408 秒内通过，六项各两次且缺失为 0；对最新 evidence 与 receipts 扫描本机用户、临时目录和盘符模式均无命中。`.gitignore` 只开放该最终 evidence 目录及当前 JSON 收据，旧探索/失败 artifacts 继续作为本机审计资料但不进入仓库。
- 用户根 `agent-quality-workflow`、用户根 `clock-tree-layout` 与包内 `clock-layout-algorithms` 三个渐进式 skill 均通过 skill-creator 快速校验，总耗时 0.661 秒。
- 当前公开 CLI 已生成本地演示 `example/out/26-feedback-reproduction-combined.svg`，耗时 0.573 秒、大小 101,830 字节；该预览是当前未修复布局的复现展示，按既有忽略规则不进入发行源码。
- 最终合同复审发现 ROUTE-002、ROOT-004、BEND-005、PORT-006 的账本 Oracle 仍指向早期占位 JSON，虽 runner 实际检查正确 case，但合同血缘不一致。四处已改为与 producer `-i` 完全相同的输入；用户根和项目门均新增 producer/Oracle 输入等价检查。旧收据因合同哈希变化失效，下一步必须重签。
- 修正合同后的 corpus `20260903T080923Z-e37161d0` 在 13.619 秒内重签成功，六项无缺口，随后 solve 门通过；`.gitignore` 的唯一可入库 evidence ID 已切换到这组收据。
- 新增输入血缘故障测试：六条正常合同逐项无错误；把任一 Oracle `--input` 改成 `wrong.json` 后项目 checker 必须报告 lineage differs，防止同类占位样例再次逃逸。
- 用户根 validator 对无 `-i/--input` 旗标的其它公开 CLI 保持兼容；只要 producer 或 Oracle 任一侧声明输入旗标，就要求双方一致。用户根自测新增“多对多收据借用其它 issue 观测”故障并正确拒绝，整套自测 2.565 秒通过；项目 solve 门继续通过。
- 项目全量 pytest 422 passed、5 skipped，测试自身报告 90.29 秒，墙钟 91.825 秒；没有隐藏失败。五项 skip 为既有环境能力跳过，需在最终测试摘要核对具体原因，不自动提升为通过。
- skip 专项复跑 29 passed、5 skipped，pytest 0.56 秒、墙钟 2.258 秒；五项全部来自本机无可用 headless browser DOM capture。ELK、端口图形和本轮独立 SVG Oracle 均未跳过；浏览器能力缺口不影响本轮 `--crossing-style none` 的线段几何复现，但仍需按环境边界披露。
- 五件套 checker 0.263 秒 PASS，无缺失、断链或 worklog 错误。真实 `pack.bat` 在 0.394 秒内由 release 前置门返回 1，逐项列出六个 `reproduced` 但未 `fixed_verified` 的布局问题及开放的 META-CLAIM-007；未进入依赖安装、PyInstaller 或 dist 改写。这是预期发布阻断，不是打包成功。
- 代码生成自查发现中文 Markdown 编写前未加载删句/表达两项专门规则；已明确记录该流程偏差，随后完整读取两项规则并对新增用户根/包内专题及 design/changelog 新句执行补救审查，删除直角引号并改写含混的“命中、聚合、拓扑、观测”等词。该补救不能倒推为写入前已合规，但当前文本已按删句与禁词规则复查。
- 综合 example 新增生成结果一致性、121 节点、22 clock 和混合图根测试。首次草稿错误地对 source 自身做 `+= 0`，会让所有节点保持零入度、使混合根断言失真；在运行前自查发现，下一修改将按 target 的 source 数正确计算入度。
- 综合 example 测试已改为按每个 target 的 source 引用数量计算入度，随后只从真实零入度节点提取器件类型；待执行专项测试确认。
- 修正后专项测试 21 passed，pytest 报告 1.76 秒、墙钟 3.165 秒；六个新/改 Python 文件 py_compile 0.177 秒通过，corpus 门与 solve 门继续通过，整组耗时 3.848 秒。
- 上传审查 `git fetch origin` 成功，main 与 origin/main 为 0 ahead/0 behind；首次 divergence 命令因 PowerShell 将未引用的 `@{u}` 误解析而失败，改为引用完整 revision 后得到 0/0。综合 SVG 属本地展示文件，新增 `example/out/*.svg` 忽略规则，避免把预览误纳入提交。
- staged 自查确认 126 个文件中 `src/**` 为 0，新增行没有密钥、私人绝对路径、仓库外相对路径或构建垃圾。继续视读 Oracle 时发现两个准确性缺口：缺失孤立节点不会 fail closed；同一 source→target 多端口边依赖 SVG 元素顺序。现要求渲染节点名字全集等于 JSON 节点全集，并按目标端点 y 排序绑定重复 source-target 的固定端口；两项均新增反例测试。由于 Oracle 哈希变化，当前正式收据再次失效，必须重签后再提交。
- 增强后的 Oracle 专项 9 passed，pytest 1.16 秒、墙钟 2.572 秒；正式 corpus `20260903T082519Z-2df8f82f` 在 13.975 秒内重签成功且六项无缺口。可入库 evidence ID 已切换到该最终批次。

## 当前边界

- 六个布局问题已由正式多对多 corpus 自然复现；本轮仍不声明它们已经修复。
- 本地 managed hook 之外的管理员和远端仓库管理员仍是信任边界；远端 Required Check 是否启用
  需在 GitHub 侧单独核实。

## 13:42 问题登记

- `FB-ROOT-001` 到 `FB-PORT-006` 已分别写入机器账本，全部为 `reported`。
- `META-CLAIM-007` 记录未复现却提交发布的声明逃逸；它不会因布局回归测试通过自动关闭。
- 每条账本均声明冻结基线、公开 CLI、原始 SVG、只读 Oracle 和独立收据路径；尚无收据。

## 13:50 项目交付门

- `.codex/quality-gate.json` 将唯一项目验收命令绑定到当前 Git tree、策略哈希、命令哈希和随机
  challenge。
- 项目只有 Agent 记录/复现基础设施变化时校验账本结构；一旦工作树包含 `src/**` 变化，自动提升
  为 `--phase solve`，六条自然复现收据缺任一项即拒绝提交、推送和发布。
- 本门不把开放问题误报为已解决；它只证明当前修改没有越过“先复现再改产品”的边界。

## 14:02 首次写入前置门

- v2 policy 新增 `write_preconditions`，明确匹配 `src/**`；managed PreToolUse 在 `apply_patch` 等
  能解析目标的写工具发生副作用前调用 solve 阶段。
- 账本六条均未复现，因此当前 wrapper 必须返回非零；Agent 仍可修改复现语料、Oracle、测试、
  项目记录和门禁本身。
- 无明确目标的 shell 写入是本地解析边界，commit/push/release 的 delivery gate 会再次检查整个
  工作树；不能把本地 hook 表述为管理员不可绕过。

## 14:21 项目反例测试

- `tests/test_feedback_reproduction_gate.py` 验证开放问题允许维护账本，但 solve 阶段必须失败并逐条
  报出六个问题。
- 测试要求 `src/**` 写入前置命令保持启用，并拒绝把 pytest、monkeypatch、mutation 或改写输出
  注册为用户自然复现。
- 测试只验证门禁，不是六个布局问题的复现证据。

## 14:26 独立发布检查器

- 新增项目内自包含的 `release` 阶段，干净 CI 不依赖用户根 skill；它要求每条问题均已自然复现、
  修复验证且状态关闭，并逐项打印尝试、分析和未复现原因。
- 非发布阶段继续委托用户根验证器，避免项目规则与通用工艺分叉。
- 此时仅完成检查器实现，尚未接入打包脚本和 GitHub Actions；因此不得声称发布入口已经封闭。

## 14:31 发布入口与逐项尝试

- 六条 issue 分别记录现有思路、正常入口核查结果、分析、未复现原因和下一复现条件；没有任何条目被提升为 reproduced。
- 本地 `pack.sh` / `pack.bat` 在环境和产物变化前调用 release 门；GitHub Actions 新增 feedback 前驱，build 与 publish 均依赖它并移除 `always()`。
- 托管 hook 向项目交付门传递触发命令；项目对 pack/`gh release` 强制选择 release 阶段，而普通账本提交仍可选择 structure。
- 当前 release 门按预期返回 1，列出六条问题、缺失收据/修复验证和两个开放流程事故；这是“禁止发布”的成功负例，不是布局质量通过。

## 14:36 机器门自测

- 用户根自然复现 validator 自测通过；托管 hook 主套件 44 项、模块隔离套件 32 项通过。
- 项目反馈门 7 项通过：逐 issue 失败清单、solve 阻断、pack 早停顺序、CI 依赖与禁止 `always()` 均由静态/执行测试约束。
- 首轮新增命令透传测试因临时策略未保护 `gh release` 而没有触发 mock，已改用策略保证保护的 `git push` 后通过；该失败没有被隐藏。

## 14:40 托管安装与首次宿主探针

- 托管安装器完成 44+32+33+6 项测试、4/4 mutation kill、25 文件 doctor，并热安装成功。
- 首次真实交互宿主探针实际看到了 UserPromptSubmit 注入；随后因本机 Codex CLI 0.140.0 不支持指定的 `gpt-5.6-luna` 返回 HTTP 400，未进入产品写入拒绝阶段。
- 该次不计宿主闭环通过；按有上限策略仅再以兼容模型重试一次。

## 14:44 宿主探针有界收敛

- 第二次改用 Codex CLI 可运行的 `gpt-5.4`；会话成功加载项目上下文、执行 UserPromptSubmit 及多个 Pre/PostToolUse，但 90 秒预算内 Agent 一直读取资料，尚未发起 README 写入。
- 因而语义注入已在真实宿主可见，但“随后的产品写入被拒绝”只由项目上下文 33 项单测证明，尚无完整宿主级写入拒绝证据。
- 两次有界尝试已用尽，本轮不再无限等待；恢复条件是精简探针提示/启动上下文或升级 CLI 后重新运行四路径宿主验收。

## 14:49 完整回归与真实 pack 早停

- 直接 `unittest discover` 因未加载 pyproject 的 `src/tests` pythonpath 出现 7 个导入错误；改用项目正式 pytest 入口后 409 passed、5 skipped，耗时 88.43 秒。
- 真实执行 `tools/pack.bat` 在 release 检查器处 0.85 秒返回 1，逐条打印六个 issue；未进入 venv、pip、npm、PyInstaller 或 bundle 阶段。
- 该失败正是当前开放反馈下的预期发布阻断；不能将其表述为发行包验证通过。

## 14:53 触发命令分级闭环

- 项目交付门将 `pack.bat`、`pack.sh`、`bundle_release.py` 和 `gh release` 统一映射到自包含 release 检查器；源码修改的 commit 仍走 solve，其它提交走 structure。
- 8 项专项测试通过，覆盖三类触发命令、阶段选择、逐 issue 报告、pack 早停与 CI 依赖；py_compile 与 diff whitespace 检查通过。

## 14:58 远端发布负门验证

- 质量基础设施检查点 `291274e` 已推送 main；GitHub Actions run `33724488973` 在反馈门失败。
- 同一 run 的 Linux Ubuntu 16.04 build 与 Publish GitHub Release 均为 skipped；feedback job 从开始到结束约 10 秒。
- 远端 `v1.0.0^{}` 仍为 `0a2f48b`，现有资产发布时间未变化；因此本次没有发布新包，也没有移动滚动 tag。
- `META-RELEASE-008` 的发布旁路修复已有真实 CI 证据，可以关闭；六条布局 issue 与 `META-CLAIM-007` 继续开放并阻断发布。
