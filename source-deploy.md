# 源码离线部署

发行包内的 `src/`、`runtime/` 和器件库支持断网运行。Python 运行代码只使用标准库，不需要安装第三方 Python 包。需要同平台的 CPython 3.10～3.14。

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

`runtime/` 中的 Node.js 与 ELK 负责自动分层和布线，发行包已随平台提供，无需单独安装。删除该运行时会失去自动布局能力。

`skills/` 提供器件库、布局算法、JSON、成图设计和项目导航资料，仅用于维护，不是绘图运行时依赖。

`source-manifest.json` 记录源码、项目 skill、运行时、器件库和示例文件的 SHA-256；文件缺失或损坏时重新取得完整发行包。
