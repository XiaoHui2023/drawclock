# 打包工具

## 一键打包（PyInstaller；Linux 再 staticx）

在仓库根执行（使用根目录 `.venv`，无则创建）：

```bash
./tools/pack.sh
```

只打主入口时传入 `src`（与默认 `all` 相同）：

```bash
./tools/pack.sh src
```

Windows 可在仓库根执行 `pack.bat`（仅 PyInstaller，无 staticx）。

Linux 另需系统安装 **`patchelf`**（如 `sudo apt install patchelf`）。产物写入 `dist/`：

| 目标 | 产物 |
| --- | --- |
| 主入口（`src`） | `drawclock` / `drawclock.exe` |

Linux 上为 staticx 处理后的单文件；Windows 为 PyInstaller onefile。macOS 当前跳过 staticx。

单文件内附带 **`drawio-lib/`**（含 `drawclock.xml`）。decode 未指定 `--library` 时使用内置库路径。

更完整的说明见仓库根目录 [PACKAGING.md](../PACKAGING.md)。
