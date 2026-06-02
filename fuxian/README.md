# Fuxian

面向自研芯片编译器开发的 AI 编码技能库。

## 支持平台

- Claude Code (CLI / VS Code 扩展)
- opencode

## 安装

### Claude Code

将此插件安装到 Claude Code 的插件目录：

```bash
# 从 git 仓库安装
claude plugins install /path/to/fuxian
```

### opencode

在 `opencode.json` 中添加：

```json
{
  "plugin": ["fuxian@git+https://github.com/YOUR_USERNAME/fuxian.git"]
}
```

## 技能列表

| 技能 | 描述 |
|------|------|
| `using-fuxian` | 引导技能 — 技能发现和优先级规则 |
| `brainstorming` | 头脑风暴 — 需求探索和设计方案 |
| `test-driven-development` | TDD — 红-绿-重构循环 |
| `systematic-debugging` | 系统调试 — 结构化调试流程 |

## 许可证

MIT