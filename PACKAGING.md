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
| `./tools/pack.sh` 或 `all` / `src` | `drawclock` / `drawclock.exe` |

## 运行打包产物

```bat
dist\drawclock.exe encode -i example\demo.drawio -o example\out --layout
dist\drawclock.exe decode --config example\out\clock-tree.json --layout example\out\drawio-layout.json -o example\out\restored.drawio
```

decode 的 `--library` 可省略：默认可执行文件内嵌的 `drawio-lib/drawclock.xml`。也可显式传入仓库中的 `drawio-lib/drawclock.xml` 覆盖。

## Linux staticx

在 Linux 上，`tools/pack.sh` 对 ELF 产物再运行 **staticx**，需要系统已安装 **patchelf**（例如 `sudo apt install patchelf`）。macOS 当前跳过 staticx，仅保留 PyInstaller onefile。

## Spec 文件

- `drawclock-cli.spec` → 二进制名 **`drawclock`**

## 兼容边界

单文件可执行文件的系统兼容性取决于**执行打包的那台机器**。要支持较旧的 Linux 发行版，应在 glibc 基线不高于目标环境的系统上构建，并在目标机实测 staticx 产物。
