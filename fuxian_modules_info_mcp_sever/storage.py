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
