# 构建与验证

## 开发验证

1. 在 `scripts/drawio_lib/components/` 中用共享几何构造器实现器件。
2. 注册器件并重新生成 `drawio-lib/drawclock/<title>.xml` 与预览图。
3. 检查文件数等于器件数、每个文件恰好一个条目、title 全局唯一、负载可解码、尺寸为正、顶点结构唯一。
4. 对每个端口比较 style 锚点和可见引脚末端，误差必须为零或处于明确的数值容差内。
5. 生成包含该器件的最小连接结构，检查每条边精确连接到预期端口。
6. 再用长标签、未连接可选端口、多输出和多库合并做边界测试。

项目命令：

```text
python scripts/build_drawio_lib.py
python -m pytest tests/test_build_drawio_lib.py tests/test_port_graphic_alignment.py tests/test_drawio_ports.py
```

## 拒绝条件

- title 重复或缺失；
- 单个 XML 包含零个或多个器件；
- w/h 与内部几何不一致；
- 端口不在可见引脚端点；
- 标签模板没有烘焙，SVG 中残留占位符；
- 边进入错误输入、错误输出或器件外框；
- 新器件要求布局器按名字分支；
- 单独预览正常，但真实 JSON 到 SVG 失败。
