# 发布项目 Skills

## 状态

- status: done
- owner: agent
- updated: 2026-08-25

## 期望结果

- 发行包根目录包含五个职责互斥、渐进披露的项目 skill。
- 内容只描述 drawclock 项目，不包含私人路径、账号、用户身份或本机工作流信息。
- skill 覆盖器件库通用设计、布局算法、JSON 数据结构、成图设计和项目导航。
- 源码清单、冻结包门与源码包门都验证 skill 完整性和可用性。

## 当前证据

- success: 五个 skill 通过项目校验器、通用 quick validation、私有路径和断链故障注入。
- success: 完整回归 321 项通过；最终 Windows ZIP 的冻结程序与源码消费门通过。
- success: Release run 32866974014 成功，v1.0.0 指向 `d5e636a2035182d8c89437aead5abd9b2b423f1c`。
- success: 下载后的 Linux 包通过包内 skill、冻结程序和源码消费门；SHA-256 为 `86FC3FF1E6EC34C4F963EFB72B647ADC640FE6C91259DE39AD52E5554E9987D9`。
- worklog: `../../project-worklog/records/release-project-skills.md`

## 下一步

- 无。

## 收敛条件

- 所有 skill 通过通用 quick validation 和项目专用隐私/引用门。
- 完整测试与真实 Windows 发布包通过。
- 远端 Release 成功，下载后的 Linux 包通过 skill、冻结程序和源码消费门。
