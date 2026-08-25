# JSON-only 零依赖收敛

- status: done
- created: 2026-08-25 14:00 +08:00
- updated: 2026-08-25 15:45 +08:00
- scene: JSON-only 零依赖收敛

## 当前状态

- `config_input.py` 同时注册 JSON、JSONC、JSON5、TOML、YAML 和 INI 系加载器。
- `config-library[json5,toml,yaml]` 带入 json-five、PyYAML、toml、regex 和 sly；发行包为 CPython 3.10～3.14 携带 14 个 wheel。
- 自动布局仍需要包内 Node.js 与 ELK；它们不是 Python 配置依赖。
- 配置加载已改为标准库 `json`，`pyproject.toml` 运行时依赖已清空。
- 首轮聚焦测试 35/40 通过；5 个失败均为旧多格式正向测试，需改为非 JSON 拒绝门。
- 旧多格式测试已改为严格 JSON 正向与非 JSON/注释/非对象根节点负向门。
- JSON-only 与多库聚焦测试 44 项通过，耗时 8.03 秒。
- wheelhouse、离线 requirements、准备脚本和组包复制逻辑已删除；源码门改为全新虚拟环境下 `python -I -S` 直接运行。
- README、绘图专档、源码部署说明、设计笔记和 changelog 已统一为严格 JSON 与零 Python 运行时依赖；源码部署不再执行 pip。
- 包清单与冻结门已移除多格式/wheelhouse；聚焦测试 43/44 通过，剩余失败暴露必需资源缺失被误报为哈希错误。
- 修正清单实际路径计算后，JSON-only、多库与组包聚焦测试 44 项通过，耗时 8.04 秒。
- 旧 `.source-wheelhouse` 的 14 个配置解析 wheel 与清单已从工作区清除；完整测试、真实静态包和远程 Release 下载复验尚待执行。
- 最新源码静态编译和依赖同模式检索通过，耗时 0.453 秒；JSON-only、多库与组包聚焦回归 44 项通过，pytest 7.99 秒、外层计时 9.518 秒。
- 路径缓存优化后的全量 318 项全部通过，pytest 126.34 秒、外层计时 127.908 秒。
- Windows 静态包构建成功，耗时 100.458 秒，ZIP 为 37,015,542 字节，SHA-256 `B751C23047BA98BC31F093C7C838E17C472370424B1B5ACDACA5453D9414A6CD`。
- 真实 ZIP 解压后的冻结程序门通过；源码消费门在创建空虚拟环境后暴露 `_venv_python` 仍引用已删除的 `os.name`，报 `NameError`。旧单测未实际执行该平台分支，需修复并增加回归门，然后全量重建。
- 源码门改用 `sys.platform` 并新增 Windows/Linux 解释器路径断言；`tests/test_main.py` 5 项通过，1.64 秒。失败 ZIP 在修正后的消费门中以空虚拟环境和 `-I -S` 成功生成 SVG，总回验 14.127 秒；仍按发布门要求重建最终包。
- 最终 Windows 包从头重建 92.588 秒。新 ZIP 解压后的冻结功能门 43.858 秒，源码空虚拟环境 `-I -S` 门 12.683 秒，合计 56.543 秒，均通过。
- 最终 ZIP 为 37,015,546 字节，SHA-256 `2636DCA340BA2E50519B7DE226A4AD09D491529CE85BB7918A93B8D7259F7CEB`；等待提交、远程 CI 与 Release 下载复验。
- 功能提交 `e2eb8cc` 的 Release run 32817679182 成功，v1.0.0 标签与提交一致。远端 Linux 包 51,852,342 字节，下载解压 9.625 秒，SHA-256 `9B7AD06C2789612F397A22EBB2032260F75158EBC1733A34B86F3290122096A9`。
- 远端包在隔离 Linux 容器中通过冻结完整示例门和空虚拟环境 `-I -S` 源码门，耗时 27.182 秒与 5.160 秒；目标收敛。

## 下一步

- 无。
