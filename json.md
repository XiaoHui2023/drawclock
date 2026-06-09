# JSON

以下为示范。

```json5
// JSON 无 wire
// freq：Hz；图上 100k、50M 等导出为数值
{
  "xtal": {
    "kind": "source"
  },
  "pll_main": {
    "kind": "pll",
    "pll_kind": "sc",
    "source": "xtal"
  },
  "pll_dual": {
    "kind": "pll",
    "pll_kind": "sc",
    "output_count": 2,  // 图中 pll2
    "source": "xtal"
  },
  "gate0": {
    "kind": "gate",
    "source": "pll_dual[0]"  // 多路 pll：名[序号]，从 0 起
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
    "source": "gate0"
  },
  "mux2": {
    "kind": "mux",  // 库 mux2…mux6 统一为 mux
    "source": {
      "0": "pll_m2a",  // 键为输入标签 0、1…，与 inK_label 一致
      "1": "pll_m2b"
    }
  },
  "pll_m2a": {
    "kind": "pll",
    "pll_kind": "sc",
    "source": "xtal"
  },
  "pll_m2b": {
    "kind": "pll",
    "pll_kind": "sc",
    "source": "xtal"
  },
  "clk_mux": {
    "kind": "clock",
    "freq": 200000000,
    "source": "mux2"
  }
}
```
