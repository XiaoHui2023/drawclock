# SVG 查看器兼容性分析

- status: done
- created: 2026-09-01 09:54 +08:00
- updated: 2026-09-01 13:05 +08:00
- scene: Ubuntu EOG 显示异常根因与方案比较

## 问题与失败基线

现有最终 SVG 把每个器件的全部图形与文字放进 `foreignObject` 的 XHTML/CSS 子树。浏览器经 HTTP 打开时具备 HTML 排版引擎，因此显示完整；Ubuntu 24.04 的 librsvg 2.58 渲染同一 `example/generated/01-linear.svg` 时只保留标题和三条边，所有器件消失。该结果复现了 EOG 症状。

## 权威依据

- W3C SVG 2 把 `foreignObject` 定义为调用其它内容处理器的扩展点，并说明 SVG 用户代理不必支持任意外部内容类型。
- librsvg 官方支持元素表包含原生 `svg`、基础图元和 `text`，没有 `foreignObject`；librsvg 只承诺其列出的 SVG/CSS 子集。
- librsvg 是 GNOME 平台的 SVG 渲染库并提供缩略图与 Cairo 渲染能力，因此 `rsvg-convert` 是 EOG/GNOME 查看链的合适无界面兼容代理。

## 候选与结论

1. 保留 XHTML 并要求用浏览器打开：不满足本地查看器兼容性。
2. 给 `foreignObject` 增加浏览器与查看器双份 fallback：会保留两套表现来源，查看器能力选择不稳定，也不利于端点与文字占用的单一几何来源。
3. 把每个器件栅格化后嵌入：兼容但失去矢量缩放，放大质量和文件体积不合格。
4. 从器件库标签的结构化 HTML 子集计算并发射原生 SVG 图元与原生文字：保持矢量、自包含、端口坐标与当前布局不变；无法静态表达的标签结构显式报错。

选择方案 4。转换按标签结构和 CSS 几何计算，不按器件名称、实例名称或示例坐标分支。

当前实现已在浏览器与 Ubuntu 24.04 librsvg 2.58 中生成相同完整拓扑。原生输出包含 10 个组件图形与 9 条边；librsvg 扁平化结果包含 43 条实际绘制路径。旧产物被静态结构门在 `foreignObject` 处拒绝。

## 质量指标注册表

| ID | 用户可观察结果 | 权威证据 | 负例 | 状态 |
| --- | --- | --- | --- | --- |
| SVG-COMPAT-01 | 文件不依赖浏览器 HTML | 最终 XML 静态禁用集 | `foreignObject` + XHTML | covered |
| SVG-COMPAT-02 | 每个逻辑节点都有可见器件 | 组件组、原生图形基数与 librsvg 绘制路径 | 只剩背景与边的扁平化结果 | covered |
| SVG-COMPAT-03 | 线端点与可见引脚重合 | 浏览器独立 CTM 几何 | gate 气泡中心错误锚点 | covered |
| SVG-COMPAT-04 | 本地打开不加载附件或网络 | URL、事件与资源引用检查 | 外部 `href`、事件属性 | covered |
| SVG-COMPAT-05 | 器件、文字和路线不被裁切 | 完整可见几何与 `viewBox` 门 | 画布下方路线 | covered |
| SVG-COMPAT-06 | 浏览器显示完整 | Edge 最终原生组件运行门 | 旧 HTML 夹具不再作为产品证据 | covered |
| SVG-COMPAT-07 | GNOME 静态查看链显示完整 | Ubuntu librsvg 扁平化与独立路径 Oracle | 旧产物器件全部丢失 | covered |
| SVG-COMPAT-08 | 冻结发行程序生成兼容 SVG | 解压包内二进制 + librsvg | 缺节点追溯的陈旧产物 | covered-local-package |
| SVG-COMPAT-09 | 断网源码入口生成兼容 SVG | 解压包 `python -I -S src` + librsvg | 冻结输出污染清单扫描范围 | covered-local-package |
| SVG-COMPAT-10 | 用户下载的远端资产与本地证据一致 | Release 下载、哈希、解压、双入口复验 | 复用本地产物冒充下载 | covered-remote |
| SVG-KNOWLEDGE-01 | 发行包含完整 SVG 维护知识 | 七个 skill 结构、链接、UTF-8 与隐私门 | 缺目录、断链、私人路径 | covered |
| SVG-FREQ-01 | 每个末端独占一行且末端同列 | 零出度集合、末端 x 和行轴不变量 | 两末端共行、末端左右摇摆 | covered-source |
| SVG-FREQ-02 | 标题顺序为工作频率/SCAN/BIST，数值红色且按行对齐 | 结构化 data 属性、列 x 与末端行轴 | 交换列、红色标题、值错行 | covered-source |
| SVG-FREQ-03 | 缺省频率为空且不裁切长值/标题 | 动态文字列宽与 viewBox 包含门 | 缺省占位文本、长值越界 | covered-source |
| SVG-FREQ-04 | 无系统中文字体仍正确显示中文标题 | SIL OFL 开放字体固定轮廓 + 最小 Ubuntu librsvg | CJK 字体缺失时四个方框 | covered-source |

声明范围为当前源码、Windows x64 本地冻结包、Ubuntu 16.04 staticx 远端包与 Ubuntu 24.04 librsvg 2.58 渲染链。

## 已验证

- 浏览器和 librsvg 都必须绘出所有器件、文字、边与端口接触点。
- 产物中不得包含 `foreignObject`、XHTML、脚本或外部资源引用。
- 已知旧产物必须被兼容门拒绝；纯原生成功基线必须被接受。
- 源码入口、冻结包和远端发行资产必须消费同一转换实现与同一门禁。
