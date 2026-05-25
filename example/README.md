# example

演示完整工作流：**器件库 → 图 → src → JSON + reload 图**。

## 运行

仓库根目录：

```bat
example.bat
```

或分步：

```bat
python scripts/build_drawio_lib.py
python scripts/build_example_demo.py
python src -i example\fig1.drawio example\fig2.drawio -o example\out\clock-tree.json -l drawio-lib\drawclock.xml
python reload -i example\fig1.drawio -l drawio-lib\drawclock.xml -o example\out\fig1-reloaded.drawio
python reload -i example\fig2.drawio -l drawio-lib\drawclock.xml -o example\out\fig2-reloaded.drawio
```

上游（库或示例图）变更后，须从对应步骤起重新执行并检查输出。

**改 `fig1.drawio` / `fig2.drawio` 或示例生成脚本后，必须跑完整 `example.bat`**（含第 4 步 **reload** 与第 5 步 **pytest**）。reload 是 example 的下一环，不可只跑 `src` 或只改图不验收 reload。

仅跑 reload 相关测试：

```bat
pytest tests\test_reload.py -q
```

## 输入图

`scripts/build_example_demo.py` 生成的 `fig1.drawio` / `fig2.drawio` 使用 draw.io **压缩 diagram**（与 `.drawio.svg` 导出同类）；`reload` 产物同样保持压缩。

| 文件 | 内容 |
| --- | --- |
| `fig1.drawio` | **source** `xtal` 输出接到跨图 **wire** `bus_xtal`（右端悬空） |
| `fig2.drawio` | 两条同名 `bus_xtal` **wire** 分别驱动 `gate0`、`div0`；**pll_main** 同时驱动 `gate0` 与 `div0`；`gate0→inv0→clk_a`、`div0→dto0→clk_b`；**mux2** 标签 `0`/`1` |

**wire** 仅用于**跨图**同名接续；单图内器件直连。`clock-tree.json` 中**不出现** `wire`。

## pll_main 连线航点（手改参考）

权威坐标见 **`refs/pll_main_fanout_waypoints.json`**（来自用户手改 fig2）。生成脚本与之对齐：

| 边 id | 航点 |
| --- | --- |
| 25 | `(170,140)` → `(170,80)` → gate0 |
| 26 | `(170,140)` → `(170,200)` → div0 |

在 draw.io：**选中 pll_main→gate0 或 →div0**，可见 **2 个蓝色菱形** 与竖直汇流柱。Agent 规范：`~/.cursor/skills/drawio-edge-waypoints/SKILL.md`。

## 输出

| 文件 | 说明 |
| --- | --- |
| `example/out/clock-tree.json` | `src` 合并两图后的样例 |
| `example/out/fig1-reloaded.drawio` | reload 刷新图 1（压缩 diagram） |
| `example/out/fig2-reloaded.drawio` | reload 刷新图 2（压缩 diagram） |

## JSON 要点（本示例）

- `xtal.targets`: `gate0`、`div0`（跨图 `bus_xtal` 折叠）
- `pll_main.targets`: `["gate0", "div0"]`
- `mux2.source`: `{"0": "pll_m2a", "1": "pll_m2b"}`
- 无 `kind: "wire"` 条目
