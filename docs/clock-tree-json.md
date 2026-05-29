# clock-tree.json

JSON **对象**：**键**为器件 `name`（字符串），**值**为该器件记录（对象，**不含** `name` 字段）。

样例：[example/out/clock-tree.json](../example/out/clock-tree.json)。

## 记录公共字段

每条记录（对象值）至少包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `kind` | string | 记录类型，见各节 |

对端连接字段中的器件名，须为**本文件顶层键**中已出现的名称。

## wire（仅图中，不进 JSON）

**wire** 只在 draw.io 中用于**跨图**同名接续（例如图 1 的 source 输出接到 `bus_xtal`，图 2 中两条同名 `bus_xtal` 分别驱动不同支路）。`src` 导出时**不**生成 `kind: "wire"` 记录，关系折叠为器件上的 `source` / `targets`。

## gate

`kind` 固定为 `"gate"`。

```json
{
  "gate0": {
    "kind": "gate",
    "source": "w_pll_main_gate0",
    "target": "w_gate0_div0"
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"gate"` | 必有 |
| `source` | string | 必有 |
| `target` | string | 必有 |

## div

`kind` 固定为 `"div"`。

```json
{
  "div0": {
    "kind": "div",
    "source": "w_gate0_div0",
    "target": "w_div0_inv0"
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"div"` | 必有 |
| `source` | string | 必有 |
| `target` | string | 必有 |

## dto

`kind` 固定为 `"dto"`。

```json
{
  "dto0": {
    "kind": "dto",
    "source": "w_inv0_dto0",
    "target": "w_dto0_clk_sys"
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"dto"` | 必有 |
| `source` | string | 必有 |
| `target` | string | 必有 |

## inv

`kind` 固定为 `"inv"`。

```json
{
  "inv0": {
    "kind": "inv",
    "source": "w_div0_inv0",
    "target": "w_inv0_dto0"
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"inv"` | 必有 |
| `source` | string | 必有 |
| `target` | string | 必有 |

## source

`kind` 固定为 `"source"`。时钟源（晶振、外部参考时钟等），仅向右输出；可驱动多路，用 **`targets`**。

```json
{
  "xtal": {
    "kind": "source",
    "targets": ["gate0", "div0"]
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"source"` | 必有 |
| `targets` | string[] | 必有 |

## pll

`kind` 固定为 `"pll"`。一路输入 **`source`**，可驱动多路 **`targets`**。

```json
{
  "pll_main": {
    "kind": "pll",
    "pll_kind": "sc",
    "source": "xtal",
    "targets": ["gate0", "div0"]
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"pll"` | 必有 |
| `pll_kind` | string | 必有；自 draw.io 导出为小写（默认 `sc`） |
| `source` | string | 必有 |
| `targets` | string[] | 必有 |

## clock

`kind` 固定为 `"clock"`。

```json
{
  "clk_sys": {
    "kind": "clock",
    "freq": 100000000,
    "source": "w_dto0_clk_sys"
  }
}
```

图中 `freq` 属性可写 `100`、`100k`、`50M` 等（后缀 `k`/`m`/`g` 大小写均可）；导出 JSON 中为**数值**（已按后缀换算为赫兹）。

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"clock"` | 必有 |
| `freq` | number | 可选 |
| `source` | string | 必有 |

## mux

`kind` 固定为 `"mux"`。`source` 为对象，**键名与图上输入标签一致**（默认 `0`、`1`、…，非 `in0`）。

```json
{
  "mux2": {
    "kind": "mux",
    "source": {
      "0": "pll_m2a",
      "1": "pll_m2b"
    },
    "target": "clk_mux"
  }
}
```

| 字段 | 类型 | 出现 |
| --- | --- | --- |
| `kind` | `"mux"` | 必有 |
| `source` | object | 必有；键为标签字符串 → 对端器件名 |
| `target` | string | 必有 |

mux6 时 `source` 键为 `"0"` … `"5"`（与 `in0_label`… 显示一致）。
