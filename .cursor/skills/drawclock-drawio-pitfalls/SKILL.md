---
name: drawclock-drawio-pitfalls
description: >-
  drawclock 图形库画布易错点与改后验收。脚本生成 .drawio、双 JSON 往返、边附着见
  ~/.cursor/skills/drawio-generate-from-config。
---

# drawclock 图形库 · 易错点与验收

本项目每轮源码或文档修改通过对应测试后，自动读取并执行用户根 `github-upload` skill，提交并推送到 GitHub；上传失败必须明确披露。公开 CLI 只有直接绘图入口，无子命令。

脚本生成示例图、**clock-tree.json** + **drawio-layout.json** 还原、**exitPerimeter=0** 等：Read **`~/.cursor/skills/drawio-generate-from-config/SKILL.md`**。
**pll_main 一分二航点**（用户手改 fig2 范式）：**`~/.cursor/skills/drawio-edge-waypoints/SKILL.md`**、**`example/refs/pll_main_fanout_waypoints.json`**。

## 强制要求（当前）

| 要求 | 做法 |
| --- | --- |
| **框外文字可见** | mxCell **`overflow=visible`**；HTML shell 也保留 `overflow:visible`，允许 `%name%` 超出选择框显示 |
| **禁止自由拉伸** | style 必含 **`resizable=0`**；用固定选择框避免图案、文字、`points` 被用户拉伸后互相漂移 |
| **端口与图案对齐** | 图案层 `absolute` 固定像素画布 + SVG `viewBox=设计格` + `preserveAspectRatio="none"`；因禁止拉伸，画布只填充固定格 |
| **小选择框** | 当前默认格宽 **40px**；`mxGeometry` 高度 = 图形底缘（`BODY_Y + body_h + body_pad_bottom` 或 mux `mux_h`、clock 波形底等），**不含** `NAME_H` / `MAX_INSTANCE_GAP`；实例名 `%name%` 从框底起经 `overflow=visible` 显示在框外 |
| 实例名间距 | 默认与 **cell** 一致：`MUX_BODY_PAD_BOTTOM=0`、`INSTANCE_NAME_GAP_PX=0`、`MAX_INSTANCE_GAP=8`；`name_block` 顶边对齐图形区底缘。**from / clock / clk_phase_sel / mux2～6** 使用 `INSTANCE_NAME_GAP_LOOSE_PX=4`（`name_block` 的 `padding-top`），略增大实例名与图形间隙。**div / div_n / dto / dto_n / source / gate / inv / 全部 cell** 使用 `INSTANCE_NAME_PULL_COMPACT_PX=10`：在保持 `cell_h` 与端口不变的前提下，将 `name_block` 顶边上移 10px（相对图形区底缘），缩小图形与 `%name%` 间距（dto 族无 LOOSE padding） |
| **标准行距** | `simple_geometry.STANDARD_ROW_PITCH`：以 **div** 为参考，图形顶（`BODY_Y`）→ 实例名底（`INSTANCE_NAME_PULL_COMPACT_PX` + `NAME_H`）+ `STANDARD_ROW_EXTRA_PAD=2`（默认 **56px**）。**mux** 的 `INPUT_PITCH` 必须等于此值；`trap_h = max(TRAP_MIN_H, span + BODY_H)`，使最上输入口的 `cell_y` 落在 `BODY_Y + BODY_H//2`（与 gate/div 等端口行对齐），多路 mux 可按行叠放标准器件 |

### 选择框与框外文字

- **`cell_h` / `mxGeometry height`** 只包裹图案带（含端口引线所在高度），**不**为实例名预留 `NAME_H` 或 `MAX_INSTANCE_GAP`。
- **`name_block` 顶边** 仍按图形区底缘减 `INSTANCE_NAME_PULL_COMPACT_PX`（紧凑族）等既有公式定位；**仅** `mxGeometry` 高度缩到图形底，实例名经 `overflow=visible` 在框外显示。
- 当前策略接受框外文字的代价：选中、自动布局、对齐分布只理解 `mxGeometry`，不理解框外文字真实占用。
- 自动布局或脚本排图时须靠项目布局规则额外留白，不指望 draw.io 避让框外文字。
- 禁止回退到 `overflow=fill`：它会让框外文字被 draw.io 外包层裁切。
- 禁止允许拉伸：固定像素文字和小选择框策略下，一旦用户拉宽/拉高，`points` 会按新框比例解释，端口容易离开图形。

## 中心符号（÷、DTO 等）勿放进 SVG

### 正确行为

- **div / div_n / dto / dto_n**：中心字用 **`label_html._overlay_on_cell`**（HTML `<span>` + `transform:translate(-50%,-50%)` + 固定 `font-size`），**不**画在 SVG 内。

### 模块型器件（cpu_gate 等）

矩形模块外形见用户根 **`drawio-module-type-component`**。**container 顶栏** + 主体区按 **mux 标准行距**（`STANDARD_ROW_PITCH`）排输出；端口名**右对齐**；宽度按最长端口名计算。骨架：`ModuleComponent` / `module_geometry.py`。

### 为何 SVG `<text>` 会反复偏

| 误区 | 后果 |
| --- | --- |
| ÷ 写在 `body_svg` 的 SVG `<text>` 里 | draw.io 导出常**丢弃** `dominant-baseline`；`y` 当基线用，竖直偏；若误开拉伸，字号还会随 SVG 变形 |
| 用 **`W/2`** 当 ÷ 的 x | 门体在左侧，÷ 会偏到整格中央（三出圆之间） |
| 设计格 x **未加 `side_pad_x`** | ÷ 相对门体整体左移约 `(cell_w - DESIGN_W)/2` |
| 手调 SVG x 像素 | 默认 40 格看似正确，一拉变形或换 draw.io 版本又错 |

### div / div_n ÷ 的 x 真源（设计格）

```text
symbol_cx = 六边形外接框水平中心（见 div_component）
cell_x    = side_pad_x(cell_w) + symbol_cx
cell_y    = body_mid_y + DIV_SYMBOL_Y_OFFSET
```

实现：`div_component` 的 `center_labels`。**禁止**在 `div_body()` 内再写 `<text>…÷…</text>`。

### 改后验收（div / div_n 中心字）

```bash
python scripts/build_drawio_lib.py
python -m pytest tests/test_label_overflow.py tests/test_simple_components.py -q
```

`div.label_html()` 须含 **`>÷</span>`**，且**不含** `÷</text>`。

## 连线点对齐（交付前必检 · 强制）

`points` 必须落在 **SVG 图形线条或边框** 上。落在默认外框缘、或 fanout 等距假位置时，缩放/布线后连线会偏离图案。

**每次改动器件库（外形、label HTML、cell 高宽、`points`、间距）后，必须做连线对齐检查；未通过不得交付。有问题则改代码 → `build` → 再检查，循环直到预览图与 draw.io 画布均正确。**

### draw.io HTML 包装偏移（端口看似上移）

| 现象 | 根因 | 做法 |
| --- | --- | --- |
| 几乎所有器件连线端点略**高于**图案 | draw.io `html=1` 外包层为 `inline-block; font-size:12px; line-height:1.2`，导出 SVG 中图案比 `mxGeometry` 原点约 **下移 7px、右移 2px**；`points` 仍按外框比例 | `stretch_body_layer` 图形层使用 **`graphic_layer_pin_css()`**：`left:-2px;top:-7px`（常量 `DRAWIO_HTML_LABEL_OFFSET_*` in `label_overflow.py`） |

### 检查项

| 检查项 | 做法 |
| --- | --- |
| 几何真源 | 端口坐标与 SVG 路径/边框由同一组 `*_geometry` / `*_output_positions()` 或 **`port_cells`** 计算；**禁止**未设 `port_cells` 时误用 `body_rect`（`margin_x=8` → x=8/32）代替芯片/六边形等真实轮廓（**dto/dto_n** 芯片 x=4/36，**div/div_n** 六边形竖边 x≈7/33） |
| Fanout 多输出 | 若输出不在右缘等距，须像 **cpu_gate / inv_mux / clk_phase_sel** 提供 `output_cells` |
| xor / xnor 输入 | 引线终点须用 **`xor_extra_input_arc_x_at_y`**（= `_or_left_arc_x_at_y` on `LOGIC_XOR_EXTRA_X`），与 X 弧 path 共真源；`test_xor_input_leads_meet_extra_arc` 断言 x2；预览 `xor.svg` 红 stub 右端须落在 X 弧描边上 |
| 自动化 | `python -m pytest tests/test_port_graphic_alignment.py tests/test_simple_components.py -q`；各器件 `verify_geometry()` |
| 预览 SVG | `python scripts/build_drawio_lib.py` 后打开 `drawio-lib/images/<器件>.svg`：**红/绿 stub 圆心**须落在线条或边框上 |
| draw.io 画布 | 重新导入库后拖入新形状，目视连线锚点与引线或边框重合 |

**器件库改动未通过上述连线检查前不得交付。**

## 改后必跑

**器件库与预览图必须同时更新**：只改 `drawio-lib/images/*.svg` 或只改 `drawclock.xml` 都不算完成。真源是 `scripts/drawio_lib/components/*.py`；一条命令同时写出库与 SVG：

```bash
python scripts/build_drawio_lib.py
```

| 产出 | 路径 | 用途 |
| --- | --- | --- |
| 器件库 | `drawio-lib/drawclock.xml` | draw.io **导入**的形状（压缩 mxlibrary） |
| 预览图 | `drawio-lib/images/<库名>.svg` | README 示意、Agent 目视验收 |

**禁止**手改上述两处的 path / label HTML。改 Python → 跑 build → 两处一起变；`build` 末尾 `check OK` 表示库 XML 与各器件 `label_html()` 几何一致。

```bash
python scripts/build_drawio_lib.py
python -m pytest tests/test_port_graphic_alignment.py tests/test_label_overflow.py tests/test_simple_components.py tests/test_mux_components.py -q
```

## 图形外形规格（Agent 改形必读）

真源：`scripts/drawio_lib/components/simple_shapes.py`（及 `*_geometry.py`）。预览图：`drawio-lib/images/<库名>.svg`。用户向 README **只放图**，外形 prose 写在本节。

### D 形门体（共用骨架）

| 常量 | 逻辑门 | gate |
| --- | --- | --- |
| 左缘 x | `LOGIC_GATE_LEFT_X=8` | `GATE_LEFT_X=11` |
| 弧起点 x | `LOGIC_GATE_ARC_X=18` | `GATE_ARC_X=19` |
| 半圆半径 r | `LOGIC_GATE_BODY_R=12` | `GATE_BODY_R=12` |

**D 形 path 骨架**（设计格，未加 `side_pad_x`）：

```text
M left,top ──顶边水平──► arc,top ──右半圆 A r r──► arc,bot ──底边水平──► left,bot ──左缘──► 闭合
```

| 器件 | 左缘 | 右缘 | 填充 | 备注 |
| --- | --- | --- | --- | --- |
| **gate** | 竖直线 | 半圆 + 输出小圆 | 无 | 时钟门控 |
| **cpu_gate** | 矩形 + 顶栏 | 主体区右缘，行距同 mux | 无 | `ModuleComponent`；见 **drawio-module-type-component** |
| **and** | 竖直线 | 半圆 | `#d9d9d9` | 标准 AND |
| **nand** | 同 and | 半圆 + 输出反相圆 | 同 and | |
| **or** | **向右凸椭圆弧** `A rx ry`（`rx=arc_x−left_x`，`ry=body_r`） | 半圆 | 同 and | **非**竖线、**非**小幅度 Q 曲线 |
| **nor** | 同 or | 半圆 + 反相圆 | 同 and | |
| **xor** | **同 or 门体** | 半圆 | 同 and | 再向左偏移 `LOGIC_XOR_EXTRA_X` 画**第二条**同参数椭圆弧（仅描边） |
| **xnor** | 同 xor | 半圆 + 反相圆 | 同 and | |

**or / nor / xor / xnor 左缘验收**：预览 `or.svg` 须明显呈 **大写 D**——与 `and.svg` 同顶边、同右半圆、同底边，仅把左侧竖线换成**向右凸出、最凸点落在 `arc_x` 竖线**（默认格 x≈58）的椭圆弧。**门体** path **禁止**用 `Q` 二次贝塞尔（旧实现 `Q 54 30` 控制点偏左，凸起仅 ~3px，肉眼仍像竖线）。

#### OR 族 path 真源（必须与 AND 同骨架）

与 **and** 共用顶边 + 右半圆 + 底边，仅把 `L left,bot Z` 的左竖线换成闭合椭圆弧（设计格，未加 `side_pad_x`）：

```text
M left,top ──L──► arc,top ──A r r──► arc,bot ──L──► left,bot ──A rx ry 0 0 0──► left,top Z
```

默认格 cell path 示例（`side_pad_x` 后）：

```text
M 48 18 L 58 18 A 12 12 0 1 1 58 42 L 48 42 A 10 12 0 0 0 48 18 Z
```

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `rx` | `LOGIC_GATE_ARC_X − LOGIC_GATE_LEFT_X`（10） | 最凸点 x = `left + rx` = `arc_x` |
| `ry` | `LOGIC_GATE_BODY_R`（12） | 与门体半高一致 |
| 闭合弧 flags | **`0 0 0`**（`bot → top`） | 向右凸；`0 0 1` 同向会凸向 **左**（x≈38） |

实现：`_or_shape()` in `simple_shapes.py`。**禁止**先画 `M left,top A … left,bot` 再 `L arc,bot`（缺显式顶边，与 and 不同步，易回归）。

#### OR 族常见误区

| 误区 | 后果 |
| --- | --- |
| 门体用 `Q` 或 `Q 54 30` 画左缘 | 控制点未到 `arc_x`，弧几乎看不见 |
| 路径不以 `M left,top L arc,top` 开头 | 与 and 顶/底不一致，验收难对比 |
| 闭合弧用 `A … 0 0 1`（`bot→top`） | 弧向左凸，不像 OR |
| 输入引线 Q 接到 `(left, top/bot)` 角点 | 引线脱离弧面；应水平接到弧上 |
| 只改 `drawio-lib/images/*.svg` 或 XML | 与 Python 真源脱节 |

#### OR 族输入引线

水平直线，终点 x 由 **`_or_left_arc_x_at_y(body_left, mid, y)`** 计算（椭圆右弧与输入 y 的交点；默认格 y=22/38 时 x≈53.5）。端口 x 仍在 `logic_input_port_x()` = 左缘 − `LOGIC_LEAD_EXT`。

**xor / xnor** 在门体左再画一条平行弧（设计格 x=`LOGIC_XOR_EXTRA_X`，与 `LOGIC_GATE_LEFT_X` 间距即两弧间隔；默认 **4px**），仅描边。输入引线用 **`_logic_input_lead_xor`** 接到该弧上，坐标与 OR 族相同：终点 x = **`xor_extra_input_arc_x_at_y`**（即 `_or_left_arc_x_at_y(body_left=extra)`，与 OR 主弧用 `_or_left_arc_x_at_y(body_left=main_left)` 同一规则），**禁止**仅用 `_or_left_arc_x_at_y_from_outside`（停在弧外缘会留缝）或穿过 X 弧连到主门体。

### 逻辑门引线

| 器件 | 输入引线 | 输出 |
| --- | --- | --- |
| and / nand | 水平直线到左缘竖线 | 水平直线 + 可选反相圆 |
| or / nor / xor / xnor | 水平直线到左弧在输入 y 处的交点（`_or_left_arc_x_at_y`） | 同上 |
| buffer | 三角形 + 水平引线 | 水平直线 |

端口 x：`logic_input_port_x()` = 左缘 − `LOGIC_LEAD_EXT`；输出 = 门体右缘 + 引线。

### 其它器件（概要）

| 库名 | 外形 |
| --- | --- |
| **div / div_n** | 正六边形；中心字 HTML overlay |
| **div2** | 正六边形；中心 **÷2** 单行 HTML overlay（勿再画 SVG 除号线 + 单独「2」，字体会与横线重叠） |
| **dto / dto_n** | 圆角矩形 + 中心字 overlay |
| **inv** | D 形（gate 系）+ 输出反相圆 |
| **inv_cell** | 同 **inv** 门体 + 输出小三角（替代反相圆） |
| **inv_mux** | 梯形 mux 形 + 反相 |
| **mux2～6** | 等腰梯形；端口在斜边；见 `mux_geometry.py`；**无** `sel` 与顶中上方竖线 |
| **pll / pll2** | 六边形/双输出六边形；中心 `%pll_kind%` HTML |
| **source** / **pad** | source：**圆** + 正弦波；pad：空心方块 + 右端 **C** |
| **clock** | 方波（右→左）+ 左侧输入引线（与波形底边 **y_lo** 同高）+ 实例名；端口 **(0, y_lo)** |
| **from** | 水平线段 |
| **occ/gen/bist/occ_bist clk_cell** | 彩色三角 |
| **async** | 红色叉 |
| **clk_phase_sel** | 方框 + 右侧三相波形 |

### 如何准确改形

1. **只改设计格常量**（`LOGIC_*` / `GATE_*`），用 `_dx(g, design_x)` 转 cell 坐标；**禁止**手改 `drawio-lib/images/*.svg` 或 `drawclock.xml`。
2. **path 与 `points` 共真源**：改 `simple_shapes` 后确认 `*_geometry.py` / `logic_gate_geometry.py` 端口仍落在引线末端。
3. **中心字 / ÷ / DTO 字**走 HTML overlay（见上文 div 节与 **drawio-module-type-component**），**不**写进 `preserveAspectRatio="none"` 的 SVG `<text>`。
4. 改完 **`python scripts/build_drawio_lib.py`**，**同时**再生 `drawio-lib/images/*.svg` 与 `drawio-lib/drawclock.xml`；须见 `check OK`。

### 改形后图形检查（须全部通过再提交）

| 步 | 做法 |
| --- | --- |
| 1 自动化 | `python -m pytest tests/test_port_graphic_alignment.py tests/test_simple_components.py tests/test_label_overflow.py -q` |
| 2 预览 SVG | 打开 `drawio-lib/images/<器件>.svg`，对照上表 **逐条**核对轮廓（D 形 / 左弧 / 反相圆 / 引线） |
| 3 与同族对比 | 逻辑门：并排看 `and.svg` 与 `or.svg`——除左缘外应同高、同右半圆、同引线位置 |
| 4 端口 | 预览 SVG 中红/绿 stub 圆应落在引线外端（与 `points` 一致） |
| 5 固定框 | 在 `drawclock.xml` 解压结果中确认 style 含 `overflow=visible` 与 `resizable=0`，且不含 `overflow=fill` |
| 6 or/xor 专项 | 门体 path 以 `M left top L arc top` 开头；含 `A 10 12 0 0 0` 闭合左弧；门体无 `Q`；xor/xnor 有两条 `A`；输入引线 x2 = `xor_extra_input_arc_x_at_y`（默认格 y=22/38 时 x≈**51.45**），须与 X 弧描边重叠、不得留缝；`drawclock.xml` 解压后 path 与 `label_html()` 一致 |

**未通过第 2～6 步目视核对，不算改完。**

改后除跑 pytest，还须对本次动过的器件打开对应 `drawio-lib/images/*.svg` 做连线点对齐目视确认。

## 改完必回写 skill（强制）

**凡改动 `scripts/drawio_lib/components/` 中器件外形、端口、引线或 `simple_shapes` 几何常量，交付前必须完成本步；跳过则任务未完成。**

| 步 | 做法 |
| --- | --- |
| 1 更新专档 | 编辑 **本文件**（`drawclock-drawio-pitfalls/SKILL.md`）：在对应器件节或「常见误区」表追加**可复现**结论——正确 path/常量、错误写法、验收命令；删或改已过时表述 |
| 2 决议级变更 | 若影响用户可见行为或 JSON/CLI 口径，当轮在 **`project-changelog`** 顶部追加一条 **决议** |
| 3 设计笔记 | 若改动器件族规则，同步 **`project-design-notes`** 图形库相关表 |
| 4 自检 | 确认本节与「图形外形规格」「改后必跑」无矛盾；新误区能被 `tests/test_simple_components.py` 中相关断言覆盖（无则补测） |

**禁止**只在对话里口头总结、不写入 skill；**禁止**只改代码不更新本专档。
