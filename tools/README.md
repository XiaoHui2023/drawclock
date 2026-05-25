# 打包工具

## 一键打包（PyInstaller；Linux 再 staticx）

在仓库根执行（使用根目录 `.venv`，无则创建）：

```bash
./tools/pack.sh
```

默认 `all` 会依次构建主入口与 reload。只打某一个时传入 `src` 或 `reload`：

```bash
./tools/pack.sh src
./tools/pack.sh reload
```

Windows 可在仓库根执行 `pack.bat`（仅 PyInstaller，无 staticx）。

Linux 另需系统安装 **`patchelf`**（如 `sudo apt install patchelf`）。产物写入 `dist/`：

| 目标 | 产物 |
| --- | --- |
| 主入口（`src`） | `drawclock` / `drawclock.exe` |
| reload | `drawclock-reload` / `drawclock-reload.exe` |

Linux 上为 staticx 处理后的单文件；Windows 为 PyInstaller onefile。macOS 当前跳过 staticx。

单文件内附带 **`drawio-lib/`**（含 `drawclock.xml`）。`src` 未指定 `--library` 时使用内置库路径。

更完整的说明见仓库根目录 [PACKAGING.md](../PACKAGING.md)。
