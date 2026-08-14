---
name: project-preload-skills
description: >-
  drawclock 会话预加载顺序与用过的 skill 记录；与设计笔记、changelog、目标组成四件套。
---

# 会话清单（drawclock）

## 预加载（实质性工作前 Read）

顺序对齐用户根 **`agent-project-preload`**「推荐加载顺序」。**2–5 每会话起手 Read**；不得因任务窄（如「删废话」「改一个词」）跳过。

### 每会话起手（固定）

1. `~/.cursor/skills/project-skill-manifest-policy/SKILL.md`
2. `~/.cursor/skills/doc-surface-roles-zh/SKILL.md`（**必须**；体裁：写什么 / 不写什么）
3. `~/.cursor/skills/forbidden-doc-comment-vocabulary/SKILL.md`（**必须**；交稿前检索禁用词）
4. `~/.cursor/skills/markdown-authoring-zh/SKILL.md`（**必须**）
5. `.cursor/skills/project-design-notes/SKILL.md`（含用户向文档分工）
6. `.cursor/skills/project-changelog/SKILL.md`（口径有疑或刚变更时）
7. `.cursor/skills/project-goals/SKILL.md`

### 改用户向 `*.md` 时（同轮追加）

8. `~/.cursor/skills/doc-prose-deletion-test-zh/SKILL.md`
9. `~/.cursor/skills/doc-expression-optimization-zh/SKILL.md`
10. （**`rule.md`** 或用户要求按本人习惯润色时）`~/.cursor/skills/user-markdown-habits-zh/SKILL.md`

含根 **README**、**`json.md`**、**`rule.md`**、**`drawio-lib/README.md`**、**`example/README.md`** 及 **`Field(description=…)`**。

改 **`json.md`** 时：7 须读到 **doc-prose-deletion-test-zh** **json.md** 节；并 Read design-notes **json.md 写法**（用户口语「加注释」「写示范」不跳过）。

**含评审/问答**：用户问某句是否废话、能否删、是否重复时，**同样走 2–8**，**不得**只读文件凭印象作答。

### 按任务追加

| 任务 | Read |
| --- | --- |
| Python 布局、README/CLI | `~/.cursor/skills/python-project-ai/SKILL.md` |
| Python 注释/docstring | `~/.cursor/skills/python-doc-comments/SKILL.md` |
| 图形库 label/style/points | `.cursor/skills/drawclock-drawio-pitfalls/SKILL.md`（**先于**用户根 troubleshooting） |
| 库 XML、器件结构 | `~/.cursor/skills/drawio-component-library/SKILL.md` |
| example .drawio、双 JSON 往返 | `~/.cursor/skills/drawio-generate-from-config/SKILL.md` |
| 连线 mxPoint 航点 | `~/.cursor/skills/drawio-edge-waypoints/SKILL.md` |
| 跨项目 draw.io 概念 | `~/.cursor/skills/drawio-component-library-troubleshooting/SKILL.md` |
| PyInstaller / 打包 | `~/.cursor/skills/python-pyinstaller-staticx-packaging/SKILL.md` |

### 回合末（用户向文档改动时强制）

若本轮写入或替换任意用户向 **`*.md`**（含代码块内中文注释）：**必须** Read **`agent-codegen-self-review`** 并完成其中 **「用户向 Markdown（删掉检验 · 强制）」** 三节；其它改动仍**建议**读本 skill 做格式自查。

## Agent 维护义务

- 需求、设计或验收变化时，当轮更新 **project-design-notes** 与 **project-changelog**；矛盾以 changelog 最新记录为准。
- 改 draw.io 库：**Read drawclock-drawio-pitfalls** → 改 `scripts/drawio_lib/components/` → `python scripts/build_drawio_lib.py` → `pytest tests/test_label_overflow.py` 等 → `check OK` → **强制回写 drawclock-drawio-pitfalls**（见该 skill「改完必回写 skill」节）；决议级变更同步 changelog。

## 项目内四件套

| Skill | 职责 |
| --- | --- |
| **project-preload-skills** | 本文件（预加载 + 用过的 skill） |
| **project-design-notes** | drawclock 产品与器件设计 |
| **project-changelog** | 按时间的决议 |
| **project-goals** | 当前目标与验收证据 |
| **drawclock-drawio-pitfalls** | 图形库画布五条易错点 + 改后验收（非三件套，专档） |

同一职责只保留一个目录；同伴规范只在 `~/.cursor/skills/`。

## 为何 Agent 常漏读强制 skill

1. **列在表里 ≠ 已 Read**：`available_skills` 与预加载列表只提供路径；无 **`.cursor/rules` `alwaysApply`** 时，规范不会自动注入上下文，全靠当轮是否执行 **Read**。
2. **旧列表把文档套装后移**：曾把 **doc-surface-roles-zh** 等压在第 10 项并写「写 Markdown 时」，易被当成可选；**design-notes** 又排在文档 skill 之前，Agent 只读分工表就动笔，漏掉体裁默认表（根 README **默认不链**子文档）与禁用词自检。
3. **design-notes 不能替代文档套装**：分工表是 drawclock 专档边界；**须在**、**旁标**、**扇出** 等禁词与 **`[…](*.md)` 禁互链** 在用户根 skill，只读 design-notes 仍会违例。
4. **任务描述窄化**：「精简 rule」「改 README 一句」「给 json 加注释」「写示范」类请求若不触发「改用户向文档」分支，Agent 会跳过 2–8 直接改文件。
5. **体裁表误导**：**doc-surface-roles-zh** 专题专档曾写「字段表」而未区分 **`json.md`** 以样例为主体，Agent 为「写全」建 **`## 字段`** 表并与 **`json5`** 双写。
6. **用户口语压过 skill**：「每个参数注释」被字面执行为逐键注释 + 字段表，未 Read **doc-prose-deletion-test-zh** **json.md** 节（口语不放宽删掉检验）。
7. **问答误判为只读**：用户问「这句能否删」「是不是废话」时，Agent 只分析未 Read **doc-prose-deletion-test-zh**，答复口径与改写不一致。
8. **回合末自查标成建议**：**agent-codegen-self-review** 标「建议」时，Agent 改完文档即结束，未对 diff 做删掉检验。

**防复发**：每会话起手 **2–5**；动或**评**任意用户向 `*.md` 走 **2–8** + design-notes 分工表；改 **`json.md`** 叠加 **doc-prose-deletion-test-zh** **json.md** 节 + design-notes **json.md 写法**；文档改动回合末**强制** **agent-codegen-self-review** 删掉检验三节；交稿前 **forbidden** 全文检索；维护预加载列表时 Read **`agent-project-preload`**。

## 目录约定

- 四件套目录名固定为表中四项，不按语言增加前缀。
- 项目类型只影响预加载列表，不改变四件套路径。
- 同伴 skill 只放在 `~/.cursor/skills/`，不在仓库中复制。

## 用过的 skill（追加记录）

- `python-pyinstaller-staticx-packaging`（用户根，PyInstaller + Linux staticx、`tools/pack.sh`、根目录 spec）
- `drawio-component-library`（用户根，含 mux2 参考范本定稿）
- `drawclock-drawio-pitfalls`（本项目，画布五条易错点）
- `drawio-component-library-troubleshooting`（用户根，跨项目概念）
- `project-design-notes`
- `project-changelog`
- `project-skill-manifest-policy`
- `doc-surface-roles-zh`（用户根，用户向文档体裁定位）
- `doc-prose-deletion-test-zh`、`doc-expression-optimization-zh`（用户根，文档编辑套装）
- `agent-project-preload`（用户根，预加载顺序真源）
- `forbidden-doc-comment-vocabulary`（用户根，禁词 **须在**、**旁标**、**可跟**）
- `user-markdown-habits-zh`（用户根，短规则专档段落习惯；已回写「短规则专档」节）
- `agent-codegen-self-review`（用户向文档改动回合末删掉检验）
- `json.md` 违例复盘与 skill 回写（**doc-prose-deletion-test-zh** / **doc-expression-optimization-zh** **json.md** 节、**doc-surface-roles-zh**、**agent-codegen-self-review**、**agent-project-preload**、design-notes **json.md 写法**）
- `python-argparse-cli`（用户根，直接绘图主入口与必填参数）
- `clock-tree-layout`、`api-documentation-contract`、`agent-quality-workflow`（`draw` 输入与测试）
- `github-upload`、`commit-quality-gate`（修改后自动提交与推送）
- `project-benchmark-learning-loop`、`research-summary-maintenance`（布局研究、基准闭环与经验固化）
- `github-release`、`python-pack-github-release`（滚动发布与下载后实包验收）
- `skill-creator`（更新用户根 clock-tree-layout 的反例与评价工艺）
- `verify-fix-repeat`、`skill-lesson-curation`、`agent-project-goals`（重复视觉缺陷、经验归档与目标证据）
- `doc-surface-cli-tool-zh`、`markdown-authoring-zh`（更新 draw 专档）
- `api-documentation-contract`、`python-doc-comments`、`doc-surface-topic-page-zh`、`doc-surface-subdir-readme-zh`（`layout_column` 配置接口、源码说明与示例文档）
