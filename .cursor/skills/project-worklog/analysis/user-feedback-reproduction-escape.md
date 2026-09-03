# 用户反馈复现与声明逃逸分析

- status: active
- created: 2026-09-03 13:32 +08:00
- updated: 2026-09-03 14:31 +08:00
- scene: 人工故障冒充复现与声明逃逸根因

## 问题

上一轮把部分自然样本、人工改坏路线的 Oracle 自测、修复后绿灯和全量回归混为“六项都已复现并
解决”。实际缺少逐条旧版本自然红灯，导致 `reproduction_escape` 与 `claim_escape`。

## 根因

1. 项目没有独立的用户反馈问题账本，复合描述被压成一个宽泛目标。
2. 测试合同只有 success/fault，没有独立 `user_reproduction` 证据类别。
3. 变异测试能证明统计器识别形状，却被错误提升为真实输入能产生该形状。
4. 提交/发布门只消费回归结果，没有检查“每条反馈是否先在冻结旧版本经公开入口失败”。
5. 完成声明没有绑定精确 issue 集合，因此局部通过被扩大为全部完成。
6. `.github/workflows/release.yml` 的 build 没有反馈复现前驱；publish 使用 `always()`，扩大了依赖失败时继续求值的旁路面。
7. 项目交付门仅依据 `src/**` 是否变化选择 solve/structure；门禁基础设施提交因此只跑 structure，无法代表可发布。

## 采用方法

- 状态机：`reported -> reproduction_in_progress -> reproduced -> fix_in_progress -> fixed_verified -> closed`。
- 自然复现：冻结 Git revision，以公开 CLI 对有效 JSON 运行两次，原始 SVG 交给只读独立 Oracle；
  runner 绑定命令、输入、产物、baseline tree 和 Oracle 哈希。
- Oracle 自测：人工变异单独记为 `oracle_self_test`，永远不能提升问题状态。
- 产品冻结：自然复现门未绿时，只允许问题账本、有效输入、runner、只读 Oracle 和门禁路径变化。
- 声明约束：全部布局问题关闭前，本轮只能声明复现流程/门禁的已验证范围。
- 发布闭包：本地 pack 先跑自包含 release 门；CI build 显式 `needs` feedback gate，publish 同时依赖 gate 与 build，禁止 `always()`。
- 语义触发：用户表达“仍然、错误、没复现、质量不过关”等负反馈时，托管 hook 先要求写入问题账本；产品路径在登记前不可修改。

## 待验证

- 六条问题各自的最小自然红灯与复杂交叉自然红灯均未取得。
- 项目 PreToolUse 是否能在第一次 `src/**` 写入前拒绝，需通过真实 hook fixture 和交互宿主探针。
- GitHub 仓库是否启用了不可绕过、限定来源的 Required Check 尚未核实。
- 新 CI 的预期结果是 feedback job 失败、build/publish skipped；在六条产品问题解决前不应追求绿色 Release workflow。
