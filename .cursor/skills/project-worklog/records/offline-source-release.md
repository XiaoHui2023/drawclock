# 发行包源码离线部署

- status: active
- created: 2026-08-25 11:19 +08:00
- updated: 2026-08-25 11:55 +08:00
- scene: 发行包源码离线部署

## 当前状态

- 已确认 Windows 压缩包含 `source/`，但 `pyproject.toml` 仍指向 `src/`。
- 包内没有离线 Python 依赖，断网环境不能安装 configlib 及各输入格式依赖。
- 已保留原始 `src/`，加入 CPython 3.10～3.14 平台 wheelhouse、文件摘要和全新虚拟环境断网运行门。
- 源码运行时发现同时支持开发目录 `.runtime/` 与发行目录 `runtime/`。
- 首轮聚焦测试 16/17 通过；组包假项目缺少必须纳入摘要的器件库文件，夹具已补齐。
- 修正后聚焦测试 17 项通过；Windows wheelhouse 已覆盖 CPython 3.10～3.14，共 14 个 wheel。
- Release workflow 已加入解压包源码断网消费门，冻结程序测试保持独立。
- 全量测试中 309 项通过，5 个浏览器几何测试因 Windows Edge 151 返回空 DOM 失败；隔离 Chromium 首次因 root sandbox 退出 1，测试启动器已限定在 Linux root 环境加入 `--no-sandbox`。
- 隔离 Chromium 几何测试 5 项通过；其余 309 项通过，第三方 configlib 有一条已知弃用提示。
- Windows 包含 16 个源码文件和 14 个 wheel；断网源码消费 18.522 秒，冻结程序消费 14.326 秒。

## 下一步

- 重建压缩包并从新解压目录验证。
- 推送后下载远程 Linux 资产复验。
