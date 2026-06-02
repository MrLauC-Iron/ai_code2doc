"""MCP 工具定义 — list_modules, get_module, push_task"""

from mcp.server import Server
from mcp.types import Tool, TextContent
import storage

app = Server("fuxian-modules")

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
