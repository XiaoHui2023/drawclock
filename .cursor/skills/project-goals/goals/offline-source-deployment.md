# 发行包源码离线部署

## 状态

- status: active
- owner: agent
- updated: 2026-08-25

## 期望结果

- Windows 与 Linux 发布包包含完整 `src/`、对应平台的离线 Python 依赖、ELK 运行时、器件库和示例。
- CPython 3.10～3.14 可在无软件源访问的全新虚拟环境中仅用包内文件安装依赖。
- 发布包源码能从包外工作目录生成结构有效的 SVG。
- 源码、离线依赖和关键资源有 SHA-256 清单，缺失或篡改时在执行前失败。

## 当前证据

- success: Windows 本地发行包包含 16 个源码文件和 14 个依赖 wheel；全新虚拟环境断网消费通过，耗时 18.522 秒。
- success: 同一新解压目录中的冻结程序消费通过，耗时 14.326 秒。
- failure: 旧发行包把源码放在 `source/`，而项目配置指向 `src/`；包内没有 Python 离线依赖，不能支持断网源码部署。
- failure: Windows Edge 151 的无头模式在当前桌面会话返回空 DOM；同一组 5 项浏览器几何门已在隔离 Chromium 中通过。
- failure: 首次远端 Linux 包的 `src/` 含 16 个源码文件和 5 个构建生成的 `drawclock.egg-info` 文件，源码集合不够纯净。
- worklog: `../../project-worklog/records/offline-source-release.md`

## 已尝试

- 2026-08-25: 审计现有压缩包 -> 确认源码只是参考材料，不构成离线部署闭环。
- 2026-08-25: 增加跨 Python 版本 wheelhouse 与源码清单 -> Windows 本地离线源码门通过。
- 2026-08-25: 增加 Release 解压后源码消费门 -> 等待远端 Linux 资产下载复验。
- 2026-08-25: 下载首次远端 Linux 资产核对源码集合 -> 功能文件齐全，但发现构建元数据混入，返回组包规则修正。

## 下一步

- 推送后值守 Release，下载 Linux 资产，在隔离容器中复验断网源码部署和冻结程序入口。

## 收敛条件

- Release workflow 成功，v1.0.0 指向当前提交。
- 远端 Windows/Linux 资产结构齐全、非空且摘要可核对。
- 下载后的 Linux 包通过包内源码断网消费与冻结程序消费。
