# 注释颜色、Python 版本与发行表面分析

- status: done
- created: 2026-09-11 16:17 +08:00
- updated: 2026-09-11 19:43 +08:00
- scene: description_color、最低 Python 与精简归档

## 已确认事实

- SVG 注释当前依赖组级固定 CSS，没有节点级颜色数据。
- 最低版本不能只靠语法编译推断；Python 3.9.0 的实际入口已在 `typing.TypeAlias` 处失败，运行模块另含 `zip(strict=True)`。
- PyPA 的 `requires-python` 是安装器使用的版本合同；多版本矩阵仍需真实解释器执行，静态最低版本扫描只作补充。
- CSS Color 允许的语法远多于旧 SVG 渲染器稳定支持面。输入应严格解析并转成 sRGB `#rrggbb` 或 `#rrggbbaa`，不把 `var()`、`url()`、`currentColor` 或宽色域表达式原样注入 SVG。
- 默认可执行归档与源码分发职责不同。仓库 tag 已保存完整源码；默认归档可按最终用户运行 allowlist 裁剪，但嵌入 Noto 字形产生的 OFL 文本必须保留。

## 方案

- 字段名采用 `description_color`，与被修饰字段一一对应，避免和器件图形颜色混淆。
- 运行时只用标准库实现命名色、十六进制、RGB(A)、HSL(A) 与 HWB 的解析和规范化，不增加项目依赖。
- 颜色质量由独立 SVG Oracle 比较配置期望色与每行 `<text fill>`，几何指标与颜色指标分开计数但对每张图共同执行。
- 最低 Python 目标暂定 3.9，以本机真实 3.9.0 作为下界门；低于该版本不作未经执行的兼容声明。
- 默认归档保留 executable、README、draw.md、器件库、`example/draw.json`、颜色字段示例与必须许可；移除源码、开发元数据、项目 Skills 和批量质量语料。

## 待验证

- 全颜色语法边界、大小写、空白、透明度和拒绝注入测试。
- Python 3.9 的完整源码 smoke 与相邻版本测试。
- 精简归档的冻结消费和 README 命令可用性。

## 冲突决议

- 旧发行约定要求默认附件含完整源码、项目 Skills 和全部示例；最新要求明确要求默认压缩包直观、简洁并移除无用开发文件。最新要求取代默认附件内容，源码仍由仓库和滚动 tag 完整保存，不删除源码能力或历史证据。
- Noto CJK 字形轮廓直接嵌入最终 SVG，SIL OFL 要求保留许可文本；`licenses/NotoSansCJK-OFL-1.1.txt` 属于依法必须文件，不按普通无用资料删除。
