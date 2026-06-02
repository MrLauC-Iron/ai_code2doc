"""MCP Server 配置"""

import os

# Server 配置
SERVER_HOST = os.environ.get("FUXIAN_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("FUXIAN_SERVER_PORT", "3001"))

# 数据目录
DATA_DIR = os.environ.get("FUXIAN_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
MODULES_DIR = os.path.join(DATA_DIR, "modules")
TASKS_DIR = os.path.join(DATA_DIR, "tasks")
