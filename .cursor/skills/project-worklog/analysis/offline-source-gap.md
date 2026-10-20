# 发行包源码部署缺口

- status: active
- created: 2026-08-25 11:19 +08:00
- updated: 2026-10-20 13:33 +08:00
- scene: 现有发行包缺口分析

## 事实

- 2026-10-20 的公开 Linux 归档没有 `src/`；当前 tag 中有 19 个产品 `src/*.py` 文件。
- `tools/bundle_release.py` 的显式复制集合不含源码；`tools/check_release_archive.py` 的 allowlist 会拒绝新增源码。
- 现有 Linux Shell 示例从包根调用冻结 `drawclock`，这条用户路径必须保持不变。

- `tools/bundle_release.py` 把仓库 `src/` 复制为包内 `source/`。
- 包内 `pyproject.toml` 的 `package-dir` 仍为 `src`。
- Python 依赖只有版本声明，发布包没有 wheel 或源码副本。
- 源码查找 ELK 运行时只检查 `.runtime/`，发布包使用 `runtime/`。

## 结论

当前正式 Linux 包只能运行冻结程序，已不能查看或使用源码。修复应只为 Linux 归档增加干净的 `src/`，由动态 exact-set、逐文件字节比对和解压后 `python3 -I -S src` 消费门证明；无需 wheelhouse，因为当前产品只使用 Python 标准库。

## 边界

源码发行仍需要目标机器预装支持版本的 CPython；完全不依赖 Python 安装的场景使用冻结程序。
