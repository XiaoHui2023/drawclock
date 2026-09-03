# 用户反馈自然复现与防假完成门禁

- status: active
- created: 2026-09-03 13:32 +08:00
- updated: 2026-09-03 14:58 +08:00
- scene: 用户反馈自然复现与防假完成门禁

## 当前事实

- 用户指出上一轮没有完整复现六类布局问题，但 Agent 已声称完成并提交发布。
- 旧 `test_quality_oracle_rejects_same_root_split_rejoin_cycle` 先生成正常图，再手工重写航点；它是
  Oracle 变异自测，不是正常用户路径的 split-rejoin 复现。
- 旧的通过范围全部撤销。六个布局条目在取得公开 CLI 的两次自然红灯收据前保持 `reported`；
  对应 `src/**` 产品 owner 冻结。
- 本轮只允许修改项目账本、复现语料、只读 Oracle、门禁与项目 skill，不修改布局生产实现。

## 本轮目标

- 项目问题账本逐条记录所有反馈，禁止复合样例替代单项证据。
- 结构门、修复授权门、完成门具有不同退出语义；结构正确不等于允许修复。
- 人工改图、故障注入、monkeypatch、测试专用入口和自报状态不能签发自然复现收据。
- 未复现时机器返回非零，commit/push/release 不得扩大为布局问题已解决。

## 当前边界

- 当前范围只建设和验证复现工艺与门禁，不声明六个布局问题已复现或已解决。
- 本地 managed hook 之外的管理员和远端仓库管理员仍是信任边界；远端 Required Check 是否启用
  需在 GitHub 侧单独核实。

## 13:42 问题登记

- `FB-ROOT-001` 到 `FB-PORT-006` 已分别写入机器账本，全部为 `reported`。
- `META-CLAIM-007` 记录未复现却提交发布的声明逃逸；它不会因布局回归测试通过自动关闭。
- 每条账本均声明冻结基线、公开 CLI、原始 SVG、只读 Oracle 和独立收据路径；尚无收据。

## 13:50 项目交付门

- `.codex/quality-gate.json` 将唯一项目验收命令绑定到当前 Git tree、策略哈希、命令哈希和随机
  challenge。
- 项目只有 Agent 记录/复现基础设施变化时校验账本结构；一旦工作树包含 `src/**` 变化，自动提升
  为 `--phase solve`，六条自然复现收据缺任一项即拒绝提交、推送和发布。
- 本门不把开放问题误报为已解决；它只证明当前修改没有越过“先复现再改产品”的边界。

## 14:02 首次写入前置门

- v2 policy 新增 `write_preconditions`，明确匹配 `src/**`；managed PreToolUse 在 `apply_patch` 等
  能解析目标的写工具发生副作用前调用 solve 阶段。
- 账本六条均未复现，因此当前 wrapper 必须返回非零；Agent 仍可修改复现语料、Oracle、测试、
  项目记录和门禁本身。
- 无明确目标的 shell 写入是本地解析边界，commit/push/release 的 delivery gate 会再次检查整个
  工作树；不能把本地 hook 表述为管理员不可绕过。

## 14:21 项目反例测试

- `tests/test_feedback_reproduction_gate.py` 验证开放问题允许维护账本，但 solve 阶段必须失败并逐条
  报出六个问题。
- 测试要求 `src/**` 写入前置命令保持启用，并拒绝把 pytest、monkeypatch、mutation 或改写输出
  注册为用户自然复现。
- 测试只验证门禁，不是六个布局问题的复现证据。

## 14:26 独立发布检查器

- 新增项目内自包含的 `release` 阶段，干净 CI 不依赖用户根 skill；它要求每条问题均已自然复现、
  修复验证且状态关闭，并逐项打印尝试、分析和未复现原因。
- 非发布阶段继续委托用户根验证器，避免项目规则与通用工艺分叉。
- 此时仅完成检查器实现，尚未接入打包脚本和 GitHub Actions；因此不得声称发布入口已经封闭。

## 14:31 发布入口与逐项尝试

- 六条 issue 分别记录现有思路、正常入口核查结果、分析、未复现原因和下一复现条件；没有任何条目被提升为 reproduced。
- 本地 `pack.sh` / `pack.bat` 在环境和产物变化前调用 release 门；GitHub Actions 新增 feedback 前驱，build 与 publish 均依赖它并移除 `always()`。
- 托管 hook 向项目交付门传递触发命令；项目对 pack/`gh release` 强制选择 release 阶段，而普通账本提交仍可选择 structure。
- 当前 release 门按预期返回 1，列出六条问题、缺失收据/修复验证和两个开放流程事故；这是“禁止发布”的成功负例，不是布局质量通过。

## 14:36 机器门自测

- 用户根自然复现 validator 自测通过；托管 hook 主套件 44 项、模块隔离套件 32 项通过。
- 项目反馈门 7 项通过：逐 issue 失败清单、solve 阻断、pack 早停顺序、CI 依赖与禁止 `always()` 均由静态/执行测试约束。
- 首轮新增命令透传测试因临时策略未保护 `gh release` 而没有触发 mock，已改用策略保证保护的 `git push` 后通过；该失败没有被隐藏。

## 14:40 托管安装与首次宿主探针

- 托管安装器完成 44+32+33+6 项测试、4/4 mutation kill、25 文件 doctor，并热安装成功。
- 首次真实交互宿主探针实际看到了 UserPromptSubmit 注入；随后因本机 Codex CLI 0.140.0 不支持指定的 `gpt-5.6-luna` 返回 HTTP 400，未进入产品写入拒绝阶段。
- 该次不计宿主闭环通过；按有上限策略仅再以兼容模型重试一次。

## 14:44 宿主探针有界收敛

- 第二次改用 Codex CLI 可运行的 `gpt-5.4`；会话成功加载项目上下文、执行 UserPromptSubmit 及多个 Pre/PostToolUse，但 90 秒预算内 Agent 一直读取资料，尚未发起 README 写入。
- 因而语义注入已在真实宿主可见，但“随后的产品写入被拒绝”只由项目上下文 33 项单测证明，尚无完整宿主级写入拒绝证据。
- 两次有界尝试已用尽，本轮不再无限等待；恢复条件是精简探针提示/启动上下文或升级 CLI 后重新运行四路径宿主验收。

## 14:49 完整回归与真实 pack 早停

- 直接 `unittest discover` 因未加载 pyproject 的 `src/tests` pythonpath 出现 7 个导入错误；改用项目正式 pytest 入口后 409 passed、5 skipped，耗时 88.43 秒。
- 真实执行 `tools/pack.bat` 在 release 检查器处 0.85 秒返回 1，逐条打印六个 issue；未进入 venv、pip、npm、PyInstaller 或 bundle 阶段。
- 该失败正是当前开放反馈下的预期发布阻断；不能将其表述为发行包验证通过。

## 14:53 触发命令分级闭环

- 项目交付门将 `pack.bat`、`pack.sh`、`bundle_release.py` 和 `gh release` 统一映射到自包含 release 检查器；源码修改的 commit 仍走 solve，其它提交走 structure。
- 8 项专项测试通过，覆盖三类触发命令、阶段选择、逐 issue 报告、pack 早停与 CI 依赖；py_compile 与 diff whitespace 检查通过。

## 14:58 远端发布负门验证

- 质量基础设施检查点 `291274e` 已推送 main；GitHub Actions run `33724488973` 在反馈门失败。
- 同一 run 的 Linux Ubuntu 16.04 build 与 Publish GitHub Release 均为 skipped；feedback job 从开始到结束约 10 秒。
- 远端 `v1.0.0^{}` 仍为 `0a2f48b`，现有资产发布时间未变化；因此本次没有发布新包，也没有移动滚动 tag。
- `META-RELEASE-008` 的发布旁路修复已有真实 CI 证据，可以关闭；六条布局 issue 与 `META-CLAIM-007` 继续开放并阻断发布。
