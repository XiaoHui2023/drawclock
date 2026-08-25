# 源码离线部署

发行包内的 `src/`、`runtime/`、`vendor/wheels/` 和器件库支持断网运行。需要同平台的 CPython 3.10～3.14。

## Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --no-index --find-links vendor\wheels -r requirements-offline.txt
.venv\Scripts\python.exe src -i example\draw.json -l drawio-lib\drawclock.xml -o clock-tree.svg
```

## Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links vendor/wheels -r requirements-offline.txt
.venv/bin/python src -i example/draw.json -l drawio-lib/drawclock.xml -o clock-tree.svg
```

安装命令禁止访问软件源。`source-manifest.json` 记录源码和离线依赖文件的 SHA-256；文件缺失或损坏时应重新取得完整发行包。
