"""小说阅读器业务服务层。"""

from __future__ import annotations

from typing import Any

from app.novel.domain.models import ChapterRecord
from app.novel.infrastructure.crawler import ChapterCrawler
from app.novel.infrastructure.database import NovelDatabase


class NovelReaderService:
    """封装抓取、保存、读取、删除等业务流程，避免界面直接依赖底层模块。"""

    def __init__(
        self,
        database: NovelDatabase | None = None,
        crawler: ChapterCrawler | None = None,
    ) -> None:
        self.database = database or NovelDatabase()
        self.crawler = crawler or ChapterCrawler()

    def fetch_and_save_chapter(self, url: str) -> ChapterRecord:
        """抓取章节并保存到本地数据库。"""
        chapter = self.crawler.fetch_chapter(url)
        chapter_id = self.database.save_chapter(
            title=chapter.title,
            book_title=chapter.book_title,
            url=chapter.url,
            content=chapter.content,
            prev_url=chapter.prev_url,
            next_url=chapter.next_url,
        )
        return ChapterRecord(
            id=chapter_id,
            title=chapter.title,
            book_title=chapter.book_title,
            url=chapter.url,
            content=chapter.content,
            prev_url=chapter.prev_url,
            next_url=chapter.next_url,
        )

    def list_chapters(self) -> list[ChapterRecord]:
        """读取本地章节列表。"""
        return [self.row_to_record(row) for row in self.database.list_chapters()]

    def get_chapter(self, chapter_id: int) -> ChapterRecord | None:
        """读取本地章节详情。"""
        row = self.database.get_chapter(chapter_id)
        return self.row_to_record(row) if row else None

    def delete_chapter(self, chapter_id: int) -> None:
        """删除本地章节缓存。"""
        self.database.delete_chapter(chapter_id)

    def row_to_record(self, row: dict[str, Any]) -> ChapterRecord:
        """把数据库行转换成稳定的数据模型。"""
        return ChapterRecord(
            id=int(row["id"]),
            title=row.get("title") or "未命名章节",
            book_title=row.get("book_title") or "未分组书籍",
            url=row.get("url") or "",
            content=row.get("content") or "",
            prev_url=row.get("prev_url"),
            next_url=row.get("next_url"),
            created_at=row.get("created_at") or "",
        )
