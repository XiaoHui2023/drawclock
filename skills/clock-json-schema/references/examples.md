# 示例与反例

## 最小链

```json
{
  "osc": {"kind": "source"},
  "core_clk": {"kind": "clock", "source": "osc"}
}
```

## 部分连接 mux 与列偏好

```json
{
  "external": {"kind": "from", "layout_column": 10},
  "select": {
    "kind": "mux2",
    "layout_column": 20,
    "source": {"1": "external"}
  },
  "clock": {"kind": "clock", "layout_column": 30, "source": "select"}
}
```

## 不应生成

```json
{
  "bad": {
    "kind": "mux",
    "component": "mux2",
    "mux_kind": "mux2",
    "x": 100,
    "source": {}
  }
}
```

问题分别是：kind 不一定是库 title、存在并行类型字段、泄漏坐标、空 source 对象。应改为一个真实 kind，并只列实际连接的输入。
