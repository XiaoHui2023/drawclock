# 渲染器模型

Web 浏览器为 `foreignObject` 中的 XHTML 提供 HTML/CSS 排版引擎。静态 SVG 库通常只解释自身支持的 SVG 与 CSS 子集，不负责运行任意外部内容处理器。

EOG 属于 GNOME 图像查看链。无界面测试使用同平台的 librsvg `rsvg-convert`，可以观察静态 SVG 解析与绘制；它不能代替 EOG 窗口交互，但能直接覆盖本项目发生的器件消失问题。

通过 HTTP 打开只改变承载方式。文件没有外部资源且 XML 相同，却只在浏览器正常时，应先检查 HTML、脚本、CSS 布局、外部字体和 URL 引用，不要先调整坐标。
