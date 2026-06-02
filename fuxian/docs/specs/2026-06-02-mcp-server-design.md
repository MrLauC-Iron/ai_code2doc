# MCP Server 与插件命令实现设计文档

**日期**: 2026-06-02
**项目名**: fuxian_modules_info_mcp_sever

## 目标

实现 MCP Server（Python + SSE）和 fuxian 插件命令的实际对接，使团队可以通过共享服务同步模块文档和任务上下文。

## 技术选型

- MCP Server：Python + `mcp` SDK + SSE 传输模式
- 数据存储：文件系统（Markdown 文件）
- 客户端：fuxian 命令行通过 HTTP 调用

## 架构

```
团队开发者
  ├── Claude Code（MCP SSE 客户端，原生调用工具）
  └── fuxian 命令行（HTTP 调用同一 server）
        ↓
  MCP Server（Python，SSE HTTP 模式，端口 3001）
        ↓
  文件系统（Markdown 文件，可用 Git 管理）
```

## MCP Server 项目结构

项目路径：`F:\CodeWorkspace\fuxian_modules_info_mcp_sever`

```
fuxian_modules_info_mcp_sever/
├── server.py              # MCP Server 入口（SSE 模式）
├── tools.py               # MCP 工具定义
├── storage.py             # 文件存储层
├── config.py              # 配置（端口、数据目录）
├── requirements.txt       # Python 依赖
├── data/                  # 模块文档存储目录
│   ├── modules/           # 模块文档
│   │   └── <模块名>.md
│   └── tasks/             # 任务上下文
│       └── <任务名>.md
└── README.md
```

## MCP 工具定义

### 1. list_modules

- 功能：列出所有可用模块
- 参数：无
- 返回：模块名列表

### 2. get_module

- 功能：读取一个或多个模块文档，返回文件内容
- 参数：`module_names` (array of string)
- 返回：所有请求的模块文档内容，不存在的模块标注为 null
- 示例：
  ```json
  // 请求
  { "module_names": ["lexer", "parser", "ir"] }

  // 返回
  {
    "lexer": "# lexer\n## 功能\n...",
    "parser": "# parser\n## 功能\n...",
    "ir": null
  }
  ```

### 3. push_task

- 功能：保存任务上下文文档
- 参数：`task_name` (string), `content` (string)
- 返回：保存成功确认
- 行为：写入/覆盖 `data/tasks/<task_name>.md`

## HTTP 端点

MCP SSE server 同时暴露 REST 端点，供 fuxian 命令行调用：

| 方法 | 路径 | 功能 | 请求/响应 |
|------|------|------|-----------|
| GET | `/modules` | 列出所有模块 | 返回 JSON 模块名列表 |
| GET | `/modules/<name>` | 获取单个模块文档 | 返回文件下载（text/markdown） |
| POST | `/modules/get` | 批量获取模块文档 | body: `{"module_names": [...]}`，返回 ZIP |
| POST | `/tasks/<name>` | 保存任务上下文 | body 为 Markdown 文件内容 |

## fuxian 命令行更新

### Server 地址配置

- 优先读取环境变量 `FUXIAN_SERVER_URL`
- 默认值 `http://localhost:3001`

### pull-module（支持批量）

```bash
# 单个
fuxian pull-module lexer

# 批量
fuxian pull-module lexer parser ir
```

行为：
1. `POST /modules/get`，body 为 `{"module_names": ["lexer", "parser", "ir"]}`
2. 收到 ZIP → 解压到 `.fuxian/modules/`

单个模块时也可用 `GET /modules/<name>`，直接保存到 `.fuxian/modules/<name>.md`。

### push-task

```bash
fuxian push-task add-vector-support
```

行为：
1. 读取本地 `.fuxian/tasks/add-vector-support.md`
2. `POST /tasks/add-vector-support`，body 为文件内容
3. 输出成功信息

## task-context 技能更新

`skills/task-context/SKILL.md` 步骤 4 更新为支持批量拉取：

```
对所有用户确认的模块，一次性批量拉取：

fuxian pull-module lexer parser ir
```

## 变更范围

- 新建：`F:\CodeWorkspace\fuxian_modules_info_mcp_sever/`（整个 MCP Server 项目）
- 修改：`F:\CodeWorkspace\superpowers\.fuxian\bin\fuxian`（替换占位实现）
- 修改：`F:\CodeWorkspace\superpowers\skills\task-context\SKILL.md`（步骤 4 批量拉取）
