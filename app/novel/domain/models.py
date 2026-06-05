"""领域数据模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterRecord:
    """界面和服务层使用的章节记录。"""

    id: int
    title: str
    book_title: str
    url: str
    content: str
    prev_url: str | None = None
    next_url: str | None = None
    created_at: str = ""
