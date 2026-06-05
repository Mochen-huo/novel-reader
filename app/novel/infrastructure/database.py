"""SQLite 数据库访问模块。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.common.utils import database_path


class NovelDatabase:
    """负责章节数据的创建、保存、读取和删除。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()
        self.init_database()

    def connect(self) -> sqlite3.Connection:
        """创建数据库连接，并使用 Row 方便按字段名读取。"""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_database(self) -> None:
        """初始化数据库表；首次启动时会自动创建，并兼容旧表结构。"""
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    url TEXT UNIQUE,
                    content TEXT,
                    created_at TEXT
                )
                """
            )
            self.ensure_column(connection, "book_title", "TEXT")
            self.ensure_column(connection, "prev_url", "TEXT")
            self.ensure_column(connection, "next_url", "TEXT")
            connection.commit()

    def ensure_column(
        self,
        connection: sqlite3.Connection,
        column_name: str,
        column_type: str,
    ) -> None:
        """为旧数据库补充新增字段，避免删除已有章节数据。"""
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chapters)").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE chapters ADD COLUMN {column_name} {column_type}")

    def save_chapter(
        self,
        title: str,
        book_title: str,
        url: str,
        content: str,
        prev_url: str | None = None,
        next_url: str | None = None,
    ) -> int:
        """保存章节；同一个 URL 再次获取时更新标题、正文和导航链接。"""
        created_at = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO chapters (title, book_title, url, content, prev_url, next_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title = excluded.title,
                    book_title = excluded.book_title,
                    content = excluded.content,
                    prev_url = excluded.prev_url,
                    next_url = excluded.next_url,
                    created_at = excluded.created_at
                """,
                (title, book_title, url, content, prev_url, next_url, created_at),
            )
            connection.commit()

            row = connection.execute(
                "SELECT id FROM chapters WHERE url = ?",
                (url,),
            ).fetchone()
            if row is None:
                raise RuntimeError("章节保存失败：无法读取章节 ID。")
            return int(row["id"])

    def list_chapters(self) -> list[dict[str, Any]]:
        """读取章节列表，按保存顺序倒序显示。"""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, COALESCE(book_title, '未分组书籍') AS book_title, url, created_at
                FROM chapters
                ORDER BY book_title COLLATE NOCASE, id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chapter(self, chapter_id: int) -> dict[str, Any] | None:
        """根据章节 ID 读取章节详情。"""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, COALESCE(book_title, '未分组书籍') AS book_title,
                       url, content, prev_url, next_url, created_at
                FROM chapters
                WHERE id = ?
                """,
                (chapter_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_chapter(self, chapter_id: int) -> None:
        """根据章节 ID 删除本地保存的章节。"""
        with self.connect() as connection:
            connection.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
            connection.commit()
