"""MCP Server 入口 — SSE 传输 + REST 端点"""

import os
import tempfile
import zipfile
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.requests import Request
from mcp.server.sse import SseServerTransport
import uvicorn

import storage
from tools import app as mcp_app
from config import SERVER_HOST, SERVER_PORT

sse = SseServerTransport("/messages")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_app.run(
            streams[0], streams[1],
            mcp_app.create_initialization_options(),
        )


async def rest_list_modules(request: Request) -> JSONResponse:
    modules = storage.list_modules()
    return JSONResponse({"modules": modules})


async def rest_get_module(request: Request) -> Response:
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

    if len(found) == 1:
        name, content = next(iter(found.items()))
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{name}.md"'},
        )

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
    task_name = request.path_params["name"]
    content = await request.body()
    if not content:
        return JSONResponse({"error": "请求体不能为空"}, status_code=400)
    storage.save_task(task_name, content.decode("utf-8"))
    return JSONResponse({"status": "ok", "task": task_name})


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
