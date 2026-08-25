# 配置依赖裁剪分析

- status: done
- created: 2026-08-25 14:00 +08:00
- updated: 2026-08-25 14:00 +08:00
- scene: 配置依赖裁剪分析

## 结论

- 唯一输入确定为严格 JSON 后，Python 标准库 `json` 足以覆盖 UTF-8 BOM、语法解析和对象根节点验证。
- configlib 及其 extras 可以整体删除；`configparser`、json5、yaml、toml 加载分支也随之删除。
- wheelhouse 只服务这些 Python 运行时依赖，因此 `requirements-offline.txt`、`prepare_source_bundle.py`、`vendor/wheels` 和源码门中的 pip 安装都可以删除。
- Node.js 与 ELK 负责布局计算，仍由 `runtime/` 随包提供；删除它们会破坏源码绘图，不在本次依赖裁剪范围内。
