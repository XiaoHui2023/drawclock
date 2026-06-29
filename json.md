# JSON

以下为示范。

`kind` 由器件库 style 中的 `drawclockKind` 导出（图中 object 不手写 `kind`）。若某大类下存在小类区分，则该类下**每个**器件导出时须同时含 `kind`（大类）与 `{大类}_kind`（小类）；基础图形也算小类，如 `inv` / `inv_kind: inv`、`cell` / `cell_kind: cell`。`mux`、`pll` 仅统一大类，无 `mux_kind` / 路数小类——输入路数、输出路数体现在库图形端口，不在 `kind` 里。`pll_kind` 表示 PLL IP 类型（如 `SC`、`INNO`），与单/双输出无关。

旧图若缺少 `drawclockKind`，导出可能仍用库类型名（如 `pll2`、`mux3`）；须重载器件库升级图形后再导出。

```json5
// JSON 无 from；涂鸦与非器件库图形不进 JSON，连到涂鸦的边忽略、不报错；其余属性原样来自图中 object
{
  "xtal": {
    "kind": "source",        // 时钟源大类
    "source_kind": "source"  // 小类：source / pad
  },
  "pll_main": {
    "kind": "pll",
    "pll_kind": "SC",
    "source": "xtal"
  },
  "pll_dual": {
    "kind": "pll",           // 库图形可为 pll 或 pll2，导出均为 pll
    "pll_kind": "INNO",
    "source": "xtal"
  },
  "gate0": {
    "kind": "gate",
    "source": "pll_dual[0]"  // 接多路输出上游：名[键]，键为 str
  },
  "div0": {
    "kind": "div",
    "source": "pll_dual[1]"
  },
  "dto0": {
    "kind": "dto",
    "source": "div0"
  },
  "inv0": {
    "kind": "inv",
    "inv_kind": "inv",
    "source": "gate0"
  },
  "mux0": {
    "kind": "mux",           // 库图形 mux2…mux6，导出均为 mux
    "source": {
      "0": "pll_m2a",        // 多路输入：source 为 dict，键为 str（序号或端口名）
      "1": "pll_m2b"
    }
  },
  "pll_m2a": {
    "kind": "pll",
    "pll_kind": "SC",
    "source": "xtal"
  },
  "pll_m2b": {
    "kind": "pll",
    "pll_kind": "SC",
    "source": "xtal"
  },
  "clk_mux": {
    "kind": "clock",
    "freq": "100",           // 图中属性原样导出，不做数值换算
    "source": "mux0"
  },
  "cell0": {
    "kind": "cell",           // 时钟 cell 大类
    "cell_kind": "cell",      // 小类：cell / occ_clk_cell / gen_cell / …
    "source": "gate0"
  },
  "occ0": {
    "kind": "cell",
    "cell_kind": "occ_clk_cell",
    "source": "gate0"
  }
}
```
