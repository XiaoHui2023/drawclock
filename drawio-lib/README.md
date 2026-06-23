# 器件库

从左侧形状面板拖出器件，画时钟树示意图。只需导入 **`drawclock.xml`** 一个文件。

## 使用

1. 在 VS Code / Cursor 安装 **Draw.io Integration** 插件（`hediet.vscode-drawio`），在本仓库中打开任意 `.drawio` / `.drawio.svg` 文件。  
2. **文件 → 导入**，选择 `drawclock.xml`。  
3. 在左侧形状库的 **drawclock** 条目中，将器件拖到画布。  
4. **双击**器件改属性；弹出框中 **Placeholders** 必须勾选，再点 **应用**。  
5. 从器件**端口**拖线到其它器件端口。

## 器件

### 选择器

| 库名 | 预览 |
| --- | --- |
| mux2 | ![mux2](images/mux2.svg) |
| mux3 | ![mux3](images/mux3.svg) |
| mux4 | ![mux4](images/mux4.svg) |
| mux5 | ![mux5](images/mux5.svg) |
| mux6 | ![mux6](images/mux6.svg) |

| 属性 | 说明 |
| --- | --- |
| `sel` | 控制选择信号名；填则在器件正上方显示竖线与文字，不填则不显示（默认空） |
| `name` | 实例名 |

下方预览图为说明用示例（含 `sel` 示意文字）；拖入库中的器件默认 `sel` 为空，不显示该线段。

### gate

![gate](images/gate.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### 分频器

| 库名 | 预览 |
| --- | --- |
| div | ![div](images/div.svg) |
| div_r | ![div_r](images/div_r.svg) |
| div_n | ![div_n](images/div_n.svg) |
| dto | ![dto](images/dto.svg) |
| dto_n | ![dto_n](images/dto_n.svg) |
| cpu_gate | ![cpu_gate](images/cpu_gate.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |
| `ratio` | 分频系数（仅 `div_r`，默认 `2`） |

### clk_phase_sel

![clk_phase_sel](images/clk_phase_sel.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### 反相器

| 库名 | 预览 |
| --- | --- |
| inv | ![inv](images/inv.svg) |
| inv_mux | ![inv_mux](images/inv_mux.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### cell

| 库名 | 预览 |
| --- | --- |
| cell | ![cell](images/cell.svg) |
| occ_clk_cell | ![occ_clk_cell](images/occ_clk_cell.svg) |
| gen_cell | ![gen_cell](images/gen_cell.svg) |
| bist_clk_cell | ![bist_clk_cell](images/bist_clk_cell.svg) |
| occ_bist_clk_cell | ![occ_bist_clk_cell](images/occ_bist_clk_cell.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### async

![async](images/async.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### 逻辑门

| 库名 | 预览 |
| --- | --- |
| and | ![and](images/and.svg) |
| nand | ![nand](images/nand.svg) |
| or | ![or](images/or.svg) |
| nor | ![nor](images/nor.svg) |
| xor | ![xor](images/xor.svg) |
| xnor | ![xnor](images/xnor.svg) |
| buffer | ![buffer](images/buffer.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### 时钟源

| 库名 | 预览 |
| --- | --- |
| source | ![source](images/source.svg) |
| pad | ![pad](images/pad.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### pll

| 库名 | 预览 |
| --- | --- |
| pll | ![pll](images/pll.svg) |
| pll2 | ![pll2](images/pll2.svg) |

| 属性 | 说明 |
| --- | --- |
| `pll_kind` | PLL 类型 |
| `name` | 实例名 |

### clock

![clock](images/clock.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### from

![from](images/from.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 须与某个 `clock` 同名 |
