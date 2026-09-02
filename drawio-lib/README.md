# 器件库

`drawclock/` 中每个 XML 只包含一个器件，均为标准 draw.io 自定义库文件。drawclock 命令可直接加载整个目录。

## 使用

1. 在 VS Code / Cursor 安装 **Draw.io Integration** 插件（`hediet.vscode-drawio`），在本仓库中打开任意 `.drawio` / `.drawio.svg` 文件。
2. **文件 → 导入**，选择 `drawclock/` 中需要的器件 XML。
3. 从左侧形状库将器件拖到画布。
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
| `name` | 实例名 |

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
| dto | ![dto](images/dto.svg) |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |
| `ratio` | 分频变量（仅 `div_r`，默认 `2`，图中显示 `1/ratio`） |

### 反相器

| 库名 | 预览 |
| --- | --- |
| inv | ![inv](images/inv.svg) |
| inv_cell | ![inv_cell](images/inv_cell.svg) |
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

### 时钟源

| 库名 | 预览 | 说明 |
| --- | --- | --- |
| source | ![source](images/source.svg) | 振荡源 |
| pad | ![pad](images/pad.svg) | I/O 输出 |
| pad3 | ![pad3](images/pad3.svg) | 三输入汇聚、单输出输入 pad |

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
| `name` | 须与某张图中的某个器件同名 |
