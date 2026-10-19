# 完整发行示例与可执行演示脚本

- status: done
- created: 2026-10-19 09:58 +08:00
- updated: 2026-10-19 13:37 +08:00
- scene: 完整发行示例与跨平台演示脚本

## 记录

- 公开 v1.0.0 Windows 资产 SHA-256 `FC777E6203A7772064C161A96882A47FFB68821F94083B7F40792E9AF338F6CD` 经重新下载确认只含 `draw.json`、33、34；旧归档门仍 PASS，证明生产者和 Oracle 共享了错误的三文件子集。
- 用户要求以完整公开示例替代该裁剪，并增加 Linux/Windows 可执行演示脚本。实现所有者为发布复制清单、独立归档 exact-set、冻结 CLI 标题元数据和 CI 解压消费门。
- 已完成首轮实现：发布生产者动态收集全部公开 JSON 和说明；归档 Oracle 要求完整 exact-set 与平台匹配脚本；CLI 新增不产生画布文字的 `--title` 元数据；两个平台脚本默认向当前工作目录输出 SVG；CI 本地解压与公开回下载阶段均实际执行脚本并检查标题。旧归档将在新 Oracle 下作为失败基线，尚待测试与新鲜打包。
- 首轮验证中，旧公开包被新门禁以缺 26 个 auto-layout JSON、两份说明和 Windows 脚本正确拒绝。编译与五件套通过；目标测试 14/15，通过前唯一失败是测试夹具的示例 README 没有库路径，属于 Oracle 夹具而非产品；已补为可验证的路径改写输入。默认 `bash` 解析到不可用 WSL，且本机没有 Git Bash；本地只做 Linux 归档结构检查，脚本实际执行由原生 Ubuntu CI 强制完成。
- 修复夹具后发布/CLI 聚焦测试 15/15 通过。全量首轮在 37 分钟、81% 时因已有 3 个失败而主动中止，避免无效继续；定向重跑定位为 2 项源码哈希收据陈旧和 1 项旧标题期望。标题合同收敛为默认固定 `drawclock`、显式 `--title` 才写自定义根 `<title>`，不泄漏输入文件名且不产生画布文字；相关 91 项通过。
- 当前源码重新生成 19 项历史修复双跑，组 `20261019T025756Z-6484faab` 无失败；七轮递归组 `20261019T030258Z-0ab653a9` 连续 7 轮 clean。release gate 首次因 260 个新证据文件未进 Git 索引而正确拒绝，精确登记两个本轮证据目录后通过，证明干净 checkout 门未被绕过。
- 自主学习双轨完成：Find Skills 查询 `python release archive testing` 无结果，`shell script portability` 命中 shellcheck/portability 候选，`github release artifact verification` 仅命中低采用专用候选，未安装。官方资料确认 SVG `<title>` 是不渲染的可访问性短描述且应为首子元素；GitHub 官方支持 release/asset 完整性核验。当前实现据此把 `<title>` 放在根 SVG 第一子节点，并保留远端资产回下载消费。因技术检索只允许使用一手资料，未采用社区帖子作为实现依据。
- 用户根 `python-pyinstaller-staticx-packaging` 新增渐进专档 `references/release-example-surface.md`，`github-release` 澄清最小 allowlist 不得删减已声明用户表面；两个 skill 生命周期校验均通过。
- 完整测试最终 `706 passed in 2251.30s`。耗时最大的用例依次为 464.00s、461.23s、185.20s、147.97s、88.72s；这些是多候选、多轮 Oracle 的质量压力测试，不是单次用户生成。新鲜 Windows 归档构建与 exact-set 门通过，SHA-256 为 `2DAA17D71CDEA398D5E8334B6A010449A916C2BDC6A29665CE6AC89CF11E422A`；解压后共有 28 个 auto-layout JSON，批处理脚本生成 8155 字节 SVG，根标题精确为 `Release package title`，冻结工作流也通过。
- 单次大输入预算门使用 7302 字节反例连续运行两次，分别 32.003330s、32.533602s，均低于 60s，输出 SHA-256 一致，29/29 质量指标通过。旧包缺失复现图与新包实际脚本输出图均已渲染并人工检查；待提交、推送及公开资产反向验收后收敛。
- 上传前第一次五件套命令误加本项目未采用的 `--require-skills-manifest`，仅因缺少可选 `project-required-skills.json` 返回 FAIL；同一检查器按本仓库 legacy-absent 合同重跑 PASS，未修改或放宽检查器。最终 feedback release 19/19、归档 surface、cached diff、五件套与无未暂存项门均 PASS。
- 产品提交 `9cce6433a1cac7d41a40f4cd519f91a8f6f290ed` 已创建，但首次 push 被 managed gate 拒绝。显式项目根后取得可验证正文：项目 delivery gate 自报 PASS，宿主仍判回执不新鲜。对照两端实现定位为项目脚本使用 `--untracked-files=normal` 且不哈希未跟踪内容，宿主当前合同使用 `all` 并追加 `untracked-content` 摘要，导致两端指纹在所有状态下都不同。现按宿主算法同步项目正式入口并增加精确回归；不手填 challenge、不绕过 push 门。
- 门禁指纹同步后 24 项专项通过，受保护 amend/push 正常放行，最终产品提交为 `447c44af2e1aef34aa920062f40520acf3f00151`。Release run `39198290012` 全绿：前置质量 job 1h11m7s，Linux 1m55s、Windows 5m17s、publish 1m15s、独立公开 Windows 回验 4m26s；原生 Linux 已实际执行 `run-example.sh` 并经 librsvg 验图。
- 公开 `v1.0.0` tag 解析到产品提交。Windows/Linux 公开资产 SHA-256 分别为 `15f88e88a27a86ec2257b33cd16ea76101d9a534b7379e15fd1432b7b30dda99`、`84b642606ea4848a31b4d5cc254eda25950667f56be36ad2f12f50f3fcc32ce7`，远端预算收据为 `428e87288f4862fcc4ef83e6c5b696b8eabc8f8b06781d4478e71b6829478cb5`。本机重新下载后两包 exact-set 均 PASS；Windows 有 28 个 auto-layout JSON，批处理在调用目录生成 8154 字节 SVG，标题精确为 `Public release title`。
- 公开预算收据状态 passed，7302 字节输入两轮为 45.788081s/45.589065s，低于 60s、输出确定一致、29/29 指标零失败且目标 witness 为 0。旧包缺失与新包输出两张 PNG 已保留，目标收敛。
