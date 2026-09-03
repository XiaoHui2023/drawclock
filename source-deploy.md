# 源码离线部署

发行包内的 `src/` 和器件库支持断网运行。代码只使用 Python 标准库，不需要安装第三方 Python 包。需要同平台的 CPython 3.10～3.14。

## Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -I -S src -i example\draw.json -l drawio-lib\drawclock -o clock-tree.svg
```

## Linux

```bash
python3 -m venv .venv
.venv/bin/python -I -S src -i example/draw.json -l drawio-lib/drawclock -o clock-tree.svg
```

自动分层和布线由源码中的确定性 Python 实现完成；发行包不包含 Node.js、ELK、浏览器或第三方 Python 运行时。

`skills/` 提供器件库、布局算法、JSON、时钟图、SVG 成品、SVG 兼容性和项目导航资料，仅用于维护，不是绘图运行时依赖。

`source-manifest.json` 记录源码、项目 skill、运行时、器件库和示例文件的 SHA-256；文件缺失或损坏时重新取得完整发行包。
