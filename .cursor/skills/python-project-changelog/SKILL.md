---
name: python-project-changelog
description: >-
  本仓库：按时间记录要求与决议；最新在上；矛盾以最新为准。
---

# 变更记录

（规则见 `~/.cursor/skills/agent-project-changelog/SKILL.md`。）

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
