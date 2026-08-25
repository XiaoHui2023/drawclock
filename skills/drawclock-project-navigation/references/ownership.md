# 职责与归属

## 唯一事实来源

| 主题 | 归属 |
| --- | --- |
| 器件轮廓、尺寸、端口、标签模板 | `scripts/drawio_lib/` 与 `component-library-design` |
| 用户 JSON 字段和 source 语义 | `src/config_input.py`、验证模块与 `clock-json-schema` |
| 逻辑图、rank、行序、坐标、路由、候选评分 | `src/auto_layout.py` 及布局辅助模块；`clock-layout-algorithms` |
| 最终图的美观/可读要求 | `clock-diagram-design`，并由 `tests/` 机器化 |
| CLI 与 SVG 输出行为 | `src/__main__.py`、`draw.md` |
| 包内容和离线可执行性 | `tools/`、Release workflow、`source-deploy.md` |

## 放置判断

- “应该怎样看起来”写到成图设计；“怎样计算出来”写到布局算法。
- 字段语义写到 JSON；字段如何影响 rank 写到布局算法。
- “端口在哪里”写到器件库；“边如何避开端口附近器件”写到布局算法。
- 通用规则进入 skill；用于证明规则的具体连接结构进入 example/tests。
- 测试指标只用于开发门禁，不增加用户参数。
