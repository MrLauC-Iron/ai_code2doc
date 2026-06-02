# MCP Server 与插件命令对接实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Python MCP Server（SSE 模式）供团队共享模块文档和任务上下文，并更新 fuxian 插件命令对接该 server。

**Architecture:** Python MCP Server 使用 `mcp` SDK + Starlette + uvicorn，通过 SSE 暴露 MCP 工具，同时暴露 REST 端点供 fuxian 命令行 HTTP 调用。数据存储为文件系统中的 Markdown 文件。两个项目各自 git 管理独立提交。

**Tech Stack:** Python 3.10+, mcp SDK, starlette, uvicorn, Bash (fuxian 命令行)

---

## 文件清单

### MCP Server 项目 (`F:\CodeWorkspace\fuxian_modules_info_mcp_sever`)

| 文件 | 职责 |
|------|------|
| `config.py` | 配置常量（端口、数据目录） |
| `storage.py` | 文件存储层（读写 Markdown） |
| `tools.py` | MCP 工具定义 |
| `server.py` | MCP Server 入口（SSE + REST） |
| `requirements.txt` | Python 依赖 |
| `data/modules/.gitkeep` | 模块目录占位 |
| `data/tasks/.gitkeep` | 任务目录占位 |

### fuxian 插件项目 (`F:\CodeWorkspace\superpowers`)

| 文件 | 职责 |
|------|------|
| `.fuxian/bin/fuxian` | 替换占位实现为实际 HTTP 调用 |
| `skills/task-context/SKILL.md` | 步骤 4 更新为批量拉取 |

---

### Task 1: MCP Server 项目初始化

**工作目录:** `F:\CodeWorkspace\fuxian_modules_info_mcp_sever`

**Files:**
- Create: `config.py`
- Create: `requirements.txt`
- Create: `data/modules/.gitkeep`
- Create: `data/tasks/.gitkeep`

- [ ] **Step 1: 初始化 git 仓库并创建 data 目录**

```bash
cd "F:/CodeWorkspace/fuxian_modules_info_mcp_sever"
git init
mkdir -p data/modules data/tasks
touch data/modules/.gitkeep data/tasks/.gitkeep
```

- [ ] **Step 2: 创建 config.py**

```python
"""MCP Server 配置"""

import os

# Server 配置
SERVER_HOST = os.environ.get("FUXIAN_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("FUXIAN_SERVER_PORT", "3001"))

# 数据目录
DATA_DIR = os.environ.get("FUXIAN_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
MODULES_DIR = os.path.join(DATA_DIR, "modules")
TASKS_DIR = os.path.join(DATA_DIR, "tasks")
```

- [ ] **Step 3: 创建 requirements.txt**

```
mcp[cli]>=1.0.0
starlette>=0.27.0
uvicorn>=0.24.0
```

- [ ] **Step 4: 提交**

```bash
cd "F:/CodeWorkspace/fuxian_modules_info_mcp_sever"
git add config.py requirements.txt data/
git commit -m "初始化项目结构和配置"
```

---

### Task 2: 文件存储层

**工作目录:** `F:\CodeWorkspace\fuxian_modules_info_mcp_sever`

**Files:**
- Create: `storage.py`

- [ ] **Step 1: 创建 storage.py**

```python
"""文件存储层 — 读写 Markdown 文件"""

import os
from config import MODULES_DIR, TASKS_DIR


def ensure_dirs():
    """确保数据目录存在"""
    os.makedirs(MODULES_DIR, exist_ok=True)
    os.makedirs(TASKS_DIR, exist_ok=True)


def list_modules() -> list[str]:
    """列出所有模块名（不含 .md 后缀）"""
    ensure_dirs()
    if not os.path.isdir(MODULES_DIR):
        return []
    return [f[:-3] for f in os.listdir(MODULES_DIR) if f.endswith(".md")]


def get_module(module_name: str) -> str | None:
    """读取单个模块文档内容，不存在返回 None"""
    path = os.path.join(MODULES_DIR, f"{module_name}.md")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_modules(module_names: list[str]) -> dict[str, str | None]:
    """批量读取模块文档，不存在的模块值为 None"""
    result = {}
    for name in module_names:
        result[name] = get_module(name)
    return result


def save_module(module_name: str, content: str):
    """写入或更新模块文档"""
    ensure_dirs()
    path = os.path.join(MODULES_DIR, f"{module_name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def save_task(task_name: str, content: str):
    """写入或更新任务上下文文档"""
    ensure_dirs()
    path = os.path.join(TASKS_DIR, f"{task_name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def get_task(task_name: str) -> str | None:
    """读取任务上下文文档"""
    path = os.path.join(TASKS_DIR, f"{task_name}.md")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 2: 提交**

```bash
cd "F:/CodeWorkspace/fuxian_modules_info_mcp_sever"
git add storage.py
git commit -m "添加文件存储层"
```

---

### Task 3: MCP 工具定义

**工作目录:** `F:\CodeWorkspace\fuxian_modules_info_mcp_sever`

**Files:**
- Create: `tools.py`

- [ ] **Step 1: 创建 tools.py**

```python
"""MCP 工具定义 — list_modules, get_module, push_task"""

from mcp.server import Server
from mcp.types import Tool, TextContent
import storage

app = Server("fuxian-modules")

# 工具定义
TOOLS = [
    Tool(
        name="list_modules",
        description="列出所有可用的模块文档",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="get_module",
        description="读取一个或多个模块文档（Markdown 文件内容）",
        inputSchema={
            "type": "object",
            "properties": {
                "module_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "模块名列表",
                }
            },
            "required": ["module_names"],
        },
    ),
    Tool(
        name="push_task",
        description="保存任务上下文文档到服务端",
        inputSchema={
            "type": "object",
            "properties": {
                "task_name": {
                    "type": "string",
                    "description": "任务名（英文短横线命名）",
                },
                "content": {
                    "type": "string",
                    "description": "任务上下文文档内容（Markdown）",
                },
            },
            "required": ["task_name", "content"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_modules":
        modules = storage.list_modules()
        if not modules:
            return [TextContent(type="text", text="当前没有模块文档")]
        return [TextContent(type="text", text=", ".join(modules))]

    elif name == "get_module":
        module_names = arguments["module_names"]
        results = storage.get_modules(module_names)
        parts = []
        for mname, content in results.items():
            if content is not None:
                parts.append(f"--- {mname} ---\n{content}")
            else:
                parts.append(f"--- {mname} ---\n(未找到)")
        return [TextContent(type="text", text="\n\n".join(parts))]

    elif name == "push_task":
        task_name = arguments["task_name"]
        content = arguments["content"]
        storage.save_task(task_name, content)
        return [TextContent(type="text", text=f"任务上下文已保存: {task_name}")]

    raise ValueError(f"Unknown tool: {name}")
```

- [ ] **Step 2: 提交**

```bash
cd "F:/CodeWorkspace/fuxian_modules_info_mcp_sever"
git add tools.py
git commit -m "添加 MCP 工具定义"
```

---

### Task 4: Server 入口（SSE + REST）

**工作目录:** `F:\CodeWorkspace\fuxian_modules_info_mcp_sever`

**Files:**
- Create: `server.py`

- [ ] **Step 1: 创建 server.py**

```python
"""MCP Server 入口 — SSE 传输 + REST 端点"""

import os
import tempfile
import zipfile
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, FileResponse
from starlette.routing import Route
from starlette.requests import Request
from mcp.server.sse import SseServerTransport
import uvicorn

import storage
from tools import app as mcp_app
from config import SERVER_HOST, SERVER_PORT

# SSE 传输
sse = SseServerTransport("/messages")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_app.run(
            streams[0], streams[1],
            mcp_app.create_initialization_options(),
        )


# --- REST 端点 ---

async def rest_list_modules(request: Request) -> JSONResponse:
    """GET /modules — 列出所有模块"""
    modules = storage.list_modules()
    return JSONResponse({"modules": modules})


async def rest_get_module(request: Request) -> Response:
    """GET /modules/<name> — 获取单个模块文档（文件下载）"""
    module_name = request.path_params["name"]
    content = storage.get_module(module_name)
    if content is None:
        return JSONResponse({"error": f"模块 {module_name} 不存在"}, status_code=404)
    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{module_name}.md"'
        },
    )


async def rest_get_modules_batch(request: Request) -> Response:
    """POST /modules/get — 批量获取模块文档（ZIP 下载）"""
    try:
        body = await request.json()
        module_names = body.get("module_names", [])
    except Exception:
        return JSONResponse({"error": "无效的 JSON body"}, status_code=400)

    if not module_names:
        return JSONResponse({"error": "module_names 不能为空"}, status_code=400)

    results = storage.get_modules(module_names)
    found = {k: v for k, v in results.items() if v is not None}

    if not found:
        return JSONResponse({"error": "没有找到任何请求的模块"}, status_code=404)

    # 单个文件直接返回
    if len(found) == 1:
        name, content = next(iter(found.items()))
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{name}.md"'},
        )

    # 多个文件打包为 ZIP
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        with zipfile.ZipFile(tmp.name, "w") as zf:
            for name, content in found.items():
                zf.writestr(f"{name}.md", content)
        with open(tmp.name, "rb") as f:
            zip_bytes = f.read()
    finally:
        os.unlink(tmp.name)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="modules.zip"'
        },
    )


async def rest_push_task(request: Request) -> JSONResponse:
    """POST /tasks/<name> — 保存任务上下文"""
    task_name = request.path_params["name"]
    content = await request.body()
    if not content:
        return JSONResponse({"error": "请求体不能为空"}, status_code=400)
    storage.save_task(task_name, content.decode("utf-8"))
    return JSONResponse({"status": "ok", "task": task_name})


# Starlette 应用
starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
        Route("/modules", endpoint=rest_list_modules, methods=["GET"]),
        Route("/modules/get", endpoint=rest_get_modules_batch, methods=["POST"]),
        Route("/modules/{name}", endpoint=rest_get_module, methods=["GET"]),
        Route("/tasks/{name}", endpoint=rest_push_task, methods=["POST"]),
    ],
)


if __name__ == "__main__":
    storage.ensure_dirs()
    uvicorn.run(starlette_app, host=SERVER_HOST, port=SERVER_PORT)
```

- [ ] **Step 2: 提交**

```bash
cd "F:/CodeWorkspace/fuxian_modules_info_mcp_sever"
git add server.py
git commit -m "添加 MCP Server 入口（SSE + REST 端点）"
```

---

### Task 5: 更新 fuxian 命令行

**工作目录:** `F:\CodeWorkspace\superpowers`

**Files:**
- Modify: `.fuxian/bin/fuxian`

- [ ] **Step 1: 替换 .fuxian/bin/fuxian 为完整实现**

将整个文件替换为：

```bash
#!/usr/bin/env bash
# Fuxian 插件命令入口
#
# 用法：
#   fuxian pull-module <模块名> [模块名...]  — 从远程拉取模块文档
#   fuxian push-task <任务名>                 — 将任务上下文推送到远程
#
# 环境变量：
#   FUXIAN_SERVER_URL — MCP Server 地址（默认 http://localhost:3001）

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODULES_DIR="${PLUGIN_ROOT}/modules"
TASKS_DIR="${PLUGIN_ROOT}/tasks"

SERVER_URL="${FUXIAN_SERVER_URL:-http://localhost:3001}"

mkdir -p "$MODULES_DIR" "$TASKS_DIR"

usage() {
    echo "用法: fuxian <command> [args]"
    echo ""
    echo "命令:"
    echo "  pull-module <模块名> [模块名...]  从远程拉取模块文档"
    echo "  push-task <任务名>                 推送任务上下文到远程"
    echo ""
    echo "环境变量:"
    echo "  FUXIAN_SERVER_URL  MCP Server 地址（默认 http://localhost:3001）"
    exit 1
}

cmd_pull_module() {
    local modules=("$@")

    if [ ${#modules[@]} -eq 0 ]; then
        echo "错误: pull-module 需要至少一个模块名"
        exit 1
    fi

    # 单个模块：GET /modules/<name>
    if [ ${#modules[@]} -eq 1 ]; then
        local module_name="${modules[0]}"
        local target_file="${MODULES_DIR}/${module_name}.md"
        local http_code
        http_code=$(curl -s -o "$target_file" -w "%{http_code}" \
            "${SERVER_URL}/modules/${module_name}") || true
        if [ "$http_code" = "200" ]; then
            echo "已拉取模块文档: ${module_name} -> ${target_file}"
        else
            rm -f "$target_file"
            echo "提示: 模块 ${module_name} 不存在于远程服务端"
            echo "将进入问答阶段补全该模块的业务背景。"
        fi
        return
    fi

    # 多个模块：POST /modules/get（返回 ZIP）
    local json_args
    json_args=$(printf '%s\n' "${modules[@]}" | jq -R . | jq -s '{module_names: .}')

    local tmp_zip="${TASKS_DIR}/.modules_tmp.zip"
    local http_code
    http_code=$(curl -s -o "$tmp_zip" -w "%{http_code}" \
        -X POST -H "Content-Type: application/json" \
        -d "$json_args" \
        "${SERVER_URL}/modules/get") || true

    if [ "$http_code" = "200" ] && [ -f "$tmp_zip" ]; then
        unzip -o "$tmp_zip" -d "$MODULES_DIR/" > /dev/null
        rm -f "$tmp_zip"
        echo "已拉取 ${#modules[@]} 个模块文档到 ${MODULES_DIR}/"
    else
        rm -f "$tmp_zip"
        echo "错误: 批量拉取失败（HTTP ${http_code:-无响应}）"
        echo "请检查 MCP Server 是否运行: ${SERVER_URL}"
    fi
}

cmd_push_task() {
    local task_name="$1"
    local task_file="${TASKS_DIR}/${task_name}.md"

    if [ ! -f "$task_file" ]; then
        echo "错误: 任务文件不存在: ${task_file}"
        exit 1
    fi

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Content-Type: text/markdown" \
        --data-binary "@${task_file}" \
        "${SERVER_URL}/tasks/${task_name}") || true

    if [ "$http_code" = "200" ]; then
        echo "任务上下文已推送: ${task_name}"
    else
        echo "错误: 推送失败（HTTP ${http_code:-无响应}）"
        echo "任务上下文已保存到本地: ${task_file}"
    fi
}

# 主入口
if [ $# -lt 1 ]; then
    usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
    pull-module)
        if [ $# -lt 1 ]; then
            echo "错误: pull-module 需要至少一个模块名"
            exit 1
        fi
        cmd_pull_module "$@"
        ;;
    push-task)
        if [ $# -lt 1 ]; then
            echo "错误: push-task 需要任务名参数"
            exit 1
        fi
        cmd_push_task "$1"
        ;;
    *)
        echo "错误: 未知命令: ${COMMAND}"
        usage
        ;;
esac
```

- [ ] **Step 2: 提交**

```bash
cd "F:/CodeWorkspace/superpowers"
git add .fuxian/bin/fuxian
git commit -m "更新 fuxian 命令行：对接 MCP Server HTTP 端点"
```

---

### Task 6: 更新 task-context 技能

**工作目录:** `F:\CodeWorkspace\superpowers`

**Files:**
- Modify: `skills/task-context/SKILL.md`

- [ ] **Step 1: 更新步骤 4 为批量拉取**

在 `skills/task-context/SKILL.md` 中找到第四步的内容（"### 第四步：拉取模块文档"），将其中的：

原内容：
```markdown
对用户确认的每个涉及模块，执行插件命令拉取最新文档：

```bash
fuxian pull-module <模块名>
```

这会将远程最新的模块文档拉取到 `.fuxian/modules/<模块名>.md`。

**如果拉取失败或模块文档不存在：**
- 跳过该模块文档，在第五步中标注为"无已有文档"
- 后续提问中需要更多地覆盖该模块的业务背景
```

替换为：
```markdown
对所有用户确认的涉及模块，一次性批量拉取最新文档：

```bash
fuxian pull-module lexer parser ir
```

这会从 MCP Server 批量拉取模块文档到 `.fuxian/modules/`。
- 单个模块时直接下载 .md 文件
- 多个模块时服务端返回 ZIP 包，自动解压到本地

**如果某个模块拉取失败（不存在于服务端）：**
- 该模块不会生成本地文件
- 在第五步中标注为"无已有文档"
- 后续提问中需要更多地覆盖该模块的业务背景
```

- [ ] **Step 2: 提交**

```bash
cd "F:/CodeWorkspace/superpowers"
git add skills/task-context/SKILL.md
git commit -m "更新 task-context 技能：步骤 4 改为批量拉取"
```

---

## 自审

**规范覆盖检查：**
- config.py ✓ (Task 1)
- storage.py 文件存储层 ✓ (Task 2)
- tools.py MCP 工具定义 ✓ (Task 3)
- server.py SSE + REST ✓ (Task 4)
- fuxian 命令行更新 ✓ (Task 5)
- task-context 技能更新 ✓ (Task 6)
- list_modules 工具 ✓
- get_module 批量返回 ✓
- push_task 工具 ✓
- REST 端点（GET/POST modules, POST tasks）✓
- ZIP 批量下载 ✓
- 环境变量配置 ✓

**占位符扫描：** 无 TBD/TODO

**一致性检查：** 文件路径、函数名、端点路径跨 Task 一致
