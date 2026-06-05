"""PySide6 主窗口模块。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QThreadPool, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.novel.application.services import NovelReaderService
from app.novel.domain.models import ChapterRecord
from app.novel.presentation.workers import FetchChapterWorker


class MainWindow(QMainWindow):
    """小说阅读器主窗口。"""

    MIN_READER_FONT_SIZE = 10
    MAX_READER_FONT_SIZE = 28
    AUTO_HIDE_SIDEBAR_WIDTH = 820
    COMPACT_TOOLBAR_WIDTH = 700
    HIDE_STATUS_WIDTH = 760
    TINY_TOOLBAR_WIDTH = 560
    MINI_READER_WIDTH = 500

    def __init__(self) -> None:
        super().__init__()
        self.service = NovelReaderService()
        self.thread_pool = QThreadPool.globalInstance()
        self.current_worker: FetchChapterWorker | None = None
        self.current_chapter_id: int | None = None
        self.current_prev_url: str | None = None
        self.current_next_url: str | None = None
        self.reader_font_size = 18
        self.focus_mode = False
        self.reader_click_timer = QTimer(self)
        self.reader_click_timer.setSingleShot(True)
        self.reader_click_timer.timeout.connect(self.handle_reader_single_click)

        self.setWindowTitle("Python 桌面小说阅读器")
        self.resize(1200, 750)
        self.setMinimumSize(320, 180)

        self.url_label = QLabel("章节 URL")
        self.url_input = QLineEdit()
        self.fetch_button = QPushButton("获取章节")
        self.clear_button = QPushButton("清空")
        self.prev_button = QPushButton("上一章")
        self.next_button = QPushButton("下一章")
        self.focus_button = QPushButton("专注")
        self.chapter_list = QListWidget()
        self.reader = QTextBrowser()
        self.status_title_label = QLabel("当前章节：无")
        self.status_count_label = QLabel("正文字数：0")
        self.status_source_label = QLabel("来源：无")

        self.build_ui()
        self.apply_dark_theme()
        self.bind_events()
        self.refresh_chapter_list()
        self.update_navigation_buttons()
        self.update_status_bar("", "", None)
        self.apply_responsive_layout()

    def build_ui(self) -> None:
        """创建窗口布局。"""
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.toolbar = QWidget()
        self.toolbar.setObjectName("topToolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        toolbar_layout.setSpacing(10)

        self.url_input.setPlaceholderText("请输入第一章或任意章节的公开 URL")
        self.url_input.setMinimumWidth(80)
        self.fetch_button.setFixedWidth(110)
        self.clear_button.setFixedWidth(72)
        self.prev_button.setFixedWidth(80)
        self.next_button.setFixedWidth(80)
        self.focus_button.setFixedWidth(72)

        toolbar_layout.addWidget(self.url_label)
        toolbar_layout.addWidget(self.url_input, 1)
        toolbar_layout.addWidget(self.clear_button)
        toolbar_layout.addWidget(self.prev_button)
        toolbar_layout.addWidget(self.next_button)
        toolbar_layout.addWidget(self.focus_button)
        toolbar_layout.addWidget(self.fetch_button)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(14, 14, 14, 14)
        self.content_layout.setSpacing(12)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        self.left_panel = QWidget()
        self.left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        list_title = QLabel("本地章节")
        left_layout.addWidget(list_title)
        left_layout.addWidget(self.chapter_list, 1)
        self.left_panel.setMinimumWidth(180)
        self.left_panel.setMaximumWidth(420)
        self.reader.setMinimumWidth(120)

        self.reader.setOpenExternalLinks(False)
        self.reader.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.reader.viewport().installEventFilter(self)

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.reader)
        self.splitter.setSizes([320, 880])

        self.content_layout.addWidget(self.splitter, 1)
        root_layout.addWidget(self.toolbar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.statusBar().addWidget(self.status_title_label, 1)
        self.statusBar().addPermanentWidget(self.status_count_label)
        self.statusBar().addPermanentWidget(self.status_source_label)

    def bind_events(self) -> None:
        """绑定界面事件。"""
        self.fetch_button.clicked.connect(self.fetch_chapter)
        self.clear_button.clicked.connect(self.url_input.clear)
        self.prev_button.clicked.connect(self.fetch_prev_chapter)
        self.next_button.clicked.connect(self.fetch_next_chapter)
        self.focus_button.clicked.connect(self.toggle_focus_mode)
        self.url_input.returnPressed.connect(self.fetch_chapter)
        self.chapter_list.itemClicked.connect(self.show_saved_chapter)
        self.chapter_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chapter_list.customContextMenuRequested.connect(self.show_chapter_context_menu)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """迷你窗口下把正文区域点击转换为翻页手势。"""
        if watched == self.reader.viewport() and self.is_mini_reader_mode():
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self.reader_click_timer.stop()
                self.scroll_reader_up()
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.reader_click_timer.start(180)
                    return True
        return super().eventFilter(watched, event)

    def toggle_focus_mode(self) -> None:
        """切换低干扰阅读界面。"""
        self.focus_mode = not self.focus_mode
        self.setWindowTitle("工作笔记 - notes.md" if self.focus_mode else "Python 桌面小说阅读器")
        self.focus_button.setText("退出" if self.focus_mode else "专注")
        self.statusBar().setVisible(not self.focus_mode)
        self.apply_responsive_layout()
        self.update_reader_stylesheet()

    def resizeEvent(self, event) -> None:  # noqa: N802
        """窗口缩放时自动切换紧凑布局。"""
        super().resizeEvent(event)
        self.apply_responsive_layout()
        self.update_reader_stylesheet()

    def apply_responsive_layout(self) -> None:
        """根据窗口宽度隐藏非核心控件，允许更小窗口阅读。"""
        width = self.width()
        sidebar_visible = (not self.focus_mode) and width >= self.AUTO_HIDE_SIDEBAR_WIDTH
        url_controls_visible = (not self.focus_mode) and width >= self.COMPACT_TOOLBAR_WIDTH
        status_visible = (not self.focus_mode) and width >= self.HIDE_STATUS_WIDTH
        tiny_toolbar = width < self.TINY_TOOLBAR_WIDTH
        mini_reader = width < self.MINI_READER_WIDTH

        self.toolbar.setVisible(not mini_reader)
        self.left_panel.setVisible(sidebar_visible)
        self.url_label.setVisible(url_controls_visible)
        self.url_input.setVisible(url_controls_visible)
        self.clear_button.setVisible(url_controls_visible)
        self.fetch_button.setVisible(url_controls_visible)
        self.statusBar().setVisible(status_visible)

        self.prev_button.setText("上" if tiny_toolbar else "上一章")
        self.next_button.setText("下" if tiny_toolbar else "下一章")
        self.focus_button.setText("退" if (tiny_toolbar and self.focus_mode) else "退出" if self.focus_mode else "专" if tiny_toolbar else "专注")
        self.prev_button.setFixedWidth(46 if tiny_toolbar else 80)
        self.next_button.setFixedWidth(46 if tiny_toolbar else 80)
        self.focus_button.setFixedWidth(46 if tiny_toolbar else 72)
        margin = 2 if mini_reader else 14
        self.content_layout.setContentsMargins(margin, margin, margin, margin)

    def is_mini_reader_mode(self) -> bool:
        """判断当前是否处于隐藏工具栏的迷你阅读模式。"""
        return self.width() < self.MINI_READER_WIDTH

    def handle_reader_single_click(self) -> None:
        """迷你模式下单击正文：优先向下翻页，到底后进入下一章。"""
        if not self.is_mini_reader_mode():
            return

        scroll_bar = self.reader.verticalScrollBar()
        if scroll_bar.value() < scroll_bar.maximum():
            next_value = min(scroll_bar.value() + scroll_bar.pageStep(), scroll_bar.maximum())
            scroll_bar.setValue(next_value)
            return

        if self.current_next_url:
            self.fetch_next_chapter()

    def scroll_reader_up(self) -> None:
        """迷你模式下双击正文：向上翻页，到顶部后进入上一章。"""
        scroll_bar = self.reader.verticalScrollBar()
        if scroll_bar.value() <= scroll_bar.minimum():
            if self.current_prev_url:
                self.fetch_prev_chapter()
            return

        previous_value = max(scroll_bar.value() - scroll_bar.pageStep(), scroll_bar.minimum())
        scroll_bar.setValue(previous_value)

    def fetch_chapter(self) -> None:
        """点击按钮后开始后台获取输入框中的章节。"""
        self.start_fetch(self.url_input.text().strip())

    def fetch_prev_chapter(self) -> None:
        """根据当前章节解析出的上一章链接继续阅读。"""
        if not self.current_prev_url:
            QMessageBox.information(self, "提示", "当前章节没有解析到上一章链接。")
            return
        self.start_fetch(self.current_prev_url)

    def fetch_next_chapter(self) -> None:
        """根据当前章节解析出的下一章链接继续阅读。"""
        if not self.current_next_url:
            QMessageBox.information(self, "提示", "当前章节没有解析到下一章链接。")
            return
        self.start_fetch(self.current_next_url)

    def start_fetch(self, url: str) -> None:
        """启动后台获取任务，统一处理手动 URL 和章节导航。"""
        if not url:
            QMessageBox.warning(self, "提示", "请先输入章节 URL。")
            return

        self.url_input.setText(url)
        self.set_fetching_state(True)
        worker = FetchChapterWorker(self.service, url)
        worker.signals.finished.connect(self.handle_fetch_success)
        worker.signals.error.connect(self.handle_fetch_error)
        self.current_worker = worker
        self.thread_pool.start(worker)

    def handle_fetch_success(self, chapter: ChapterRecord) -> None:
        """获取成功后刷新列表并显示正文。"""
        self.refresh_chapter_list(selected_id=chapter.id)
        self.display_chapter(
            chapter_id=chapter.id,
            title=chapter.title,
            url=chapter.url,
            content=chapter.content,
            from_cache=False,
            prev_url=chapter.prev_url,
            next_url=chapter.next_url,
        )
        self.set_fetching_state(False)
        self.current_worker = None

    def handle_fetch_error(self, message: str) -> None:
        """获取失败时恢复按钮状态并显示错误。"""
        self.set_fetching_state(False)
        self.current_worker = None
        QMessageBox.critical(self, "获取失败", message)

    def set_fetching_state(self, fetching: bool) -> None:
        """切换按钮状态，防止重复点击。"""
        self.fetch_button.setEnabled(not fetching)
        self.prev_button.setEnabled((not fetching) and bool(self.current_prev_url))
        self.next_button.setEnabled((not fetching) and bool(self.current_next_url))
        self.fetch_button.setText("获取中..." if fetching else "获取章节")

    def refresh_chapter_list(self, selected_id: int | None = None) -> None:
        """刷新左侧本地章节列表，按书名分组显示章节。"""
        self.chapter_list.clear()
        current_book_title: str | None = None
        for chapter in self.service.list_chapters():
            book_title = chapter.book_title or "未分组书籍"
            if book_title != current_book_title:
                current_book_title = book_title
                header = QListWidgetItem(f"📖 {book_title}")
                header.setData(Qt.ItemDataRole.UserRole, None)
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.chapter_list.addItem(header)

            title = chapter.title or "未命名章节"
            item = QListWidgetItem(f"    {title}")
            item.setData(Qt.ItemDataRole.UserRole, chapter.id)
            item.setToolTip(f"{book_title}\n{title}\n{chapter.url}")
            self.chapter_list.addItem(item)
            if selected_id is not None and chapter.id == selected_id:
                item.setSelected(True)

    def show_saved_chapter(self, item: QListWidgetItem) -> None:
        """点击左侧章节后显示本地保存的正文。"""
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        if chapter_id is None:
            return
        chapter = self.service.get_chapter(int(chapter_id))
        if chapter is None:
            QMessageBox.warning(self, "提示", "没有找到该章节。")
            self.refresh_chapter_list()
            return
        self.display_chapter(
            chapter_id=chapter.id,
            title=chapter.title,
            url=chapter.url,
            content=chapter.content,
            from_cache=True,
            prev_url=chapter.prev_url,
            next_url=chapter.next_url,
        )

    def show_chapter_context_menu(self, position: QPoint) -> None:
        """显示左侧章节列表的右键菜单。"""
        item = self.chapter_list.itemAt(position)
        if item is None:
            return
        if item.data(Qt.ItemDataRole.UserRole) is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("删除本地章节")
        selected_action = menu.exec(self.chapter_list.mapToGlobal(position))
        if selected_action == delete_action:
            self.delete_saved_chapter(item)

    def delete_saved_chapter(self, item: QListWidgetItem) -> None:
        """删除右键选中的本地章节记录。"""
        chapter_id = int(item.data(Qt.ItemDataRole.UserRole))
        title = item.text()
        result = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除本地章节“{title}”吗？\n此操作只删除本地缓存，不会影响网站内容。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        self.service.delete_chapter(chapter_id)
        self.refresh_chapter_list()
        if self.current_chapter_id == chapter_id:
            self.clear_reader()

    def clear_reader(self) -> None:
        """清空阅读区和当前章节状态。"""
        self.current_chapter_id = None
        self.current_prev_url = None
        self.current_next_url = None
        self.reader.clear()
        self.update_navigation_buttons()
        self.update_status_bar("", "", None)

    def display_chapter(
        self,
        chapter_id: int,
        title: str,
        url: str,
        content: str,
        from_cache: bool,
        prev_url: str | None,
        next_url: str | None,
    ) -> None:
        """在右侧阅读区显示章节标题、URL 和正文。"""
        self.current_chapter_id = chapter_id
        self.current_prev_url = prev_url
        self.current_next_url = next_url
        self.url_input.setText(url)
        self.update_navigation_buttons()

        safe_title = self.escape_html(title)
        safe_url = self.escape_html(url)
        safe_content = self.escape_html(content).replace("\n", "<br>")
        html = f"""
        <article>
            <h1>{safe_title}</h1>
            <p class="url">{safe_url}</p>
            <div class="content">{safe_content}</div>
        </article>
        """
        self.reader.setHtml(html)
        self.update_status_bar(title, content, from_cache)

    def update_navigation_buttons(self) -> None:
        """根据当前章节是否有导航链接启用或禁用按钮。"""
        fetching = self.current_worker is not None
        self.prev_button.setEnabled((not fetching) and bool(self.current_prev_url))
        self.next_button.setEnabled((not fetching) and bool(self.current_next_url))
        self.prev_button.setToolTip(self.current_prev_url or "当前章节没有上一章链接")
        self.next_button.setToolTip(self.current_next_url or "当前章节没有下一章链接")

    def update_status_bar(self, title: str, content: str, from_cache: bool | None) -> None:
        """更新状态栏中的当前章节、字数和来源信息。"""
        shown_title = title if title else "无"
        word_count = len("".join(content.split())) if content else 0
        if from_cache is None:
            source = "无"
        else:
            source = "数据库缓存" if from_cache else "网络获取"

        self.status_title_label.setText(f"当前章节：{shown_title}")
        self.status_count_label.setText(f"正文字数：{word_count}")
        self.status_source_label.setText(f"来源：{source}")

    def escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符，避免正文被当作标签渲染。"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    def apply_dark_theme(self) -> None:
        """应用接近 VSCode 的暗色主题。"""
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 14px;
            }
            QWidget#topToolbar {
                background: #333333;
                border-bottom: 1px solid #3c3c3c;
            }
            QWidget#leftPanel {
                background: #252526;
            }
            QLabel {
                color: #d4d4d4;
            }
            QLineEdit {
                background: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px 10px;
                selection-background-color: #264f78;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
            QPushButton {
                background: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #1177bb;
            }
            QPushButton:disabled {
                background: #3c3c3c;
                color: #858585;
            }
            QListWidget {
                background: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 9px 10px;
                border-bottom: 1px solid #2d2d2d;
            }
            QListWidget::item:hover {
                background: #2a2d2e;
            }
            QListWidget::item:selected {
                background: #37373d;
                color: #ffffff;
            }
            QMenu {
                background: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
            QMenu::item {
                padding: 8px 24px;
            }
            QMenu::item:selected {
                background: #37373d;
            }
            QTextBrowser {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 6px;
                selection-background-color: #264f78;
            }
            QSplitter::handle {
                background: #3c3c3c;
                width: 1px;
            }
            QStatusBar {
                background: #007acc;
                color: #ffffff;
                border-top: 1px solid #005a9e;
            }
            QStatusBar QLabel {
                color: #ffffff;
                padding: 0 8px;
            }
            """
        )
        self.update_reader_stylesheet()

    def update_reader_stylesheet(self) -> None:
        """根据当前字号和模式刷新正文区域样式。"""
        font_size = self.calculated_reader_font_size()
        mini_reader = self.width() < self.MINI_READER_WIDTH
        title_color = "#d4d4d4" if self.focus_mode else "#ffffff"
        title_size = font_size if self.focus_mode else font_size + (3 if mini_reader else 10)
        url_display = "none" if (self.focus_mode or mini_reader) else "block"
        line_height = 1.55 if mini_reader else 1.75
        self.reader.document().setDefaultStyleSheet(
            f"""
            body {{
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: {font_size}px;
                line-height: {line_height};
            }}
            h1 {{
                color: {title_color};
                font-size: {title_size}px;
                font-weight: 500;
                margin-bottom: {4 if mini_reader else 12}px;
            }}
            .url {{
                color: #858585;
                display: {url_display};
                font-size: 12px;
                margin-bottom: 24px;
            }}
            .content {{
                color: #d4d4d4;
                white-space: normal;
            }}
            """
        )

    def calculated_reader_font_size(self) -> int:
        """根据窗口尺寸计算正文基础字号。"""
        width = self.width()
        height = self.height()
        compact_base = min(width, int(height * 1.45))
        auto_size = 10 + round(max(0, compact_base - 360) / 120)
        return max(self.MIN_READER_FONT_SIZE, min(self.MAX_READER_FONT_SIZE, auto_size))
