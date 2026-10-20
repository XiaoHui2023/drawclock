# 发行包源码离线部署

## 状态

- status: active
- owner: agent
- updated: 2026-10-20

## 期望结果

- Linux 正式发布包包含完整、干净的 `src/`，现有冻结程序、文档、器件库、示例和 Shell 演示路径保持不变。
- `src/` 是独立的离线部署入口；现有 `example/run-example/*.sh` 仍调用包内冻结可执行程序，不能切换到源码入口。
- 从 Linux 包中取用 `src/`、`libraries/` 和输入 JSON 后，只依赖系统 CPython 3.9 或更高版本即可离线生成 SVG，不需要 PyInstaller 可执行程序或第三方 Python 包。
- 输入配置只接受严格 JSON；CPython 3.10～3.14 无需安装第三方包即可运行源码。
- 发布包源码能从包外工作目录生成结构有效的 SVG。
- 源码和关键资源有 SHA-256 清单，缺失或篡改时在执行前失败。

## 当前证据

- success: Python 项目运行时依赖为空，严格 JSON 由标准库 `json` 解析；发行包不含 requirements 或 wheelhouse。
- success: Windows 本地最终 ZIP 解压后，冻结门 43.858 秒、空虚拟环境 `-I -S` 源码门 12.683 秒，均通过；SHA-256 为 `2636DCA340BA2E50519B7DE226A4AD09D491529CE85BB7918A93B8D7259F7CEB`。
- success: Release run 32817679182 成功，v1.0.0 指向功能提交 `e2eb8cc57de980dc103a4959ab851c7cacb36e87`。
- success: 远端 Linux 包 SHA-256 为 `9B7AD06C2789612F397A22EBB2032260F75158EBC1733A34B86F3290122096A9`；隔离容器冻结门 27.182 秒、源码门 5.160 秒，均通过。
- failure: 2026-10-20 复核当前 `v1.0.0` 的 `drawclock-1.0.0-linux.tar.gz`，归档中没有任何 `src/` 条目；`bundle_release.py` 未复制源码，`check_release_archive.py` 还会把源码判为 unexpected files。
- worklog: `../../project-worklog/records/offline-source-release.md`
- worklog: `../../project-worklog/records/json-only-zero-dependencies.md`

## 已尝试

- 2026-08-25: 审计现有压缩包 -> 确认源码只是参考材料，不构成离线部署闭环。
- 2026-08-25: 增加跨 Python 版本 wheelhouse 与源码清单 -> Windows 本地离线源码门通过。
- 2026-08-25: 增加 Release 解压后源码消费门 -> 等待远端 Linux 资产下载复验。
- 2026-08-25: 下载首次远端 Linux 资产核对源码集合 -> 功能文件齐全，但发现构建元数据混入，返回组包规则修正。
- 2026-08-25: 排除 `*.egg-info` 后重新发布并下载复验 -> 源码集合、断网安装、源码绘图和冻结程序入口全部通过。
- 2026-08-25: 审计 configlib extras 与多格式加载器 -> JSON-only 可改用标准库 `json`，同时删除 wheelhouse 工艺。
- 2026-10-20: 用户重新确认 Linux 正式归档必须直接包含独立 `src/` -> 当前公开归档自然复现缺失，目标重新打开。

## 下一步

- 将 Linux 归档的源码 exact-set、缓存排除、解压后 `python3 -I -S src` 离线运行和远端回下载复验接入发布硬门；保持现有 Shell 示例继续调用冻结程序。

## 收敛条件

- Release workflow 成功，v1.0.0 指向当前提交。
- 本地与远端 Linux 归档含当前全部产品 `src/*.py`，不含 `__pycache__`、`*.pyc` 或 `*.egg-info`，归档源码字节与提交一致。
- 下载后的 Linux 包同时通过冻结程序消费、全部现有 Shell 示例消费和系统 Python 的 `-I -S src` 离线源码消费。
