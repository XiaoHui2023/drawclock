# 源码运行

完整源码由仓库和发布 tag 提供。代码只使用 Python 标准库，不需要安装第三方 Python 包。支持 CPython 3.9 或更高版本。

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

自动分层和布线由标准库 Python 实现，不需要 Node.js、ELK 或浏览器。
