# 发布项目 Skills

## 状态

- status: active
- owner: agent
- updated: 2026-08-25

## 期望结果

- 发行包根目录包含五个职责互斥、渐进披露的项目 skill。
- 内容只描述 drawclock 项目，不包含私人路径、账号、用户身份或本机工作流信息。
- skill 覆盖器件库通用设计、布局算法、JSON 数据结构、成图设计和项目导航。
- 源码清单、冻结包门与源码包门都验证 skill 完整性和可用性。

## 当前证据

- worklog: `../../project-worklog/records/release-project-skills.md`

## 下一步

- 建立 skill 内容和验证脚本。

## 收敛条件

- 所有 skill 通过通用 quick validation 和项目专用隐私/引用门。
- 完整测试与真实 Windows 发布包通过。
- 远端 Release 成功，下载后的 Linux 包通过 skill、冻结程序和源码消费门。
