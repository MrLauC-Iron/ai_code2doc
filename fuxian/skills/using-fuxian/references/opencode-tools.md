# OpenCode 工具映射

技能中使用 Claude Code 工具名。在 opencode 中使用对应的替代工具：

| 技能中的引用 | opencode 等价物 |
|-------------|----------------|
| `TodoWrite` (任务跟踪) | `todowrite` |
| `Task` 工具 (派发子代理) | OpenCode 子代理系统（@mention） |
| `Skill` 工具 (调用技能) | opencode 原生 `skill` 工具 |
| `Read`, `Write`, `Edit`, `Bash` | opencode 原生文件/命令工具 |
| `Grep` (搜索文件内容) | opencode 原生搜索工具 |
| `Glob` (按名称搜索文件) | opencode 原生搜索工具 |
| `EnterPlanMode` / `ExitPlanMode` | 无等价物 — 在主会话中继续 |
| `WebSearch` | 无等价物 — 使用 `web_fetch` 搭配搜索引擎 URL |
| `WebFetch` | opencode 原生 `web_fetch` |

## 子代理支持

OpenCode 原生支持子代理（subagent），使用 `@` 语法。技能要求派发子代理时，使用 `@generalist` 并传入技能中的完整提示模板。
