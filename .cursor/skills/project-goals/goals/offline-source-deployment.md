# 发行包源码离线部署

## 状态

- status: active
- owner: agent
- updated: 2026-08-25

## 期望结果

- Windows 与 Linux 发布包包含完整 `src/`、ELK 运行时、器件库和示例，不包含 Python 运行时依赖。
- 输入配置只接受严格 JSON；CPython 3.10～3.14 无需安装第三方包即可运行源码。
- 发布包源码能从包外工作目录生成结构有效的 SVG。
- 源码和关键资源有 SHA-256 清单，缺失或篡改时在执行前失败。

## 当前证据

- success: Windows 本地发行包包含 16 个源码文件和 14 个依赖 wheel；全新虚拟环境断网消费通过，耗时 18.522 秒。
- success: 同一新解压目录中的冻结程序消费通过，耗时 14.326 秒。
- success: 最终远端 Linux 包含 16 个源码文件、0 个 `.egg-info` 文件和 14 个 wheel，SHA-256 为 `92C78B21A9B24CCFB1E3594C2BF321F5DE654CDFFB84B1A31A51803DDCC9F6F3`。
- success: 最终远端 Linux 包在无网络 Python 3.12 容器中的源码部署耗时 4.036 秒，冻结程序消费耗时 29.535 秒。
- failure: 旧发行包把源码放在 `source/`，而项目配置指向 `src/`；包内没有 Python 离线依赖，不能支持断网源码部署。
- failure: Windows Edge 151 的无头模式在当前桌面会话返回空 DOM；同一组 5 项浏览器几何门已在隔离 Chromium 中通过。
- failure: 首次远端 Linux 包的 `src/` 含 16 个源码文件和 5 个构建生成的 `drawclock.egg-info` 文件，源码集合不够纯净。
- failure: 当前严格 JSON 入口仍经由 configlib，发行包因此携带 14 个 wheel；与收敛后的零 Python 运行时依赖目标不符。
- worklog: `../../project-worklog/records/offline-source-release.md`
- worklog: `../../project-worklog/records/json-only-zero-dependencies.md`

## 已尝试

- 2026-08-25: 审计现有压缩包 -> 确认源码只是参考材料，不构成离线部署闭环。
- 2026-08-25: 增加跨 Python 版本 wheelhouse 与源码清单 -> Windows 本地离线源码门通过。
- 2026-08-25: 增加 Release 解压后源码消费门 -> 等待远端 Linux 资产下载复验。
- 2026-08-25: 下载首次远端 Linux 资产核对源码集合 -> 功能文件齐全，但发现构建元数据混入，返回组包规则修正。
- 2026-08-25: 排除 `*.egg-info` 后重新发布并下载复验 -> 源码集合、断网安装、源码绘图和冻结程序入口全部通过。
- 2026-08-25: 审计 configlib extras 与多格式加载器 -> JSON-only 可改用标准库 `json`，同时删除 wheelhouse 工艺。

## 下一步

- 删除多格式加载器、运行时依赖、wheelhouse 组包与相关文档测试，重新验证源码和冻结包。

## 收敛条件

- Release workflow 成功，v1.0.0 指向当前提交。
- 本地 Windows 包和远端 Linux 包结构齐全、非空且摘要可核对。
- 下载后的 Linux 包不含 `vendor/wheels` 和 `requirements-offline.txt`，通过零安装源码消费与冻结程序消费。
