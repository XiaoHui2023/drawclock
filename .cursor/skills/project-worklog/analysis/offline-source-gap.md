# 发行包源码部署缺口

- status: done
- created: 2026-08-25 11:19 +08:00
- updated: 2026-08-25 11:55 +08:00
- scene: 现有发行包缺口分析

## 事实

- `tools/bundle_release.py` 把仓库 `src/` 复制为包内 `source/`。
- 包内 `pyproject.toml` 的 `package-dir` 仍为 `src`。
- Python 依赖只有版本声明，发布包没有 wheel 或源码副本。
- 源码查找 ELK 运行时只检查 `.runtime/`，发布包使用 `runtime/`。

## 结论

当前包能运行冻结程序，也能查看源码，但不能证明断网源码部署。采用保持仓库目录结构、目标平台多 Python wheelhouse、摘要清单和空虚拟环境源码运行四项约束。

## 边界

源码发行仍需要目标机器预装支持版本的 CPython；完全不依赖 Python 安装的场景使用冻结程序。
