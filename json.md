# JSON

以下为示范。

```json5
// JSON 无 from；kind 与器件库名一致；属性原样来自图中 object
{
  "xtal": {
    "kind": "source"
  },
  "pll_main": {
    "kind": "pll",
    "pll_kind": "SC",
    "source": "xtal"
  },
  "pll_dual": {
    "kind": "pll2",
    "pll_kind": "SC",
    "source": "xtal",
    "target": {
      "0": "gate0",  // 多路输出：target 为 dict，键为输出口序号
      "1": "div0"
    }
  },
  "gate0": {
    "kind": "gate",
    "source": "pll_dual[0]"  // 接多路输出上游：名[序号]，从 0 起
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
    "kind": "mux2",
    "source": {
      "0": "pll_m2a",  // 多路输入：source 为 dict，键为输入口序号
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
    "freq": "100",  // 图中属性原样导出，不做数值换算
    "source": "mux2"
  }
}
```
