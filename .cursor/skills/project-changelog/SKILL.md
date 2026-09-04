---
name: project-changelog
description: >-
  本仓库：按时间记录要求与决议；最新在上；矛盾以最新为准。
---

# 变更记录

（规则见 `~/.cursor/skills/agent-project-changelog/SKILL.md`。）

## 2026-09-04

- **mux3 边界与发行范围收敛**：第 27 例使用六个稀疏 `mux3`，公共/私有根分别接输入 0/1、输入 2 空置，再继续 `cell→clock`；冻结旧版与当前版均为单公共设施、单纵干线的成功边界。删除 512/1024/2048/4096 的五组高压力输入、生成图和专属验收，维护发行范围以 16/64/128 终端时钟为代表但不在 CLI 设置固定上限。提交 `aabdd48` 的滚动 Release、公开回下载 frozen/source smoke 和独立包内源码消费均通过，`FB-ROOT-015` 关闭。
- **相邻高根折点修复**：`FB-BEND-014` 由冻结公开 CLI 双跑复现。根因是线段—矩形相交基元以浮点精确相等识别水平/垂直，端口计算的极小尾差被当成斜线并虚报碰撞；公共基元改用显式容差，保留严格障碍门而不按器件类型特判。
- **紧凑公共根合并**：`FB-ROOT-015` 由冻结四行公共 source 双跑复现。两处分区 owner 统一以同网共享线段并集长度和当前器件真实可视框周长决定设施数量；紧凑工整消费者保留一个图案与纵向干线，真正远距消费带仍可生成任意数量副本。
- **大图无损加速**：下游同行轴优化先复用节点/边索引完成线性结构预检，仅在存在真实候选时构建全局碰撞与交叉报告；4096 时钟门恢复到 30 秒预算内，复杂组合图候选仍正常执行。
- **紧凑消费带过度拆分反馈**：登记 `FB-ROOT-015`。同一零入度逻辑时钟服务相邻或近邻工整下游时，应优先由一个显示设施与一条共享纵干线分发；四至五行只用于搜索复现，不作为生产阈值，是否拆分由实际几何与完整质量向量决定。
- **相邻高根器件折点反馈**：登记 `FB-BEND-014`。两个相邻高零入度器件连接右侧多输入器件时，下方路线疑似因高度或可视障碍计算过度保守而折弯；只有最终 SVG 的直线反事实确认真实可视净空后才判为缺陷，冻结自然双跑前不修改生产布局。
- **交叉分区折点关闭**：路线按有序交叉点分为 whole/prefix/interior/suffix；多入边共同端口轴驱动完整下游视觉行闭包，只有具体碰撞、端点、异网重叠、交叉事件/点和线长均不退化且折点严格减少才接受。冻结公开入口仍保留 1 个交叉且尾段 2 折，当前入口保留相同交叉并把两条 mux 入边直线化。
- **局部区段折点反馈重新打开**：`ports__sel` 输入路线在整边含交叉时，最后交叉之后的无交叉尾段仍有多余转向；登记为 `FB-BEND-013`。现有整边无交叉判据作废，产品 owner 在局部区段 Oracle 经正常入口自然双跑复现前保持冻结。
- **两项新增反馈关闭**：公共零入度根连接局部 mux 的四拐点远绕，以及物理单边根锚点滞留左列造成的可避免跨线，均由冻结旧版公开入口双跑复现；当前公开入口双跑不再命中 `FB-ROUTE-009` 与 `FB-ROOT-010`。
- **消费者走廊**：零入度显示设施可按物理服务边移动或拆分到消费者附近；移动消费者及右侧后缀、重接端口、回收空设施后，以可视碰撞、异网重叠、交叉、折点、线长和源设施冗余的完整布局比较决定是否接受。
- **层序与规模门**：走廊不得破坏独立纯 DAG ALAP 层序包络；连接关系工作量较低时使用连续列与精确走廊搜索，工作量较高时使用规范列搜索，两种路径共用相同几何硬门且不读取节点名称、器件类型或 clock 数量。
- **反馈关键字**：用户表达“有问题”“还是有问题”或“违反优化功能”时，每项现象都登记为独立问题；共享测试图只承载证据，不能合并问题身份。

## 2026-09-03

- **六项反馈闭环**：普通零入度根交叉、同源分裂-重合-再分裂、公共根穿越低复用根、低复用根滞留早列、可避免折点、固定端口支路反序均由冻结旧版公开 CLI 自然双跑复现；当前公开 CLI 对相同语料双跑后六项均不再命中。
- **问题关闭**：六项均已绑定冻结自然红灯、当前公开入口逐 case 双跑绿灯、独立 Oracle、全量回归和新静态包消费证据，项目专用门与用户根通用门同时通过后从 `fixed_verified` 进入 `closed`。
- **逻辑网络树化**：同一逻辑根与输出端口的显示副本先按真实共线重叠合并身份，再以“长度、真实转向、图边数”最短路树消除物理环；目标端口保持叶节点，终态逻辑环秩必须为零，端口、碰撞、异网重叠、交叉、折点和长度不得退化。
- **逐 case 确定性**：一项反馈可由多个不同输入共同覆盖；确定性门要求每个输入至少双跑且哈希一致，不再错误要求不同输入产生相同 SVG。最新自然红灯与当前绿灯证据均纳入版本控制，远端 checkout 可独立复验。
- **零运行时依赖发行**：公开布局完全由标准库 Python 实现，删除未调用的 Node/ELK 参考入口、npm 清单与 Runtime 打包链。压缩包保留完整源码、单器件库目录、26 个布局示例和七个项目 Skills，不携带 Node.js、浏览器或第三方 Python 运行时依赖。
- **多对多自然复现**：问题判据保持逐项，测试载体改为 `case -> observed issue IDs` 多对多关系；60 个正常 JSON 搜索语料和三个冻结证据 case 使六项各获得两次自然红灯，不再要求一问题一个文件。
- **独立几何 Oracle**：从最终 SVG 绑定全部节点、边和端口，区分交叉/接触/重叠，规范化折点，并用同网环、固定端口纵序和无退化反事实判定 split–rejoin、异常折线与根位置；人工几何只用于 Oracle 自测。
- **综合复现**：新增 121 节点、22 clock 的 `26-feedback-reproduction-combined.json`；相同公开 JSON 在 current 与冻结 06c 的直接检测结果并集覆盖六项，用于展示交互而非替代各自 baseline 收据。
- **反馈语义触发**：用户表达“仍然、错误、异常、没有复现、质量不过关”等负反馈后，必须先逐项登记问题、尝试、观察、分析、未复现原因与下一条件；未登记前禁止产品修改。
- **发布失败闭包**：本地 pack 和 GitHub Actions 在构建前执行自包含 release 门；任一问题未自然复现、未修复验证或未关闭即失败，build/publish 依赖该门且禁止 `always()` 旁路。
- **诚实状态（历史阶段）**：取得自然红灯时六条布局问题只升级为 `reproduced`，尚未进入 `fixed_verified/closed`；该阶段只解锁产品修复，打包和发布仍失败。后续状态以本日较新的闭环记录为准。

## 2026-09-02

- **19 复杂多源交错示例**：19 扩展为 8 个独立 source、48 个 clock，覆盖非周期不定间隔直连、完整/稀疏三输入 PAD、根集合重叠、PAD 扇出、PAD 与另一 source 二次汇聚、不同链深与复用度；独立 Oracle 量化祖先签名、根对和间隔，旧 12 行浅层语料会被突变门拒绝。
- **远端 Release 资产消费门**：publish 后从 GitHub Release URL 重新下载 Linux 压缩包，在全新目录解压并运行 frozen 与离线源码代表性 smoke；不再以 publish 前 workflow artifact 代替用户实际下载物。
- **多输入 pad 合同**：保留旧 `pad` 的零输入单输出语义，新增独立 `pad3` 器件文件；布局只从库标题与 `0/1/2/C` 可见端口推导连接，不按器件名增加生产分支。
- **逐边与逐源路由统计**：质量报告增加每条边的完整曼哈顿/横纵长度、最长竖段、效率、折点、交叉点与交叉对事件，并按逻辑源聚合锚点、长度和折点；测试端按最终几何独立复算，禁止生产实现自证。
- **通用分散源副本**：仅零入度逻辑源可重复显示；同源多目标的设施成本按一条共享竖干线的覆盖跨度计一次，再加几何行距归一化的锚点开设成本。排序后在 `gap > fixed_cost` 的每个间隙切分是精确最优解，锚点数量由输入几何决定，不设固定上限；同行消费不妨碍四行外远簇单独例化，中间与末端器件禁止复制。
- **源副本接受门**：每个显示锚点必须实际服务逻辑边，不能无代价合并；节点/文字/线碰撞、异网重叠、交叉与折点不得退化，且必须改善交叉或扣除开设成本后的线长。面积只作低优先级记录，不能覆盖可读性收益。
- **性能约束**：夹行统计改为二分计数，设施分区由二次动态规划化为 `O(k log k)` 精确间隙算法；确定几何失败的候选提前停止，最终统计复用已验证硬指标，无候选的链轴精修先做结构预检。1024、2048、4096 压力门继续受 5、10、30 秒预算约束。
- **浏览器 Oracle 能力门**：系统存在浏览器可执行文件不等于 headless DOM 可用；最小 DOM 往返失败时明确 skip 并记录工具阻塞，能力恢复后自动重启端口可见几何强门。

## 2026-08-26

- **单文件单器件库**：内置 `drawclock.xml` 全集迁移为 `drawio-lib/drawclock/` 目录；每个标准 draw.io XML 恰好包含一个器件，文件名不参与类型识别。
- **多来源加载保持**：`--library` 继续支持多个文件、多个目录及混合输入；递归扫描、稳定排序、路径去重和重复 title 拒绝语义不变。
- **发行门迁移**：组件 XML 逐文件进入源码 manifest；冻结程序与无依赖源码消费门都从目录生成 SVG，并覆盖混合输入。

## 2026-08-25

- **发行项目 Skills**：发行包根目录新增器件库设计、布局算法、JSON 合约、成图设计和项目导航五个渐进披露 skill；内容综合当前源码、器件库、质量门与公开资料，并移除私人路径和个人工作流信息。
- **Skills 包门**：`skills/` 纳入 source manifest；冻结包和源码包消费门都验证五个入口、引用完整性、UTF-8、单层 references 与私人路径排除，故障注入覆盖私有路径、断链和未链接资料。
- **JSON 与依赖收敛**：输入只接受严格 JSON，改用 Python 标准库解析；删除 config-library 及 JSON5、YAML、TOML 等传递依赖，源码运行时不再需要第三方 Python 包。
- **多器件库合并**：`--library` 接受多个 XML 文件和目录并可重复填写；目录递归扫描 XML，输入稳定去重，同名器件冲突直接报错。
- **源码发行简化**：发行包删除 requirements、wheelhouse 和依赖准备脚本；源码门在空虚拟环境中以 `-I -S` 运行，并验证严格 JSON 与文件、目录混合器件库。
- **离线源码发行**：压缩包保留仓库 `src/` 名字，加入目标平台 CPython 3.10～3.14 固定版本 wheelhouse、源码部署说明和逐文件 SHA-256 清单；源码运行直接使用包内 Node.js 与 ELK。
- **源码消费门**：CI 从解压包创建空虚拟环境，以 `--no-index` 安装包内依赖并通过 `python src` 生成 SVG；故障注入覆盖源码篡改和 wheel 缺失，冻结程序门仍独立执行。
- **五件套迁移**：按当前用户根规则增加 `project-worklog`，预加载、设计笔记、changelog、目标和工作记录统一纳入仓库。

## 2026-08-14

- **四件套统一**：项目入口固定为 `project-preload-skills`、`project-design-notes`、`project-changelog`、`project-goals`，旧的 `python-project-*` 目录已迁移并删除。四件套加入版本控制，克隆仓库后可以直接运行统一检查器。
- **整数列等级**：`layout_column` 只接受整数；较小值靠左，较大值靠右，相同值尽可能共列。数值是顺序而非绝对列号，省略时不增加主观约束，连接方向冲突时保持边向右。
- **列等级门禁**：Agent schema 11 分别报告同等级错位与相邻等级逆序；覆盖不同支路深度、输入逆序、未填写、不同器件、远距整数、同等级因果冲突和反向等级冲突，并注入整列错位与等级逆序故障。
- **等级计算效率**：同等级节点收缩为约束节点，相邻等级只增加一条次序边；一次最长路径扫描完成计算，复杂度为 `O(V + E + L)`。4096 个不同等级的回归测试总计 0.596 秒。
- **冻结包独立门禁**：发布包补入线性、密集、512 时钟与非对称合流四个分层样例；冻结 smoke 从可执行文件所在的解压根加载资源，并直接限制非对称样例的总拐点，禁止借仓库 checkout 补齐缺失输入形成假通过。
- **两拐点逃逸**：固定端点的路线比较无法发现需要移动整条上游链的折线；新增零入度独占链整组端口同轴候选，`div_b → sel[1]` 从两个航点改为零航点，全图总拐点由 4 降为 2。
- **质量检查修正**：Agent schema 9 增加独占链可避免拐点；故障注入移动完整上游链并要求检查拒绝。候选重叠与穿线改为比较具体对象集合，禁止新错误替换旧错误后靠相同计数通过。
- **通用性证据**：覆盖 mux 输入镜像、实例换名、JSON 逆序、外部器件改 title 与尺寸、12 个性质种子以及 1024/2048/4096 压力配置；共享父节点不属于完整独占链，不能因局部少拐点破坏公共首纵线。
- **v1.0.0 功能范围**：删除 extract、reload、旧兼容别名及关联源码、测试、夹具、示例和专档；绘图成为唯一直接主功能。配置、器件库与输出均为必填，输出内容固定为 SVG。
- **旧版保留**：`v0.0.0` tag 与 Release 继续指向提交 `8befc99`，保存旧代码与发行包；新版本从 `v1.0.0` 发布，不移动或覆盖旧 tag。
- **长距末端直线化**：按入度、出度与中间列推导独占上游链，整组换行并重路由边界线；只接受硬几何指标不变差且总拐点严格减少的候选。`gate_a_tap` 从两航点改为零航点，总拐点减少 4，交叉为 0。
- **质量优先级**：端口、穿越、重叠、交叉与拐点优先于路线长度和画布面积；质量检查不再因宽高增加拒绝更少拐点的安全方案。
- **效率分工**：两拐点长距末端由整组换行处理，四拐点以上异常保留单点联合优化；高复用域不执行全局候选扫描。512 生成 0.825 秒，4096 预算调整为 30 秒。
- **v1 静态包检查**：源码 295 项通过；Windows v1.0.0 ZIP 解包后隔离 PATH，直接入口、9 种输入格式、任意输出后缀、默认圆弧、复杂配置和 512 时钟压力配置通过。

- **远端源副本**：零入度逻辑源的目标端口轴存在由局部间距、器件尺寸与净空共同证明的远距离分簇时，以一维 L1 中位数设施动态规划比较单源长主干与多个渲染别名；仅复制显示器件，不增加逻辑节点或边，中间和末端器件禁止复制。
- **源副本门禁**：Agent schema 8 增加非源副本、闲置副本、器件身份漂移、逻辑边漏配/重复、可合并冗余副本及服务代价检查；冻结包 512-clock smoke 明确要求 1046 个逻辑节点对应 1048 个物理器件，`xtal_0` / `xtal_1` 各两个显示锚点，边仍为 1300。
- **联合坐标优化**：节点纵坐标与正交路线在同一支配目标中计算，只接受总拐点严格减少且端口、碰撞、异网重合、交叉、主干、面积和边界均不退化的候选；共享根网、多输出网和扇出源不允许逐边移动破坏整体主干。

- **汇聚顺序**：层内重心排序后增加固定目标端口父节点的稳定优先级投影，覆盖两侧长短互换的非对称 mux 汇聚；局部两折输入若存在无碰撞、无交叉的可见通道路线，不允许保留外凸并穿过兄弟输入。
- **共享主干**：源侧通道统一以源节点和源端口为身份，目标簇只影响目标侧分支；长边简化与全局 refinement 必须保留公共首纵线，禁止形成无依据的 A/B/A 主干。共享 PLL 等全局网按整体主干评估，不能逐边换取虚假的短路线。
- **机器门禁**：Agent 报告升至 schema 7，增加同目标输入交叉、可避免局部汇聚交叉、微段候选惩罚和主干碎裂硬失败；两折/四折故障注入、两种镜像最小反例及 12-seed 性质语料进入回归。
- **示例**：增加 `20-asymmetric-merge-route-bulge.json/.svg`，专门展示一侧多一级器件、另一侧复用时的固定端口无交叉汇聚。

## 2026-08-13

- **布局闭环**：层内排序改为交替重心扫描，消除末层 A-B-A 扇出交错；汇聚节点按根祖先集合与汇聚代数形成约束队列，并以 ASAP/ALAP 可行区间补充必要层深；根与残余子域按共享关系排序，只在根集合可分离时重排，避免在真实交织网络中以局部收益换取更多全局交叉。
- **源与主干**：跨度覆盖顶部路线的可分离根从顶部消费轴进入；同源目标按几何间隔自动形成局部主干。Agent 指标区分合理分组与碎裂，并统计根消费域夹杂数量。
- **拐点与端点**：单父末端在相邻节点非重叠约束内投影到精确端口轴，消除亚像素微线段；末层交叉增加独立结构指标。全边枚举两拐点候选会导致 4096 压力图超时，已拒绝该二次复杂度方案，仅保留空间索引和结构排序内的优化。
- **覆盖**：新增 17 末端扇出顺序、18 非对称汇聚列、19 分散根扇出三个通用示例；基线分别由 1/8/10 个交叉降至 0/7/0，拐点由 10/28/28 降至 8/28/28。

- **布局**：多源节点不再固定堆在左上方；按下游端口纵轴的加权中位数放置，并在可行层内投影到无重叠位置。内部保留完整的确定性候选比较，按硬错误、异网重叠、源诱发交叉、折线和可见面积选取。
- **紧凑度**：路由完成后按实际使用的层间纵向通道重新着色并整体压缩右侧层；以可见器件和文字包围盒计算有效空白，新增可见空白面积、填充率、可避免层间间隙指标。生产样例的可避免层间间隙必须为零。
- **质检根因**：同高端口的浮点尾差曾把直线候选误识别为斜线，进而虚报器件碰撞并保留多余折线；候选在障碍判断前统一正交坐标。性质语料和故障注入覆盖该问题。
- **决议**：正交路由只依据输入拓扑、器件库几何、端口和可见文字包围盒计算；禁止按示例名、节点数量或固定器件组合特判，也禁止生成后校准坐标。预分配通道与实际路由使用同一确定性排序，同一源端口允许共享主干，不同源网禁止共线重叠。
- **质检**：Agent 门禁新增端口零偏差、首末水平逃逸、器件与文字穿线、歧义重叠、锯齿、可避免折线、可避免交叉和可避免外绕；“可避免”采用障碍、重叠、交叉、折线、距离的支配关系判定，不能用更短但更乱的候选误判。
- **覆盖**：除固定的简单、中等、512/1024/2048/4096 时钟示例外，增加长名称、高交叉、综合折磨样例，以及固定种子的随机拓扑和变异器件库性质测试。测试数据只证明通用约束，不参与生产规则选择。
- **发布**：`draw` 仍只生成 SVG 内容；冻结包只携带 Node.js 与 ELK，不依赖 Chrome/Chromium。发布门禁从压缩包解压后隔离运行，并覆盖任意输出后缀、所有 configlib 输入格式、自定义器件库和 512-clock 压力图。

## 2026-08-12

- **决议**：`draw` 固定写入 SVG XML，`--output` 后缀不再表示格式；移除 PNG 分支、Chrome Headless Shell、浏览器发现与 PNG 门禁。即使文件名是 `.png` / `.drawio` 或无后缀，内容仍必须是 SVG。
- **闭环根因**：远程 Release 包在干净 Ubuntu 22.04 中的 SVG 成功而 PNG 失败；Chrome 151 缺少整组动态库，且安装 Ubuntu 16.04 库后仍要求 `GLIBC_2.25` / `NSS_3.30`。因此不再将数百 MiB 浏览器伪装成自包含图片依赖。
- **决议**：`draw` 只公开输出 `.svg` / `.png` 成品图片；`.drawio` 是可编辑工程格式，不再属于 JSON 生图契约。源码与 frozen executable 均必须早期拒绝该后缀。
- **修复**：器件顶点的 HTML 图形模板查找必须传递本次 `--library`；禁止自定义 title 只采用库尺寸却因回落默认库而渲染成矩形。
- **修复**：SVG/PNG 画布范围按节点、全部线端/航点、分支点和 HTML label wrapper 的并集计算，禁止仅按节点矩形导致底部路由被裁切；冻结门禁新增 512-clock 坐标包含检查。
- **决议**：同一源端口的一对多连线共用首个纵向分发主干，每个目标保留独立横向支线；Agent 指标只统计源引线后的第一个纵段，禁止把后续跨层纵段误报为主干碎片。
- **决议**：跨线默认值为 `arc`；原生 SVG 在真实异网交点绘制圆弧桥，`gap` / `sharp` / `none` 仍由参数选择。
- **决议**：`draw` 输入的 `kind` 直接、唯一对应 `--library` 中的器件 title（如 `mux2` / `mux3` / `pll2`），禁止按已连接端口数量猜型号。多输入 `source` 是稀疏映射，允许只连接任意一个有效端口；回归覆盖 mux2 仅 0、仅 1、两路全连。
- **质检**：冻结程序必须覆盖全部公开图片格式 `.svg` / `.png` 及可编辑 `.drawio` 输出。SVG 直接检查尺寸、节点数、边数与端点；PNG 必须完整解码、尺寸与 SVG 一致且非空白；只验扩展名、文件存在或 PNG 签名不算通过。
- **修复**：Linux staticx 冻结程序查找同级 `runtime/` 时优先使用 `STATICX_PROG_PATH`；禁止使用指向临时解包目录的内层 `sys.executable` 作为发布根目录。
- **修复**：运行时获取阶段不再要求当前 Chromium 在 Ubuntu 16.04 构建容器执行成功；该容器只负责旧 glibc Python/staticx 构建。探针结果写入 manifest，真正的 PNG 可执行性由发布 runner 上的解压后、隔离 PATH frozen smoke 阻断。
- **决议**：发布附件只提供完整压缩包；压缩包内置固定版本 Chrome Headless Shell、Node.js 与 ELK，PNG 和质量布局不得依赖宿主机浏览器或 Node。发布门禁必须从压缩包解压，并隔离宿主 PATH 后运行冻结示例。
- **决议**：原生 SVG 预览的 `foreignObject` 固定在 `mxGeometry` 原点，draw.io HTML `(2,7)` 内容偏移在视口内部施加，禁止把左侧端口移出视口。布局坐标统一按 4 位小数契约序列化，禁止 `g` 格式降低线端精度。
- **决议**：`example/draw.json` 采用最小通用输入，只写 `kind` 与必要的 `source`；`component` 和 `*_kind` 均为可选字段。每个器件必须提供非空字符串 `kind`，即使显式填写 `component` 也不能省略。

## 2026-08-11

- **决议**：公开 CLI 使用短子命令 **`draw`**（JSON → draw.io/SVG/PNG）、**`extract`**（draw.io → JSON）、**`reload`**；`json-to-drawio`、`drawio-to-json`、`run` 仅为隐藏兼容别名，不出现在根帮助。
- **决议**：自动布局不按节点总数硬切换。选择器使用源端口扇出分布、骨干移除后的剩余连通域、长边跨层负载和层间边对工作量；高复用网络采用确定性域分解，简单网络保留全局 ELK。所有位置和路由由当前拓扑、器件尺寸与命名端口一次计算，禁止生产后坐标校准。
- **决议**：布局质量检查属于 Agent 的测试/skill 环境，不新增公开 QA 子命令或生产修补阶段。统一几何分组扫描为默认质检算法，全对扫描仅作显式差分 oracle。
- **决议**：本项目每轮源码或文档修改通过相应门禁后，自动读取并执行用户根 **`github-upload`** skill，提交并推送；上传失败必须明确披露。

## 2026-06-23

- **决议**：**mux2～6** 移除 **`sel`** 属性与梯形顶中向上的选择信号竖线/文字；库 **object** 仅保留 **`name`** + **`label`**。旧图 **reload** 后 `sel` 不再写入模板 schema。

## 2026-06-22

- **决议**：**source** / **pad** 归为时钟源大类：库 **object** 写入 **kind=source**、**source_kind** 为 **source** 或 **pad**（不可编辑、仅内部）；**run** 原样导出。见 **json.md**、**drawio-lib/README.md**。

## 2026-06-22

- **决议**：**div_gate** 更名为 **cpu_gate**，外形改为**模块型矩形**（框内模块类型名 + 输出端口名 `hclk_en` / `hclk` / `clk_arm_core`）；归入 **分频器** 大类。通用约定写入用户根 **drawio-module-type-component**；`FanoutComponent` 增 `output_overlays`。

## 2026-06-20

- **决议**：**div / div_n / dto / dto_n / source / 全部 cell** 实例名与图形间距收紧：新增 `INSTANCE_NAME_PULL_COMPACT_PX=10`（累计上移 10px，`cell_h` 与端口不变）；dto 族取消原 `LOOSE` 4px padding。见 **drawclock-drawio-pitfalls**。

## 2026-06-19

- **决议**：图形库选择框实际收窄到 **40px**：普通器件、mux、clock、from 的库条目 `w` 与 `mxGeometry width` 均为 **40**；HTML/SVG label 从百分比画布改为固定像素 `width:Wpx;height:Hpx`，配合 `overflow=visible;resizable=0` 让实例名/频率等文字在选择框外完整显示。
- **决议**：图形库画布策略改为 **`overflow=visible` + `resizable=0`**：允许实例名等文字超出选择框完整显示，禁止自由拉伸以避免固定像素文字、图案与 `points` 端口漂移；自动布局只按 `mxGeometry` 选择框避让，脚本排图须额外给框外文字留白。见 **drawclock-drawio-pitfalls**。
- **决议**：**run** / **reload** 改为器件库驱动、无器件名硬编码：**run** 从 **`-l`** 器件库解析端口与 **kind**，图中 **object** 属性原样进 JSON（含 **freq** 等，不做换算或默认补全）；多输入 **source** 为 dict、多输出 **target** 为 dict，接多路输出上游写 **`名[序号]`**；**from** 仍须同名 **clock** 且不进 JSON。**reload** 仅换库模板与默认宽高，保留图中已有属性，不注入 **pll_kind** 等默认值。
- **决议**：库器件 **wire** 更名为 **from**（图形不变，仅保留右端输出端口）。**from** 须与某个 **clock** 同名，逻辑输入继承该 **clock** 的上游；导出 JSON 不含 **from**，下游 **source** 经 **from** 折叠为同名 **clock** 的上游。见 **rule.md**、**drawclock-drawio-pitfalls**。
- **决议**：**clock** 默认格恢复 **120×72**（与标准器件同宽）：左右各 **37px** 留白供长 **name**，方波+引线居中；端口在引线左端 **(37, y_lo)**。
- **决议**：`src/` 采用正规模块解析：**`pyproject.toml`** 配置 **`package-dir` + `py-modules`**、pytest **`pythonpath = ["src"]`**；**删除** `src/` 内及测试中的 **`sys.path.insert`**。入口为 **`python src`**；**唯一** CLI 文件 **`src/__main__.py`**（**删除**并列 **`drawclock.py`**，**禁止** `__main__` 转调另一入口脚本）。**仍无 `__init__.py`**（CLI 应用、非可导入库）。约定写入用户根 **`python-project-ai`**「目录与入口」。

## 2026-06-18

- **决议**：**or / nor / xor / xnor** 门体与 **and** 共用 D 形骨架（顶边 + 右半圆 + 底边），左竖线改为椭圆弧 `A rx ry 0 0 0`（`rx=arc_x−left_x`，最凸点 x=`arc_x`）；输入引线水平接到 `_or_left_arc_x_at_y` 算出的弧上交点。见 **drawclock-drawio-pitfalls**「OR 族 path 真源」。
- **决议**：改图形库器件外形/端口后，**强制**回写 **drawclock-drawio-pitfalls**（「改完必回写 skill」节）；**session-manifest** Agent 维护义务已列入该步。
- **决议**：接入 **GitHub Release 滚动自动发布**（push `main` → Ubuntu 16.04 PyInstaller → frozen example 门禁 → 覆盖 `v{version}` tag 与 Release 附件）；配置见 **ubuntu-pyinstaller-release**（无 staticx，仅 Linux 两类附件）。
- **决议**：项目运行入口合并为根脚本 **`drawclock.py`**；用户向功能为 **`run`**（原 `src`，生成 `clock-tree.json`）与 **`reload`**（刷新旧图）。`src/` 与 `reload/` 保留为内部模块目录，旧 `__main__.py` 仅兼容转调根脚本；README、example 与 CLI 测试以 `python drawclock.py run|reload` 为准。
- **决议**：发布压缩包内源码参考目录命名为 **`source/`**；原仓库 `src/` 在包内映射为 **`source/drawclock/`**，与 **`source/reload/`**、**`source/pyproject.toml`** 同级。

## 2026-06-09

- **决议**：**`json.md`** 标题 **`# JSON`**；示范**一句**（**以下为示范。**）；**不**写 **example/**、**src**、CLI（发行包与 **example/tools** 互不可见）；规则只在 **`json5`** **`//`** 内。见 **design-notes** **json.md 写法**。
- **决议**：**`json.md`**：**示范**标题下**一句**；样例未展示的边界（**wire**、**freq** Hz、**pll2**、**`[序号]`**、mux）写在 **`json5`** **`//`** 内；**不**写 **键=name**、**`-i`**（CLI）、块外导语段；无字段表。见 **design-notes** **json.md 写法**。
- **决议**：**`rule.md`** 定稿：短段画布规则（库图形可混注释、实例名、连线、**clock** 后缀、**wire** 跨图）；见 **design-notes** **rule.md 写法**。
- **决议**：**`json.md`** 违例根因收口：Agent 未走预加载 **2–8**、误读 **doc-surface-roles-zh**「字段表」为必建表、用户口语「每个参数注释」覆盖删掉检验。回写用户根 **doc-prose-deletion-test-zh**（**json.md** 专节）、**doc-expression-optimization-zh**、**doc-surface-roles-zh**、**agent-codegen-self-review**、**agent-project-preload**；**design-notes** 增 **json.md 写法**；**session-manifest** 增口语窄任务条目。
- **决议**：用户向专档**禁止** `[…](*.md)` 互链；**rule** / **json** / **example** 各文自洽；**design-notes** 分工表去掉「一句链专档」；与 **forbidden-doc-comment-vocabulary**「点名其它 Markdown」一致。
- **决议**：**`json.md`** 按 **doc-prose-deletion-test-zh** 删掉检验：删样例已表达的 **键=name**、**下游 source**、**无 target**；保留样例未覆盖的 **JSON 无 wire**、**freq Hz / 图后缀导出数值**。
- **决议**：防 Agent 漏做删掉检验：**doc-prose-deletion-test-zh** 增「评审/问答须 Read」与 **`json.md`** 代码块注释粒度；**agent-codegen-self-review** 增「用户向 Markdown（删掉检验 · 强制）」；**agent-project-preload** / **python-project-session-manifest** 增问答触发与文档改动回合末强制自查。
- **决议**：**python-project-session-manifest** 预加载顺序对齐 **`agent-project-preload`**：**doc-surface-roles-zh**、**forbidden-doc-comment-vocabulary**、**markdown-authoring-zh** 升为每会话起手 **2–4**（不再压在「写 Markdown 时」可选项）；增「为何 Agent 常漏读强制 skill」节（列表≠Read、无 alwaysApply、任务窄化）。
- **决议**：用户根 **forbidden-doc-comment-vocabulary** 增禁词 **须在**、**旁标**、**可跟**。
- **决议**：**`rule.md`** 按文档编辑套装重写：只写画布连线与实例名，**不**重复 **`json.md`** 字段；**禁**多专档外链与 **拓扑** 等禁用词；**`drawio-lib/README.md`** 仅一句链 **`rule.md`**。
- **决议**：新增根目录 **`rule.md`**（画图连线规则）；**design-notes** 分工表增一行；**`json.md`** 仍专写导出字段，**`drawio-lib/README.md`** 仍专写库用法，三者不重复正文。
- **决议**：根 **README** **不写** **example**、**`update.bat`** / **`test.bat`** / **`pack.bat`** 等（见 **example/README.md**、**PACKAGING.md**、**tools/README.md** 等专档）。
- **决议**：新增用户根 **`doc-surface-roles-zh`**（体裁定位）；与 **markdown-authoring-zh**、**doc-prose-deletion-test-zh**、**doc-expression-optimization-zh** 组成文档编辑套装；改用户向 Markdown **强制** Read 并维护 **design-notes** 分工表。
- **决议**：根 **README** **src** / **reload** **仅参数表**；**不写**表下 JSON / 器件库 / reload 行为；**不写**命令行演示（入口见 **`--help`**）。
- **决议**：根 **README** **不链**子文档（**`json.md`**、子目录 README、**`PACKAGING.md`** 等；除非用户明确要求）；各专档自洽。
- **决议**：根 **README** **不写**仓库目录树（除非用户明确要求）；**`##` 标题**只写主题名，**禁止** **`主题：说明`**（说明进正文）。
- **决议**：**`docs/clock-tree-json.md`** 迁至根目录 **`json.md`**；删除空 **`docs/`**；README 链到 **`json.md`**。
- **决议**：用户向 README（含 **`drawio-lib/README.md`**、**`example/README.md`**）**禁止**提及 **skill** 或 Agent 专档路径；口径写入用户根 **`forbidden-doc-comment-vocabulary`**、**`python-project-ai`**。
- **决议**：用户向 README **禁止**写作者私人工作区/IDE 配置状态（如 **工作区已配置 `customLibraries`**）；draw.io 形状库加载统一写 **文件 → 导入** **`drawclock.xml`**。
- **决议**：**用户向文档各司其职**（分工表见 **python-project-design-notes**「用户向文档分工」）：**`json.md`** 专写 JSON 字段与导出语义；**`drawio-lib/README.md`** 只写库用法与器件属性（图+表），**禁止** JSON 导出描述与外形 prose；根 README / example README 不重复 JSON 规则正文，只链 **`json.md`**。
- **决议**：**`drawio-lib/README.md`** 属性表仅 **属性｜说明** 两列；器件小节无功能/外形副标题。
- **决议**：**`drawio-lib/README.md`** 删「通用属性」节；有 **`images/*.svg`** 则不写端口/中心字/间距等外形 prose；**`name`** 说明只写 **实例名**（不写「留空不显示」）。
- **决议**：根 **README** / **example/README** 不重复 **`json.md`** 规则正文；example 删「JSON 要点」专节，改链 **`json.md`** + 样例路径。

## 2026-06-05

- **决议**：**mux2～mux6** 去掉 **`in0_label`…** 可编辑属性；输入旁固定显示 **0…N−1**，`clock-tree.json` 中 mux `source` 键也固定用这些序号。reload 会移除旧图残留的 `in*_label` 属性。
- **决议**：**pll2** 使用专用外形：上下平行线加长，中心 **`pll_kind`** 位置保持原 pll 靠左位置；右缘两路输出仍落在 **>** 折线，并在端点左边固定显示 **0 / 1** 序号。

## 2026-06-04

- **决议**：**clock-tree.json** 去掉 **`target` / `targets`**，连接只写在下游 **`source`**；图中 **gate/div/dto/inv/mux** 等输出端口允许多路连接（与 pll/source 一致）。文档 **`docs/clock-tree-json.md`**、示例 **`example/out/clock-tree.json`** 同步。

## 2026-05-29

- **决议**：**pll** 改为 **左入右出**（右端仍可多路）；外形左侧凹口由上下线段闭合、中点为输入；中央 **`pll_kind`** 区加宽约 4 字符；**`clock-tree.json`** 对 pll 增加必有 **`source`**。示例 **fig2** 中 **wire_a→pll_main**、**osc_mux→pll_m2a/b**。
- **决议**：**pll** 图形库新增 **`pll_kind`**；**reload** 经 **`src/drawio_library.reload_object_attrs`** 补属性并重写 label 模板，**不烘焙** `%pll_kind%`（与 freq/name 一致，由 draw.io 替换）。见 **drawclock-drawio-pitfalls**「pll_kind 与 reload」节。

## 2026-05-25

- **决议**：**reload** 的 object 使用库 **label 模板 + `placeholders=1`**（保留 `name`/`freq`/`in*_label` 属性值），不再烘焙为 `placeholders=0`，以便 draw.io 双击编辑变量。
- **决议**：**reload** 在更新方框宽高后，对两端均为器件库的边调用 **`resolve_edge_style`** 重算端口附着比例（避免仍用 `exitX=1` 等旧 bbox 值而离端口有空隙）；**航点**保留。
- **决议**：**reload** 用 **`reload_object_attrs`** 按库模板重绘 label（避免旧 `viewBox` 与拉宽后的方框不一致导致图案被拉伸）；**width/height** 取库默认，保留 **x/y**。
- **决议**：**example** 的 `fig1.drawio` / `fig2.drawio` 由 `build_example_demo.py` 以 **压缩 diagram** 写出；reload 产物同为压缩；pytest 验收 `example/out/*-reloaded.drawio` 无内嵌 `<mxGraphModel`。
- **决议**：**reload** 支持 draw.io **压缩 diagram**（含 `.drawio.svg`）；**输入为压缩则输出仍为压缩**（未压缩 `.drawio` 保持子节点 `mxGraphModel`）。`compress_diagram_payload` / `decompress_diagram_payload` 在 `drawio_decode.py`。
- **决议**：**拓扑校验**对 **wire** 报左右端悬空（如「左端未接上游、右端接了 gate0」），不再仅报下游器件「输入/输出未连接」。
- **决议**：**`src` 的 `-o`** 为 JSON **文件路径**（非目录）；`-l` / `--library` 必填、无默认。
- **决议**：**example 变更必验 reload**：`example.bat` 增第 5 步 `pytest`（`test_reload.py` + example 用例）；`test_example_out_reload_preserves_input_waypoints` 校验 `example/out/*-reloaded.drawio` 与输入图航点一致。
- **决议**：**pll_main 一分二航点**以用户手改 **`example/fig2.drawio`**（边 25/26）为准：每边 **2** 个 mxPoint，汇流柱 **x=170**，`(170,140)→(170,80|200)`；记入 **`~/.cursor/skills/drawio-edge-waypoints/SKILL.md`**、**`example/refs/pll_main_fanout_waypoints.json`**；`build_example_demo.py` 的 `_connect_pll_main_fanout` 与之对齐。
- **决议**：**`clksrc` 改名为 `source`**，去掉中心 SRC 字；**`pll` / `source` 导出 `targets`[]**；**mux `source` 键为标签 `0`/`1`…**；**wire 仅跨图、不进 JSON**；示例改为 **`fig1.drawio` + `fig2.drawio`**，`example.bat` 串联库→图→src→reload。
- **决议**：图形库新增 **`clksrc`**（已更名为 **source**）：圆 + 正弦波、仅右端口。
- **决议**：新增 **`docs/clock-tree-json.md`**：`clock-tree.json` 各 `kind` 节点字段、wire 合并与引用规则；README / example README 链到该文档。
- **决议**：**reload** 不再按新库 `points` 重算连线 `exitX`/`entryX`（格宽未变时会把端点往中间拽偏）；仅 `finalize_edge_style` 补全 `exitPerimeter=0` 等，保留原附着比例。
- **决议**：CLI 拆为 **`src/`**（仅 draw.io → `clock-tree.json`，按器件库校验；忽略非库图形）与 **`reload/`**（旧 draw.io + 新器件库 → 新 draw.io，保留坐标与非库内容）；取消 `encode`/`decode` 子命令与 `drawio-layout.json` 主流程。
- **决议**：`clock-tree.json` 中 wire 由 `connections` 改为 **`source`（左端至多一个器件名）** + **`targets`（右端器件名列表，可多个）**；encode 时左端重复连接报错；不再接受 `connections` 字段。
- **决议**：图形库默认格加宽——一般器件 `W` **80→120**（`side_pad` 两侧各 **40px** 给实例名）；clock 左留白 **60→80**，默认格 **240→260**；图案仍 **DESIGN_W=40** 居中。

## 2026-05-24

- **决议**：decode / encode 布局写入时从 `drawclock.xml` 补全器件库 **html=1** 样式；仅含 `drawclockType` 的旧 `.drawio` 在 draw.io 中不显示图案。
- **决议**：修复 `drawio_graph._parse_points` 仅解析首个端口导致 mux 多入连接失败；往返测试覆盖 **图↔JSON**（`test_json_encode_decode_roundtrip`）。
- **决议**：`example/demo.drawio` 扩展为全器件类型展示；`scripts/build_example_demo.py` 生成；`example.bat` 含 encode→decode→再 encode 校验。

## 2026-05-22

- **决议**：wire 端口改到图形两端（`side_pad` / `side_pad+DESIGN_W`），不再落在格边 0/W；clock 右侧非对称留空（freq_gap 60px + 文本区 80px），默认格宽 **240**。
- **决议**：自由变形端口错位——改 **`overflow=fill`** + shell 无 min 尺寸（见 pitfalls）。
- **决议**：CLI 拆 **encode** / **decode**：`clock-tree.json` + 可选 `drawio-layout.json` ↔ `.drawio`；decode 须 `--config`、`--layout`、`--library`（`drawio-lib/drawclock.xml`）；往返无损（拓扑与布局 JSON 一致）。
- **决议**：drawclock 画布五条易错点迁入项目 **`.cursor/skills/drawclock-drawio-pitfalls/SKILL.md`**；用户根 **`drawio-component-library-troubleshooting`** 仅保留跨项目概念并指向本项目 skill；`label_overflow` 增 `verify_gap_placeholder`、`verify_no_degenerate_label_tricks` 与 viewBox/100% 断言；改库须 `build_drawio_lib.py` + `test_label_overflow`。
- **决议**：clock 方波缩至与其它器件同宽（40px 格、5 周期）；`viewBox` 与整格一致，修复窄 viewBox 横向拉满导致图案过大。
- **决议**：根因修复——用户根 **`agent-project-init`** 取消 Python 预加载双命名（仅 `python-project-session-manifest`）、骨架分 Python/其它两套、新增「重命名须删旧目录」；**`project-skill-manifest-policy`** 同步；本仓库 **session-manifest** 增「根因与防复发」节。
- **决议**：删除 `.cursor/skills/` 下无内容的重复目录 `project-preload-skills`、`project-design-notes`、`project-changelog`、`drawio-component-library`；仅保留三件套 `python-project-session-manifest` / `python-project-design-notes` / `python-project-changelog`。
- **决议**：拉伸方框后端口错位：`verticalAlign=middle` 使标签居中、`points` 仍按外框比例；全库改 **`align=left;verticalAlign=top`**，集中 **`mxcell_html_label_style_parts()`** + **`verify_mxcell_label_style`**。
- **决议**：文字超出方框被裁：根因为 draw.io 在 **`overflow=fill`** 时外包 **`overflow:hidden`**；全库改 **`overflow=visible`** + 内层 **`min-width/min-height`**；新增 **`label_overflow.verify_label_overflow_policy`** 与 **`tests/test_label_overflow.py`**，改 label/style 须过测。
- **决议**：取消可编辑 **`font_size`**、**`graphic_scale`**；实例名/路号固定 **11px**（`LABEL_FONT_PX`），图案仅随方框拉伸（无 `transform:scale` 占位符）；`<object>` 仅保留 **`name`**、**`gap`** 及器件专用属性。
- **决议**：画布故障排查迁入用户根 skill **`drawio-component-library-troubleshooting`**；删除 `drawio-lib/TROUBLESHOOTING.md`；与 `drawio-component-library` 分工。
- **决议**：JSON 每条增加 `kind`；`example/demo.drawio` + `example.bat` 可运行演示。
- **决议**：全库图案与文字不随方框拉伸；新增 **`font_size`**（默认 11）、**`graphic_scale`**（默认 1）；**`_name` 改名为 `name`**；图案层 `transform: scale` + `preserveAspectRatio=meet`；CLI 解析兼容旧 `_name`。
- **决议**：CLI 支持多个 `.drawio.svg` / `.drawio` 输入，解析连线关系输出 `list[dict]` JSON（`name` / `freq` / `source` / `target` / `connections`）；wire 写入 JSON，`connections` 长度 1 或 2；mux 的 `source` 为 `in0`… 字典；除 wire 外名称须唯一；校验端口与引用器件。
- **决议**：gate 改为右半圆 + 与右圆间隔；去掉 EN；去掉三角尖。
- **决议**：gate 改为左半圆 + 右尖 + 右圆（对齐 inv）；右端口 x=37；EN 仍在上。
- **决议**：inv 右侧反相标记由六边形改为圆。
- **决议**：simple/mux/wire 标签外壳改固定 `width×height` 像素（同 clock）；`overflow=visible` 保图案可见且大 `gap` 不裁 `_name`。
- **决议**：wire 波带 `overflow=fill` + 固定 28px 外层；gate 反相圆右移（`GATE_BUBBLE_X=39`）与左体留间隔。
- **决议**：clock **`freq_gap`** 默认 60（原 30）；库默认宽 114。
- **决议**：wire 恢复专用标签壳（`height:100%` + 固定 28px 波带）；勿复用 simple 的 `min-height` 壳，避免波形被拉高压扁。
- **决议**：clock 波形 grid 居中、`freq_gap` 仅推频率右移；左端口对齐波形左缘；`autosize=0`。
- **决议**：gate 左竖线 + 上下横线 + 右半圆（非子弹头尖）；横向拉长时中间横线随比例变长。
- **决议**：带 `gap` 的器件 style/label 改 `overflow=visible`，大间距时 `_name` 不被方框裁切（mux/simple 与 wire 一致）。
- **决议**：全库 `_name` 改 HTML 绝对定位（11px），缩放形状时不随 SVG 拉伸；mux/clock/gate/inv 等统一。
- **决议**：CSS 内间距占位符改为 `%freq_gap%` / `%gap%`（勿用 `%{…}`），修复 clock 等间隔不生效。
- **决议**：wire 实例名改 HTML + `overflow=visible`，大 `gap` 时不再被裁切。
- **决议**：gate 左体改为子弹头曲线；右圆半径 4→3。
- **决议**：div / dto 中心文字改 HTML 固定字号（同 pll）；÷、DIV、DTO 缩放时不拉伸。
- **决议**：pll 中心 **PLL** 改 HTML 固定字号，缩放时不拉伸。
- **决议**：wire 恢复下方 `_name`；全库 `_name` 默认与库名相同；`images/` 示范图显示实例名。
- **决议**：clock **`freq_gap`** 改为 flex 定宽 spacer（修复间距不生效）；全库 `whiteSpace=nowrap`。
- **决议**：clock 新增编辑属性 **`freq_gap`**（默认 30）；波形 5 周期；PLL 右三角加宽。
- **决议**：clock 6 周期、波形在整格垂直中线；频率 `right:0`；`_name` 与波形同宽对齐。
- **决议**：clock 方波加高加宽、4 周期、左低电平引线；频率间距 30（原 10 的 3 倍）；总宽 92。
- **决议**：clock 仅保留 50% 方波；频率与实例名改 HTML 固定字号；`overflow=visible`、`autosize=1` 避免裁切与文字拉伸。
- **决议**：gate 改为左半圆弧锁存 + 右锥 AND；EN 居中上接、竖线入顶；端口仍在 x=11 / x=33。
- **决议**：pll 改为向右标签形（左开口、上下平行、右尖）；去掉三圆闭环。
- **决议**：pll 改为 VCO / ÷N / PFD 三圆节点与曲线闭环，去掉矩形外框与方角反馈环。
- **决议**：clock 图案改为楔 + 方波 + 空心端点；频率文本左对齐向右延伸；图形与频率默认间隔 10；总宽 71。

## 2026-05-21

- **决议**：gate/div/dto/inv/pll/clock/wire 外形改版：非矩形主导（AND 门、六边形分频、PLL 环、方波终端、波浪 wire）；inv 反相标改为六边形以避免拉伸变扁。
- **决议**：图形库新增 **gate、div、dto、inv、pll、clock、wire**；共享 `simple_geometry` / `simple_component`；div/dto 以图上文字区分；pll 仅右端口、clock 仅左端口、wire 为水平连线段。
- **决议**：新增 **mux3～mux6**（3～6 路输入），共享 `mux_geometry` / `mux_component`；库与 `examples/` 示范一并生成；mux2 几何与端口不变。
- **决议**：**mux2 图形库定稿**（用户确认理想形态）；一体 SVG 缩放、`points` 在梯形端口、`_name`/`gap` 编辑数据、`drawclockType` 在 style、`dy="0.35em"` 等写入用户根 **drawio-component-library**「参考范本」节。
- **决议**：mux2 输入标注 `dy="0.35em"`（字底在端口 y 时下移居中；负 dy 会更偏上）。
- **决议**：mux2 连接点改到梯形端口（trap 相对坐标）；去掉标签内引线；样式加 `overflow=fill`、`autosize=0`，避免缩放时连线与外形错位。
- **决议**：mux2 类型写入样式 `drawclockType=mux2`（编辑数据不显示）；实例字段改为 `_name`、`gap`（编辑数据前两行，适配 draw.io 字母序）。
- **决议**：mux2 梯形水平偏移 `TRAP_X=8`；左引线 (0,y)→(8,y) 在梯形外；`0`/`1` 标签距梯形左缘 `LABEL_INSET_X=6`；右引线仍 (32,y)→(40,y) 与外框点 x=1 对齐。
- **决议**：项目内 skill 只保留三件套目录名 **`python-project-session-manifest`**、**`python-project-design-notes`**、**`python-project-changelog`**；删除重复的 `project-preload-skills`、`project-design-notes`、`project-changelog`（与 `project-skill-manifest-policy` 一致）。
- **决议**：mux2 端口：梯形锚点 + 引线至外框；draw.io `points` 在外框轮廓（`x=0` / `x=1`），五元组第三项 `0`。
- **决议**：mux2 去掉图上 `component_type` 文字；`instance_name` 属性排第一；梯形收窄为 32×64，总宽 40。
- **决议**：mux2 黑白无填充、更高梯形（44×64）；`0`/`1` 与左连接点 Y 对齐。
- **决议**：mux2 梯形改为左长右短；`0`/`1` 在梯形内、连接点右侧；编辑数据属性顺序 `component_type` 第一、`instance_name` 第二。
- **决议**：mux2 外形改为梯形 mux（SVG）；新增 **`in0_label`** / **`in1_label`**（默认 `0`/`1`）；尺寸 88×86。
- **决议**：mux2 新增 **`instance_gap`**（实例名与方框间距，像素，默认 4）；总高改为 76 以预留更大间距。
- **决议**：draw.io **通用**知识迁至用户根 `~/.cursor/skills/drawio-component-library`；mux2 等器件设计留在 **python-project-design-notes**；删除本仓库 `drawio-component-library` skill；`drawio-lib/README.md` 仅保留用法。
- **决议**：mux2 布局：方框正中 `%component_type%`（默认 mux2）；方框外下方 `%instance_name%`（默认空）；总高 68，连接点按方框区域计算。
- **决议**：draw.io 器件制作规范拆为独立 skill `.cursor/skills/drawio-component-library/SKILL.md`；design-notes 只保留 drawclock 产品边界；预加载清单加入该 skill。
- **决议**：库生成后校验加强（禁止 mxCell 子 object、label 转义、JSON/必填字段）；修复 `could not add object for object`（外层 object 包裹 mxCell）。
- **决议**：用户向图形库说明在 `drawio-lib/README.md`。
- **决议**：`drawio-lib/` 仅 `drawclock-components.xml`；mux2 元数据 `instance_name`、`component_type`。
- **决议**：仓库 Agent 三件套；项目名 **drawclock**。
