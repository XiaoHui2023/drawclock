# 端口与 source 引用

## 单输入

当目标器件只有一个输入时，直接写上游实例名：

```json
"divider": {"kind": "div", "source": "pll_main"}
```

## 多输入

目标有多个输入时，`source` 是对象。键来自库端口旁的可见标签；无法提取标签时，按输入端口从上到下使用稳定数字键：

```json
"select": {
  "kind": "mux2",
  "source": {"0": "osc", "1": "external"}
}
```

对象可以只列实际连接的端口：

```json
"select": {"kind": "mux2", "source": {"1": "external"}}
```

不要写空对象；没有输入连接时省略 `source`。

## 多输出

上游有多个输出时，用 `实例名[输出键]`：

```json
{
  "pll_dual": {"kind": "pll2", "source": "osc"},
  "branch_a": {"kind": "div", "source": "pll_dual[0]"},
  "branch_b": {"kind": "div", "source": "pll_dual[1]"}
}
```

单输出通常不需要后缀。为避免解析歧义，实例名建议使用字母、数字、下划线和短横线，不使用方括号。
