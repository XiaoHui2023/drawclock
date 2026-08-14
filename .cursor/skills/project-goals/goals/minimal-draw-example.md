# 最小通用 draw 示例

## 状态

- status: achieved
- owner: agent
- updated: 2026-08-12

## 期望结果

- 发布示例只包含 `kind` 与必要的 `source`。
- 不填写 `component` 和 `*_kind` 时仍能解析全部示例器件。
- 缺少 `kind` 时立即报错。
- 发布压缩包包含修改后的 `example/draw.json`。
- 发布压缩包自带 Node.js 与 ELK 运行时，隔离宿主 PATH 后仍可生成 SVG。
- PLL 与 clock 的线端坐标和浏览器可见触点一致。

## 当前证据

- success: v1.0.0 Windows 压缩包已在新目录解压，并隔离宿主 PATH 完成 SVG 示例检查。
- failure: 修改前的发布示例为每个器件填写 `component`，并包含多个器件库专用属性。

## 已尝试

- 2026-08-12: 删除示例中的可选字段并增加直接断言。
- 2026-08-12: 内置固定版本 headless Chromium、Node.js 与 ELK；修复 Windows 批处理调用 `npm.cmd` 后提前退出。
- 2026-08-12: 将 HTML 标签偏移移入 `foreignObject` 视口，并统一 4 位坐标序列化；PLL/clock 浏览器 CTM 与故障注入通过。

## 下一步

- 推送 main，并等待滚动 Release 工作流与 Linux 解压后冻结门禁通过。

## 收敛条件

- 相关测试、全量测试、发布包内容与冻结程序示例均通过。
