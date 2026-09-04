# Managed delivery gate 调用误判分析

- status: done
- created: 2026-09-04 18:30 +08:00
- updated: 2026-09-04 18:35 +08:00
- scene: 闭环提交后的新鲜回执与 push 误阻断诊断

## 问题

产品提交与公开 Release 已完成后，又产生一笔闭环记录提交。Agent 直接运行 `tools/run_agent_delivery_gate.py`，看到缺少 `CODEX_GATE_CHALLENGE`、策略哈希和命令哈希的 exit 2，随后仍依据触发前读到的旧回执判断无法签发，因此没有继续推送闭环记录提交。

## 可验证事实

- 直接运行项目 delivery command 稳定返回 exit 2，且 ready receipt 的 SHA-256 不变；这是拒绝伪造 challenge 的负基线。
- 托管运行时 `gate_runtime.delivery.run_delivery_gate` 会在子进程环境中注入三项绑定值；`handle_pre_tools` 对每个受保护命令生成新 challenge，`handle_stop` 对 dirty 项目执行同一正式 gate。
- ready receipt 在 `2026-09-04 17:17:23 +08:00` 由 Stop 更新到当时的闭环提交树 `32b303bb4ce14d426815c1241c6bd307a508afc6`，说明签发器与 Stop 路径可用。
- 用户根 Hook 成功/失败双基线为 44 个核心测试、32 个模块化测试和 35 个项目上下文测试全部通过，没有发现按 turn 复用验收或跨盘根解析失败。
- 随后的受保护 commit `13227a45738ae4258f77b15e0380c73b38cc945c` 已成功执行，但回执的 challenge、树和修改时间完全未变；新 `HEAD^{tree}=9f9e79e05f60840e3ff21c1642f6e9e697eba87e`。这是 PreToolUse 没有观察到嵌套命令的直接反例。
- 当前 `codex-cli 0.140.0` 与 OpenAI issue #23411 所述 Code Mode `exec` 不发出 PreToolUse 的实现缺口一致；官方文档描述的是目标行为，不能替代本机真实宿主验证。

## 根因与影响

根因有两层：首先把 managed-only 子进程接口当作普通 CLI，并把预期负基线误判为 Hook 故障；继续实验又确认当前 Desktop Code Mode 的嵌套 `exec_command` 没有进入 PreToolUse，受保护命令可以在回执陈旧时执行。实际产品提交、`v1.0.0` 标签、远端 Release 与公开资产不受影响，但机器级“副作用前阻断”对这条工具路径并不成立，闭环提交的 push 必须采用受控桥接或等待 Stop 后在新回合执行。

## 解决与防复发

- 项目脚本的缺环境错误改为明确说明“managed-hook-only / expected negative control / 禁止手工补变量”，并增加 subprocess 回归测试。
- 通用硬门禁知识库固定诊断顺序：记录触发前树与回执，触发 managed Stop 或真实受保护操作，再核对新 challenge、回执修改时间和当前树；内层 stderr 不代表外层 Hook 结果。
- 当前交付使用一次性受控桥接：把原 push 命令交给已安装 managed Hook 入口，由 Hook 自行生成 challenge；Hook 通过后先精确核对新回执树，再执行 push。禁止手工设置 challenge。
- 机器级覆盖缺口不能由项目代码修复；当前无需 Quarantine、重装或重启。恢复条件是升级到包含 Code Mode 嵌套 Hook 修复的 Codex 版本，并重新通过真实宿主 Pre/Post/Stop 故障注入。
