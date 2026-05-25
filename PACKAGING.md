# 打包发布

在可访问 PyPI 的机器上于仓库根执行一键脚本，得到单文件 CLI。Linux 上会在 PyInstaller onefile 之后再做 staticx，便于在较旧 glibc 环境运行。

## 一键打包

```bash
./tools/pack.sh
```

Windows：

```bat
pack.bat
```

脚本会创建或复用根目录 `.venv`，安装项目与 PyInstaller，再按 `drawclock-cli.spec` 构建。参数与单入口说明见 [tools/README.md](tools/README.md)。

| 命令 | 产物（`dist/`） |
| --- | --- |
| `./tools/pack.sh` 或 `all` | `drawclock`、`drawclock-reload`（Windows 为 `.exe`） |
| `./tools/pack.sh src` | `drawclock` / `drawclock.exe` |
| `./tools/pack.sh reload` | `drawclock-reload` / `drawclock-reload.exe` |

## 运行打包产物

```bat
dist\drawclock.exe -i example\demo.drawio -o example\out
```

`--library` 可省略：默认可执行文件内嵌的 `drawio-lib/drawclock.xml`。

reload 示例：

```bat
dist\drawclock-reload.exe -i example\fig1.drawio -o example\out\fig1-reloaded.drawio
```

## Linux staticx

在 Linux 上，`tools/pack.sh` 对 ELF 产物再运行 **staticx**，需要系统已安装 **patchelf**（例如 `sudo apt install patchelf`）。macOS 当前跳过 staticx，仅保留 PyInstaller onefile。

## Spec 文件

- `drawclock-cli.spec` → **`drawclock`**
- `drawclock-reload.spec` → **`drawclock-reload`**

## 兼容边界

单文件可执行文件的系统兼容性取决于**执行打包的那台机器**。要支持较旧的 Linux 发行版，应在 glibc 基线不高于目标环境的系统上构建，并在目标机实测 staticx 产物。
