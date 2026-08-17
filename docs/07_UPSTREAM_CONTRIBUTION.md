# 上游贡献

个人主仓库与 HolmesGPT fork 分离。Fork 只用于小而清晰的上游 PR。

建议顺序：

0. 文档 / 测试 / Azure 配置示例（熟悉 DCO 与 CI）
1. `approval_required_tools` 对自定义 Toolset/MCP 的测试与修复
2. Azure MCP Schema 兼容性（坏工具隔离）
3. 可选：`traceparent` 跨 Holmes → MCP

详见 `skills/upstream-pr/SKILL.md`。
