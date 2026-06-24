"""通用工具函数。"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """返回项目根目录，便于跨平台拼接路径。"""
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """返回数据目录；如果目录不存在则自动创建。"""
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    """返回 SQLite 数据库文件路径。"""
    return data_dir() / "novels.db"
