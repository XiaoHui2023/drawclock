# 原生 SVG 兼容修复记录

- status: done
- created: 2026-09-01 09:54 +08:00
- updated: 2026-09-01 13:05 +08:00
- scene: 原生 SVG 兼容修复、专题 skill 与发行闭环

## 当前状态

- 已确认当前提交为 `5bf4492b43bd783fd512106abd68aebb9849022c`，工作树起始干净。
- 已在 Ubuntu 24.04、librsvg 2.58 中复现器件全部缺失的失败基线。
- 已确认问题由最终 SVG 的 XHTML `foreignObject` 表现层导致，不是 HTTP、MIME、外部文件或字体加载问题。
- 已新增与器件名称无关的标签结构转换器、静态 SVG 验证器、23 种现有器件转换门和历史 `foreignObject` 漏放负例；生产入口尚未切换，下一步先证明新 Oracle 会拒绝旧实现。
- 新 Oracle 在旧生产实现上产生 23 个预期失败，证明不会继续放行浏览器专属表现层；现已把最终生成入口切换到原生 SVG 转换，并在返回产物前执行静态兼容验证。
- 浏览器端口 CTM 门已改为检查最终原生组件，不再检查旧 `foreignObject` 测试夹具。
- 新增独立 librsvg 制品 Oracle：同时检查浏览器专属元素、每组件原生图形基数和 librsvg 扁平化后的实际绘制路径；负例覆盖旧结构与渲染后组件丢失。
- Release CI 已增加冻结入口与 `python -I -S src` 两条包内输出的 GNOME librsvg 实际渲染门。
- 原冻结包与源码包冒烟脚本曾把 `foreignObject` 当作“节点存在”代理量，属于本次 Oracle 逃逸；现已改为检查原生组件组、静态元素禁用集和原生图形坐标。
- 已新增 `svg-artifact-design` 与 `svg-portability` 两个渐进披露项目 skill，分别维护原生 SVG 成品结构和跨查看器兼容合同；发行 skill 清单扩展为七项。
- 用户根部新增 `svg-artifact-production` 大 skill，保存跨项目的静态 SVG 设计、查看器兼容和 Oracle 方法；W3C Embedded Content 与 librsvg feature 页面已下载为断网资料，通用 skill 验证通过。
- 用户文档已明确最终文件为自包含原生 SVG、EOG/librsvg 可直接打开，以及不兼容器件标签的失败合同。
- 已冻结 11 项 SVG 兼容与知识指标；源码工作树 8 项已覆盖，冻结包、包内源码和远端资产 3 项保持 pending，防止局部 PASS 提升为发行完成。
- 21 份弱到 4096 时钟的仓库示例已全部重生成；总耗时 44.164 秒，扫描结果为 21 份均无 `foreignObject`、XHTML、脚本或 HTTP 资源。
- 标签转换改为对未知 HTML 几何样式失败关闭，并补充外部 `href`、CSS `url()`、`@import` 和事件属性负例，防止新器件库静默产生位置错误或外部依赖。
- 新增频率注释的结构化渲染基础：按零出度识别通用末端，按真实入口轴一行一末端，统一计算“工作频率 / SCAN / BIST”列宽、标题、红色数值与 viewBox 边界。字段仅接受字符串或非布尔数字，缺省保持空单元。
- 频率门禁已加入字段类型正反例、标题顺序/色彩、值与节点追溯、同行同 y、不同末端不共行、缺省空值、XML 转义、长值扩展画布与 viewBox 包含。
- 新增门首轮 112 项耗时 9.146 秒，111 通过；唯一失败是测试误从 `generate_elk_layout` 读取不存在的 `hard_pass` 键，非产品几何或数据失败。
- 修正 Oracle 接口后复跑 112/112 通过，耗时 8.659 秒；同时已硬性检查真实布局末端 x 同列且 y 不重复。
- 新增公开示例 `22-terminal-frequency-table.json`，覆盖三频全填、部分填写和全部省略，并纳入全示例生成与发行包。
- `draw.md`、README、JSON schema、布局算法、成图设计与 SVG 质量 skill 已同步末端行、字段映射、色彩、缺省、动态列宽和边界合同。
- librsvg 真实渲染发现最小 Ubuntu 无 CJK 字体时“工作频率”显示方框，因此不能把系统字体当自包含保证。首次临时 fontTools 安装在 45 秒后失败，可验证错误为 `Can not combine '--user' and '--target'`，系 pip 用户配置与临时目标冲突；将用 `--isolated` 有上限重试。
- 第二次 `--isolated` 仍因 Windows Store Python site 配置强制 `install.user=yes` 失败；第三次增加 `--no-user` 后成功获取临时 fontTools 4.59.2 和 Noto Sans CJK SC Regular。
- “工作频率”已转为四个固定原生 SVG 轮廓，不再依赖查看器 CJK 字体；字体本体和 fontTools 不进入仓库/发行包，仅随包提供官方 SIL OFL 1.1 许可文本（SHA-256 `6A73F954...2BF2`）。
- 轮廓修复后聚焦门 115/115 通过，耗时 8.857 秒；第 22 示例在无 CJK 字体的最小 Ubuntu librsvg 中生成与渲染耗时 1.261 秒，人工视觉复核确认四个中文字、两个英文标题、三行 clock 与红色值显示正常。
- 最终 SVG 器件组现携带 `data-node-id`，与频率值的节点/字段标记共同形成独立追溯链。冻结包门已扩展为从输入 JSON 重算零出度末端，检查同列、独占行、标题顺序/黑色/四轮廓和值映射/红色；librsvg 包内门已覆盖基础示例与频率示例的冻结/源码双入口。
- 源码清单完整性已扩展到包内全部 JSON 示例与 `licenses/`，因此第 22 示例或 OFL 许可缺失/被篡改都会阻断断网源码部署门。
- 包与接口聚焦门 120/120 通过，耗时 10.612 秒。独立频率制品 Oracle 对旧生成文件报 `terminal traceability is incomplete`，用当前源码重生成后通过，该故障注入/恢复耗时 0.427 秒。
- 22 份全量示例已按当前源码重生成。首段 01～10 约 30 秒后被单调用时间边界截断，断点后 11 单独耗时 28.419 秒，12～16 耗时 4.938 秒，17～22 耗时 1.538 秒，总执行约 64.9 秒；超大图频率列计算保持线性。
- 完整回归为 372/372 通过，pytest 报告 128.06 秒，隐藏后台计时 129.563 秒。前台首次因 30 秒工具输出边界在 58% 被截断且无残留进程，后台复跑保留了全量进度与退出码 0。
- 删除仅供人工查看的临时 PNG，仓库示例仍仅保留 SVG。七项目 skill 结构/链接/隐私验证通过，`git diff --check` 无内容错误（仅 Windows CRLF 转换提示），合计耗时 0.422 秒。
- Windows x64 冻结构建与组包退出 0，耗时 115.761 秒；产出 `dist/drawclock.exe` 和 `dist/drawclock-1.0.0-windows.zip`。内置 Node 16.20.2、ELK 0.11.1，npm 审计 0 漏洞，PyInstaller 构建成功。
- 新目录用 Python `zipfile` 完整解压耗时 2.188 秒，包 SHA-256 为 `21912DA0...42E2C`，冻结包功能门耗时 15.800 秒并通过。PowerShell 第一次前台解压受 30 秒边界中断，第二次后台包装脚本因引号转义报 `UnexpectedToken "$code"`，两者均未被当作通过证据。
- 包内源码门在 0.218 秒失败：先执行的冻结门会生成 `example/out/frozen-input.json`，清单 Oracle 过宽地递归扫描整个 `example/`，将运行产物误报为发行额外文件。这是门禁范围错误，修复后必须从干净构建重来。
- 清单 Oracle 现仅对公开发行输入 `example/draw.json` 和 `example/auto-layout/*.json` 建立完整性集，显式忽略 `example/out/` 运行产物；回归样本先在包根生成同名 `frozen-input.json`，再要求源码清单仍通过。
- 清单范围聚焦回归 5/5 通过，耗时 3.744 秒。
- 第二次干净 Windows 构建耗时 92.398 秒，新包 SHA-256 为 `EA741365A637090A8C8CC73898775143656CC95A000974B5E756839482B7DE32`，新目录解压 2.171 秒。
- 新包的冻结功能门耗时 15.398 秒并通过；在其先写入 `example/out/` 后，断网零依赖源码门耗时 13.842 秒并通过。
- 包内冻结入口与 `python -I -S src` 入口的第 22 示例均经最小 Ubuntu librsvg 2.58 真实渲染，两者均为 7 器件、6 边、41 绘制路径，频率独立 Oracle 同时通过，耗时 2.787 秒。
- 项目 SVG 成品/兼容 skill 与用户根部 `svg-artifact-production` 已补入“字体回退不等于自包含”、固定多语言标题轮廓化、许可/可访问性与无字体最小系统故障注入经验。
- 项目/用户根部 skill 复验均通过，耗时 0.340 秒。提交前编译、22 份 SVG XML/禁用集/三标题、diff 和归档哈希自审通过，有效执行耗时 1.189 秒；首次单行 Python 检查因引号嵌套报 `unterminated string literal`，改用 XML DOM 后完整重跑。
- PyInstaller 警告仅含 Windows 目标下标准库的 POSIX/Jython/代理条件导入，无项目模块、Node/ELK 资源或业务 hidden import 缺失；冻结完整功能门已直接验证该分类。
- 提交 `a3dc27980144f914e4bac15c8844ffed3a34ce8d` 已推送，耗时 5.892 秒；Release #82 成功，Ubuntu 16.04 构建 job 从 02:59:41Z 运行到 03:01:44Z。
- v1.0.0 注释 tag 剥离后精确指向 `a3dc27980144f914e4bac15c8844ffed3a34ce8d`。远端 Linux 资产大小 51,894,908 字节，下载后 SHA-256 为 `28A6B675B1F59B6B22030C1AAB9C8D20614600D59532D252BFBEBA2E80A1C4A7`，解压耗时 2.673 秒。
- 远端包在 Ubuntu 16.04 的 staticx 冻结入口与 Python 3.10 `-I -S` 源码入口均生成第 22 示例；librsvg 2.58 对两份结果均观测到 7 器件、6 边、41 绘制路径，频率 Oracle 通过，源码+渲染阶段耗时 4.363 秒。

## 结论

SVG 查看器兼容、末端行和三列频率功能已在源码、Windows 本地冻结包、Linux CI staticx 包、断网源码入口与远端下载资产上闭合。
