"""Pytest 配置 — 让 `from api import ...` 与 `from config import ...` 都能工作。"""
import sys
from pathlib import Path

# 把 api/ 加入 sys.path(顶层 config.py 等模块在那里)
API_DIR = Path(__file__).resolve().parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))