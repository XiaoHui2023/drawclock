# v1.0.0 单功能重构

## 状态

- status: completed
- owner: agent
- updated: 2026-08-14

## 结果

- `gate_a_tap` 末端路线为直线，节点端口与线端点精确相接。
- 美观、正确性、可读性和拐点数优先于路线长度与画布面积。
- CLI 只保留直接绘图；extract、reload、旧别名和关联文件已删除。
- 远端 `v0.0.0` 保持在旧提交，`v1.0.0` 指向本次重构提交。
- 源码测试、压力测试、本地静态包、GitHub Release 和下载后静态包均已验证。

## 证据

- `gate_a_tap` 航点为空；全图 4 个拐点、0 个交叉，生成耗时 24.207 ms。
- 295 项源码测试通过，最终完整回归耗时 133.28 秒。
- Windows PyInstaller 构建耗时 10.6 秒，v1.0.0 ZIP 组包耗时 23.8 秒，解压归档门禁耗时 49.3 秒。
- GitHub Release 工作流 31782092072 成功，发布 `drawclock-1.0.0-linux.tar.gz`。
- Release 下载包 SHA-256 为 `89A8150957F8FC9E095059B1512366CEEC5F3232E8EA42F16096ACD90AB6A657`。
- 下载后的 Linux 冻结程序在容器中通过全流程门禁，耗时 30.874 秒。
- 远端 `v0.0.0^{}` 为 `8befc99b9becf4b271938e64cc15c993cce478c1`；`v1.0.0^{}` 为 `bc05a9aa509563c7e25e4c465bf3697252e1b4e4`。
