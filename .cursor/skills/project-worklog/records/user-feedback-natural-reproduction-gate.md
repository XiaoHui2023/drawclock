# 用户反馈自然复现与防假完成门禁

- status: active
- created: 2026-09-03 13:32 +08:00
- updated: 2026-09-03 14:21 +08:00
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
