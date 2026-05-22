# Interactive Agent Design: Conversational REPL for ai_code2doc

## Overview

当前 `analyze` 命令在 5 阶段流水线完成后即退出，`query` 命令只能做一次性问答。本设计为 ai_code2doc 添加对话式 Agent，在分析完成后自动进入 REPL 交互模式，用户可以持续探索代码、迭代文档、触发增量分析。

## Goals

- 分析完成后不退出，进入对话模式，用户可持续交互
- Agent 通过 LLM tool-use 能力，根据用户意图自动路由到正确操作
- 支持代码问答、文档定向更新、依赖/影响分析、增量重新分析、错误纠正
- 多 LLM 提供商统一接口（OpenAI、Anthropic、Ollama、自定义端点）

## Command Interface

### `analyze` 命令行为变更

```bash
# 分析完成后必定进入 REPL（默认行为，无 --no-interactive）
ai_code2doc analyze ./myproject
# ... 5 阶段流水线输出 ...
# ✓ 分析完成！进入对话模式（输入 /help 查看命令，/quit 退出）
# > 你好，有什么可以帮助你了解这个项目的？
```

### 新增 `chat` 命令

```bash
# 跳过分析，直接加载已有结果进入 REPL
ai_code2doc chat ./myproject

# 项目未分析时提示用户，并提供"是否现在分析？"选项
```

## Agent Architecture

### 核心循环

1. 用户输入自然语言问题
2. LLM 判断意图，选择调用工具（或不调用，直接回答）
3. 执行工具，获取结果
4. LLM 基于工具结果生成最终回答
5. 回到步骤 1，直到用户输入 `/quit`

### Tool-Use 集成

- OpenAI 格式：`tools` 参数 + `tool_calls` 响应
- Anthropic 格式：`tools` 参数 + `tool_use` content block
- Provider 层做格式转换，上层 Agent 逻辑只看统一的 `ToolCall` 对象

## Tool Set

| 工具 | 触发场景 | 输入 | 输出 |
|------|---------|------|------|
| `code_qa` | "这个函数做什么？""模块 X 的职责？" | 用户问题 | 基于向量库的 RAG 回答 |
| `update_doc` | "重写 layer1 的架构部分""给 utils 加更多细节" | 目标层/模块 + 更新指令 | 更新后的文档内容 |
| `analyze_deps` | "main.py 的调用链是什么？""谁依赖了 utils？" | 查询目标（文件/模块） | 依赖路径 / 影响范围 |
| `rescan` | "重新扫描 src/""我刚改了 auth.py" | 文件路径或目录 | 增量分析结果摘要 |
| `correct` | "这里写错了，应该是..." | 错误位置 + 正确内容 | 修正确认 + 更新后的文档 |
| `list_context` | "目前分析了哪些模块？""项目概览" | 无 | 当前分析状态摘要 |

### 工具实现复用

- `code_qa` → 复用 `query_cmd.py` 的 RAG 逻辑 + `vector_store/`
- `update_doc` → 复用 `generator/` 的 Layer1/2/3 generator
- `analyze_deps` → 复用 `analyzer/` 的 DependencyGraphBuilder
- `rescan` → 复用 `scanner/` + `parser/` + `ChangeDetector`
- `correct` → `update_doc` 的变体，带 diff 确认

## Conversation Management

### History

- 每轮对话保存为 `{role, content, tool_calls, tool_results}` 结构
- 内存中维护滑动窗口（默认最近 10 轮），避免 token 膨胀
- 退出时可选保存到 `.ai_code2doc/session.json`，下次 `chat` 可恢复

### System Prompt

- 固定 system prompt 包含：项目基本信息（名称、语言、目录结构摘要）、可用工具描述、分析结果概览
- 不把整个分析结果塞进 context，靠工具按需检索

### Context Strategy

- 简单问题（代码问答）→ system prompt + 当前问题 + 历史摘要
- 复杂操作（文档更新、重新分析）→ 工具执行后才扩展上下文
- 历史轮数可通过配置调整

## LLM Provider Abstraction

### 配置方式

```toml
[llm]
provider = "openai"          # openai / anthropic / ollama / custom
model = "gpt-4o"
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
```

### Provider 层设计

- `LLMProvider` 抽象基类：统一 `generate()` / `agenerate()` / `generate_with_tools()` 接口
- `OpenAIProvider`：基于现有 `openai` 库，兼容所有 OpenAI 协议提供商
- `AnthropicProvider`：使用 Anthropic SDK，适配 tool-use 格式差异
- `OllamaProvider`：`base_url` 指向 `http://localhost:11434/v1`，复用 OpenAI Provider

### Tool-Use 格式适配

- 各 Provider 将工具调用/响应转换为统一的 `ToolCall` / `ToolResult` 数据类
- 上层 `dispatcher.py` 不感知底层格式差异

## REPL Interface

### 技术选型

`prompt_toolkit`：
- 多行输入、历史记录（上下箭头）、自动补全
- Markdown 渲染输出（工具结果、代码片段带语法高亮）

### Slash Commands

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/quit` | 退出 REPL |
| `/history` | 查看对话历史 |
| `/save` | 手动保存会话 |
| `/context` | 查看当前上下文状态（token 用量等） |

### 输出格式

- 普通回答：Markdown 渲染，代码块带语法高亮
- 工具调用：`⚡ 调用 code_qa: "main.py 的职责"` → 结果
- 文档更新：`📝 已更新 layer2/utils.md` + diff 预览
- 错误/警告：红色高亮，不中断对话

### 交互体验

- 启动时打印分析摘要（文件数、模块数、耗时）
- 长时间工具执行显示 spinner
- Ctrl+C 中断当前操作，不退出 REPL
- `--verbose` 查看工具调用原始 JSON（调试用）

## File Structure (New/Modified)

```
src/ai_code2doc/
├── cli/
│   ├── main.py              # 修改：analyze 完成后进入 REPL
│   ├── analyze_cmd.py       # 修改：去掉退出逻辑，返回分析结果给 REPL
│   ├── chat_cmd.py          # 新增：独立 chat 命令入口
│   └── ...
├── agent/                    # 新增目录
│   ├── __init__.py
│   ├── repl.py              # REPL 循环、输入输出、/命令
│   ├── conversation.py      # 会话历史管理、上下文窗口
│   ├── tool_registry.py     # 工具注册与路由
│   ├── dispatcher.py        # LLM 调用 + tool-use 循环
│   └── tools/               # 具体工具实现
│       ├── __init__.py
│       ├── code_qa.py       # RAG 问答
│       ├── update_doc.py    # 文档定向更新
│       ├── analyze_deps.py  # 依赖分析
│       ├── rescan.py        # 增量重扫
│       ├── correct.py       # 错误修正
│       └── list_context.py  # 上下文状态查询
├── llm/
│   ├── client.py            # 修改：新增 tool-use 支持
│   ├── provider.py          # 新增：Provider 抽象层
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── ollama_provider.py
│   └── ...
└── config/
    └── settings.py          # 修改：新增 provider/repl 相关配置
```

## Error Handling

| 场景 | 处理 |
|------|------|
| 无 API Key | 进入 REPL 前检查，提示配置方法，不崩溃 |
| LLM 超时/限流 | 指数退避重试，超过 3 次提示用户 |
| 工具执行失败 | 错误信息回传 LLM，生成友好回复，不中断对话 |
| 项目未分析直接 `chat` | 提示先运行 `analyze`，或提供"是否现在分析？"选项 |
| 会话恢复失败 | `.ai_code2doc/session.json` 损坏时忽略，新建会话 |

## Dependencies (New)

- `prompt_toolkit`：REPL 界面
- `anthropic`：Anthropic Provider（如果需要原生 Anthropic SDK）
- 现有依赖 `openai`、`chromadb` 等保持不变
