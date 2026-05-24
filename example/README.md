# 示例

演示复杂时钟树图经 **encode** 导出 JSON，再经 **decode** 无损还原为 draw.io。

## 在 draw.io 里看到器件图案

| 文件 | 作用 |
| --- | --- |
| `demo.drawio` | 手工/脚本维护的示例原理图 |
| `out/restored.drawio` | **decode 还原图**：由 `clock-tree.json` + `drawio-layout.json` 生成，应与 `demo.drawio` 拓扑一致 |

画布上的 PLL、mux、方波等外形来自 `drawclock.xml` 里每条形状的 **`object label="..."` HTML**（含 SVG），与 mxCell 的 `style`（`html=1`、`points` 等）一起写入 `.drawio`。

- **生成示例图**：`python scripts\build_example_demo.py` 只读 `drawio-lib/drawclock.xml`，**不必**在 draw.io 里导入器件库即可查看 `demo.drawio`。
- **若只看到方框**：说明文件里缺少 `label` HTML。重新运行上述脚本或 `example.bat`。
- **从面板拖新器件**（手工编辑）：仍可在 draw.io 中导入 `drawclock.xml`（见 [drawio-lib/README.md](../drawio-lib/README.md)）。

## 准备

在仓库根目录执行 `update.bat` 安装依赖。

生成或更新示例图（可选，改器件布局后执行）：

```bat
python scripts\build_example_demo.py
```

## 运行

在仓库根目录：

```bat
example.bat
```

或分步：

```bat
python src encode -i example\demo.drawio -o example\out --layout
python src decode --config example\out\clock-tree.json --layout example\out\drawio-layout.json --library drawio-lib\drawclock.xml -o example\out\restored.drawio
python src encode -i example\out\restored.drawio -o example\out --layout
```

第二次 encode 得到的 `clock-tree.json` 与 `drawio-layout.json` 应与第一次一致。

## 输出

| 文件 | 内容 |
| --- | --- |
| `example/out/clock-tree.json` | 逻辑连接：器件名、类型、source/target、mux 多路 source、wire 的 connections |
| `example/out/drawio-layout.json` | 坐标、尺寸、边样式、航点、对象属性（与配置 JSON 配套供 decode） |

## 图内容（demo.drawio）

- **主链**（wire 串联）：`pll_main` → `gate0` → `div0` → `inv0` → `dto0` → `clk_sys`（100 MHz）
- **mux2～mux6**：各路独立 PLL 接入对应 mux 输入，经 wire 接到各档时钟终端（200～600 MHz）
- 覆盖图形库类型：`pll`、`gate`、`div`、`inv`、`dto`、`wire`、`clock`、`mux2`～`mux6`

在 draw.io 中打开 `demo.drawio` 前，请先导入 `drawio-lib/drawclock.xml`（见 [drawio-lib/README.md](../drawio-lib/README.md)）。
