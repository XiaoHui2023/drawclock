# drawclock 图形库

从左侧形状面板拖出器件，画时钟树示意图。只需导入 **`drawclock.xml`** 一个文件。

改库或排查画布问题：Agent 见 **`.cursor/skills/drawclock-drawio-pitfalls/SKILL.md`**。

## 使用

1. 在 VS Code / Cursor 安装 [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio) 插件，在本仓库中打开任意 `.drawio` / `.drawio.svg` 文件。  
2. 工作区已配置 `hediet.vscode-drawio.customLibraries`，**每次打开图表**都会从 `drawio-lib/drawclock.xml` 加载 **drawclock** 形状库（改库后重新打开该图即可看到新器件）。  
3. 若在其它目录单独用 draw.io，仍须 **文件 → 导入** 选择 `drawclock.xml`。  
4. 在左侧形状库的 **drawclock** 条目中，将器件拖到画布。  
5. **双击**器件改属性；弹出框中 **Placeholders** 必须勾选，再点 **应用**。  
6. 从器件**端口**（形状边缘连接点）拖线到其它器件端口。

## 通用属性

库中形状可自由拉宽拉高；**图案横纵随方框拉伸**（`overflow=fill` + 图案层 `100%×100%`、`preserveAspectRatio="none"`），端口与图形对齐。默认格已加宽（一般 **80px**、clock **160px**）以容纳较长实例名。

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

## 器件

库中形状名与下表 **库名** 一致。各器件在图形**下方**显示 **`name`** 实例名（默认与库名相同，留空不显示）。

### mux

多路选择器

![mux3 示意](images/mux3.svg)

| 库名 | 输入路数 |
| --- | --- |
| mux2 | 2 |
| mux3 | 3 |
| mux4 | 4 |
| mux5 | 5 |
| mux6 | 6 |

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |
| `in0_label` … | 左侧第 K 路旁标注（按路数有 `in0`…`in5`） | 与路号相同（0、1…） |

端口：左侧每路输入各一点，右侧一点输出。

### gate

时钟门控单元

![gate 示意](images/gate.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

端口：左侧时钟入，右侧门控时钟出。

### div

时钟分频器

![div 示意](images/div.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

中心 **÷**、**DIV** 为固定小字号。

端口：左侧入，右侧出。

### dto

占空比调整单元

![dto 示意](images/dto.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

中心 **DTO** 为固定约 7px。

端口：左侧入，右侧出。

### inv

时钟反相器

![inv 示意](images/inv.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

端口：左侧入，右侧出。

### source

时钟源（晶振、外部参考时钟等）

![source 示意](images/source.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

图形为圆内正弦波，无库内固定中心文字。端口：**仅右侧**输出。

### pll

锁相环

![pll 示意](images/pll.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |

端口：**仅右侧**输出。

### clock

时钟终端

![clock 示意](images/clock.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 图形下方实例名；留空不显示 | 与库名相同 |
| `freq` | 右侧 **`(freq hz)`** 中频率部分；留空为 `(hz)` | （空） |

波形与 `(freq hz)` 间距在库内固定 **60px**，无 `freq_gap` 属性。

端口：**仅左侧**输入。

### wire

时钟连线

![wire 示意](images/wire.svg)

| 属性 | 说明 | 默认 |
| --- | --- | --- |
| `name` | 波形下方实例名；留空不显示 | `wire` |

端口：左、右各一点。
