# 参考资料

- [JSON Schema object](https://json-schema.org/understanding-json-schema/reference/object)：`properties`、`required` 和对象字段约束。
- [JSON Schema 官方规范入口](https://json-schema.org/specification)：需要把合约发布成机器 schema 时使用。

项目当前运行时只依赖 Python 标准库 JSON 解析器，不要求安装 JSON Schema 验证库。文档中的概念 schema 用于设计和测试，实际约束以项目验证代码与测试为准。
