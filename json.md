# JSON

以下为示范。

```json5
// JSON 无 from；属性原样来自图中 object；有归类的器件 kind 为大类、{大类}_kind 为小类（如 inv/inv_kind、source/source_kind；库内写入，不可编辑）
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
    "kind": "pll2",
    "pll_kind": "SC",
    "source": "xtal",
    "target": {
      "0": "gate0",  // 多路输出：target 为 dict，键为 str（序号 "0"/"1" 或端口名）
      "1": "div0"
    }
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
  "mux2": {
    "kind": "mux2",
    "sel": "clk_sel",  // 可选；图中填写则原样导出，未填则不出现在 JSON
    "source": {
      "0": "pll_m2a",  // 多路输入：source 为 dict，键为 str（序号或端口名）
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
