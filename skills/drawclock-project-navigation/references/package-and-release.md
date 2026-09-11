# 打包与发行门禁

## 包内容

默认发行压缩包只保留冻结可执行文件、`libraries/*.xml` 平铺器件库、`example/` 中的代表输入和 `doc/` 中的用户文档。根目录不放 README，禁止旧 `drawio-lib/`、开发源码、项目 Skills、批量测试语料、未使用的 Node.js、浏览器或第三方 Python 运行时进入默认用户包。

`skills/` 是纯文本维护资料，不是程序运行依赖；即使删除它，绘图运行逻辑也不应改变。发行门验证七个 skill 齐全、引用有效、无私人路径或身份信息，并把它们纳入 SHA-256 清单。

## 本地和 CI 门禁

```text
python skills/drawclock-project-navigation/scripts/validate_skills.py skills
python -m pytest
tools/pack.bat
```

组包后检查：

- 压缩包中每个 skill 的 `SKILL.md` 和 references 都存在；
- source manifest 的文件集合与摘要完全一致；
- PATH 隔离时冻结程序仍能从示例生成有效 SVG；
- 新虚拟环境中使用 `python -I -S src` 能离线生成有效 SVG；
- 任意输出后缀仍写 SVG，非 JSON 输入在开始布局前失败；
- 单文件单器件约束有效，多个文件、多个目录及混合输入均可确定性合并。

发布后下载远端资产重复上述校验，并确认 v1.0.0 rolling tag 指向当前发布提交。
