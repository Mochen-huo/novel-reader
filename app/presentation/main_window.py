"""应用顶层主窗口。"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.novel.presentation.main_window import MainWindow as NovelReaderWindow
from app.video.presentation.video_widget import VideoBrowserWidget


class MainWindow(QMainWindow):
    """承载小说阅读和网页视频两个功能的主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("桌面阅读与网页视频工具")
        self.resize(1200, 750)
        self.setMinimumSize(320, 180)

        self.tabs = QTabWidget()
        self.novel_reader = NovelReaderWindow()
        self.video_browser = VideoBrowserWidget()

        self.tabs.addTab(self.novel_reader, "小说")
        self.tabs.addTab(self.video_browser, "视频网页")
        self.setCentralWidget(self.tabs)
        self.apply_dark_theme()

    def apply_dark_theme(self) -> None:
        """应用顶层标签页暗色样式。"""
        self.setStyleSheet(
            """
            QMainWindow, QTabWidget::pane {
                background: #1e1e1e;
                border: 0;
            }
            QTabBar::tab {
                background: #252526;
                color: #d4d4d4;
                padding: 8px 18px;
                border-right: 1px solid #3c3c3c;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #ffffff;
                border-top: 2px solid #007acc;
            }
            """
        )
