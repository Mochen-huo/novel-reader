"""通用工具函数。"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """判断是否在 PyInstaller 打包后的环境中运行。"""
    return getattr(sys, "frozen", False)


def project_root() -> Path:
    """返回项目根目录（源码目录或 PyInstaller 解压目录）。"""
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """返回用户数据目录，用于存放数据库、浏览器配置等持久化文件。

    - 源码开发时：项目根目录下的 ``data``
    - 打包 exe 后：``%APPDATA%\\NovelReader``（Windows）
    """
    if is_frozen():
        # PyInstaller 打包后，持久数据放在用户 AppData 下
        import winreg
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            appdata = Path(winreg.QueryValueEx(key, "AppData")[0])
            winreg.CloseKey(key)
        except Exception:
            appdata = Path.home() / "AppData" / "Roaming"
        path = appdata / "NovelReader"
    else:
        path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """别名：返回用户数据目录。"""
    return user_data_dir()


def database_path() -> Path:
    """返回 SQLite 数据库文件路径。"""
    return data_dir() / "novels.db"
