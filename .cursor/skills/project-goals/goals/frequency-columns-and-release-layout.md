# 频率列裁剪与发行目录收敛

## 状态

- status: done
- owner: agent
- updated: 2026-09-12

## 期望结果

- 右侧工作频率、SCAN、BIST 各列只有在至少一个末端值非空时才显示；三列全空时不生成频率表，也不为其预留画布。
- 新规则作为独立终态质量指标，对每张测试图执行完整指标集合，覆盖单列、任意列组合、空字符串和全空反例。
- 默认发布压缩包使用 `libraries/*.xml` 平铺器件库，并把用户文档集中到 `doc/`；根目录不再出现 README 或旧 `drawio-lib/`。
- 发布物仍能从全新解压目录运行，文档命令使用包内新路径，旧的源码仓库开发路径不受发布目录映射影响。
- 错列、右移 mux 不得诱发公共根主干在中部过早离开纵向总线、穿入分支带后再向下；边界/纵向主干候选在交叉与折点上支配时必须采用该候选。

## 当前证据

- failure: 公开 CLI 生成 `31-node-descriptions.json` 时只有 `func_freq` 有值，SVG 仍包含工作频率、SCAN、BIST 三个表头。
- failure: 公开 CLI 生成 `01-linear.json` 时三类频率全空，SVG 仍包含 `<g class="frequency-table">` 和三个表头。
- failure: 当前发布归档仍以根级 `README.md`、`draw.md` 和 `drawio-lib/drawclock/*.xml` 暴露旧目录。
- failure: 用户报告错列且更靠右的 mux 会诱发公共根线路提前穿入右侧再向下，造成大量异网交叉；现有 `premature_interior_trunk_entry` 指标虽已注册，但必须用该诱因重新攻击，确认适用性和 Oracle 没有逃逸。

- success: 修复后 31 号仅输出 `func_freq`，01 号不生成频率表；27 张公开图和 27 张仓库 SVG 均逐图通过完整 28 项指标。
- success: 错列 mux 定向搜索 24/24 未复现，四个固定回归 seed 无过早内部主干入口；七轮递归攻击连续全绿。
- success: Windows 包使用平铺 `libraries/*.xml` 和集中 `doc/`；全新解压后冻结程序生成两张代表图并各自通过 28 项指标。
- success: GitHub Release run `34609031939` attempt 2 三个 job 全部成功，publish 从公开 Release 回下载 Linux 资产并通过冻结消费；`v1.0.0` 解引用精确指向产品提交 `25196cf`。
- success: 本机独立下载的 Linux 资产为 17,040,415 bytes，SHA-256 `e74e60fc80016c08f719e88028020a84070d25edeb055c3f4a956a714a7b4525`，与 GitHub API digest 一致；归档 exact-set 门通过，包含 24 个平铺 XML、集中 `doc/` 且无根级文档或 `drawio-lib/`。

## 已尝试

- 2026-09-11: 用 Python 3.13 `-I -S src` 和公开示例形成修改前结构化 XML 红灯；定位布局 owner 为 `_frequency_table()` 固定三列分配，发布 owner 为 `bundle_release.py` 的原路径复制。
- 2026-09-12: 排除仓库 Actions 权限、runner 标签和其它非终态 run 后，正常取消卡死的 run attempt 1，并按 GitHub 官方 REST API 对同一 run 执行 re-run；attempt 2 保持产品 SHA `25196cf`，数秒内获得 GitHub-hosted runner。

## 下一步

- 无.

## 收敛条件

- 聚焦测试、全部测试、全公开制品×完整指标、递归攻击和发行归档 exact-set 全部通过。
- 新鲜 Windows 发布包在全新解压目录以 `libraries/` 成功生成并通过终态质量系统；远端发行资产回下载复验通过。
