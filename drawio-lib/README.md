# drawclock 图形库

从左侧形状面板拖出器件，画时钟树示意图。只需导入 **`drawclock.xml`** 一个文件。

## 使用

1. 在 VS Code / Cursor 安装 **Draw.io Integration** 插件（`hediet.vscode-drawio`），在本仓库中打开任意 `.drawio` / `.drawio.svg` 文件。  
2. **文件 → 导入**，选择 `drawclock.xml`。  
3. 在左侧形状库的 **drawclock** 条目中，将器件拖到画布。  
4. **双击**器件改属性；弹出框中 **Placeholders** 必须勾选，再点 **应用**。  
5. 从器件**端口**拖线到其它器件端口。

## 器件

### mux

![mux3](images/mux3.svg)

| 库名 | 输入路数 |
| --- | --- |
| mux2 | 2 |
| mux3 | 3 |
| mux4 | 4 |
| mux5 | 5 |
| mux6 | 6 |

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### gate

![gate](images/gate.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### div

![div](images/div.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### cell

![cell](images/cell.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### dto

![dto](images/dto.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### inv

![inv](images/inv.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### source

![source](images/source.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |

### pll

![pll](images/pll.svg)

| 属性 | 说明 |
| --- | --- |
| `pll_kind` | PLL 类型 |
| `name` | 实例名 |

### pll2

![pll2](images/pll2.svg)

| 属性 | 说明 |
| --- | --- |
| `pll_kind` | PLL 类型 |
| `name` | 实例名 |

### clock

![clock](images/clock.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |
| `freq` | 频率 |

### wire

![wire](images/wire.svg)

| 属性 | 说明 |
| --- | --- |
| `name` | 实例名 |
