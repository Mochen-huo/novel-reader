"""后台任务模块。"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from app.novel.application.services import NovelReaderService


class WorkerSignals(QObject):
    """后台任务信号，用于把结果安全传回主线程。"""

    finished = Signal(object)
    error = Signal(str)


class FetchChapterWorker(QRunnable):
    """后台获取并保存章节任务，避免网络请求卡住界面。"""

    def __init__(self, service: NovelReaderService, url: str) -> None:
        super().__init__()
        self.service = service
        self.url = url
        self.signals = WorkerSignals()

    def run(self) -> None:
        """执行章节获取流程，并通过信号返回保存后的章节记录。"""
        try:
            chapter = self.service.fetch_and_save_chapter(self.url)
        except Exception as exc:
            self.signals.error.emit(str(exc))
            return
        self.signals.finished.emit(chapter)
