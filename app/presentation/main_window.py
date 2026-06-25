"""应用顶层主窗口。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.novel.presentation.main_window import MainWindow as NovelReaderWindow
from app.video.presentation.video_widget import VideoBrowserWidget


class MainWindow(QMainWindow):
    """承载小说阅读和网页视频两个功能的主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("桌面阅读与网页视频工具")
        self.resize(1200, 750)
        self.setMinimumSize(320, 180)
        self.settings = QSettings()
        self.hide_when_deactivated = False
        self.floating_button_enabled = False
        self.restore_button_dragging = False
        self.restore_button_drag_moved = False
        self.restore_button_drag_offset = QPoint()
        self.restore_button_custom_position: QPoint | None = None
        self.force_quit = False

        self.tabs = QTabWidget()
        self.novel_reader = NovelReaderWindow()
        self.video_browser = VideoBrowserWidget()
        self.pin_button = QPushButton("置顶")
        self.auto_hide_button = QPushButton("切走隐藏")
        self.float_button = QPushButton("悬浮按钮")
        self.restore_button = QPushButton("显示")

        self.tabs.addTab(self.novel_reader, "小说")
        self.tabs.addTab(self.video_browser, "视频网页")
        self.build_ui()
        self.bind_events()
        self.configure_restore_button()
        self.configure_tray_icon()
        self.restore_settings()
        self.apply_dark_theme()

    def build_ui(self) -> None:
        """创建顶层布局和窗口控制按钮。"""
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        controls = QWidget()
        controls.setObjectName("windowControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 8, 14, 8)
        controls_layout.setSpacing(8)

        for button in (self.pin_button, self.auto_hide_button, self.float_button):
            button.setCheckable(True)
            button.setFixedWidth(92)
            controls_layout.addWidget(button)

        controls_layout.addStretch(1)
        root_layout.addWidget(controls)
        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def bind_events(self) -> None:
        """绑定顶层窗口控制事件。"""
        self.pin_button.toggled.connect(self.set_always_on_top)
        self.auto_hide_button.toggled.connect(self.set_hide_when_deactivated)
        self.float_button.toggled.connect(self.set_floating_button_enabled)
        self.restore_button.clicked.connect(self.toggle_main_window_visibility)

    def configure_restore_button(self) -> None:
        """配置隐藏后用于恢复窗口的悬浮按钮。"""
        self.restore_button.setWindowTitle("阅读器控制")
        self.restore_button.setFixedSize(72, 34)
        self.restore_button.setToolTip("点击隐藏或显示主窗口")
        self.restore_button.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.restore_button.installEventFilter(self)
        self.position_restore_button()

    def configure_tray_icon(self) -> None:
        """配置系统托盘入口，便于隐藏后恢复和退出。"""
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("桌面阅读与网页视频工具")

        tray_menu = QMenu(self)
        show_action = QAction("显示/隐藏", self)
        pin_action = QAction("置顶", self)
        pin_action.setCheckable(True)
        auto_hide_action = QAction("切走隐藏", self)
        auto_hide_action.setCheckable(True)
        float_action = QAction("悬浮按钮", self)
        float_action.setCheckable(True)
        quit_action = QAction("退出", self)

        show_action.triggered.connect(self.toggle_main_window_visibility)
        pin_action.toggled.connect(self.pin_button.setChecked)
        auto_hide_action.toggled.connect(self.auto_hide_button.setChecked)
        float_action.toggled.connect(self.float_button.setChecked)
        quit_action.triggered.connect(self.quit_application)
        self.pin_button.toggled.connect(pin_action.setChecked)
        self.auto_hide_button.toggled.connect(auto_hide_action.setChecked)
        self.float_button.toggled.connect(float_action.setChecked)

        tray_menu.addAction(show_action)
        tray_menu.addAction(pin_action)
        tray_menu.addAction(auto_hide_action)
        tray_menu.addAction(float_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.handle_tray_activated)
        self.tray_icon.show()

    def event(self, event: QEvent) -> bool:
        """窗口切到后台时按需隐藏主窗口。"""
        handled = super().event(event)
        if event.type() == QEvent.Type.WindowDeactivate and self.hide_when_deactivated:
            QTimer.singleShot(120, self.hide_if_still_inactive)
        return handled

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:  # noqa: N802
        """处理悬浮按钮拖动事件。"""
        if watched == self.restore_button and self.handle_restore_button_drag(event):
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """主窗口尺寸变化后同步悬浮按钮位置。"""
        super().resizeEvent(event)
        self.position_restore_button()

    def moveEvent(self, event) -> None:  # noqa: N802
        """主窗口移动后同步悬浮按钮位置。"""
        super().moveEvent(event)
        self.position_restore_button()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """关闭主窗口时真正退出应用。"""
        self.save_settings()
        self.restore_button.close()
        self.tray_icon.hide()
        self.novel_reader.save_settings()
        self.video_browser.save_settings()
        self.video_browser.detach_existing_edge_window()
        super().closeEvent(event)
        QTimer.singleShot(0, QApplication.quit)

    def handle_restore_button_drag(self, event: QEvent) -> bool:
        """让悬浮按钮可拖动，避免挡住阅读内容。"""
        if not hasattr(event, "button"):
            return False
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.restore_button_dragging = True
            self.restore_button_drag_moved = False
            self.restore_button_drag_offset = event.globalPosition().toPoint() - self.restore_button.pos()
            return True
        if event.type() == QEvent.Type.MouseMove and self.restore_button_dragging:
            new_position = event.globalPosition().toPoint() - self.restore_button_drag_offset
            if (new_position - self.restore_button.pos()).manhattanLength() > 3:
                self.restore_button_drag_moved = True
            self.restore_button_custom_position = new_position
            self.restore_button.move(new_position)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and self.restore_button_dragging:
            self.restore_button_dragging = False
            if not self.restore_button_drag_moved:
                self.toggle_main_window_visibility()
            self.save_settings()
            return True
        return False

    def set_always_on_top(self, enabled: bool) -> None:
        """切换主窗口置顶显示。"""
        geometry = self.geometry()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.setGeometry(geometry)
        self.show()
        self.raise_()
        self.activateWindow()
        self.pin_button.setText("已置顶" if enabled else "置顶")
        self.position_restore_button()
        self.save_settings()

    def set_hide_when_deactivated(self, enabled: bool) -> None:
        """切换主窗口失去焦点后自动隐藏。"""
        self.hide_when_deactivated = enabled
        self.auto_hide_button.setText("已启用隐藏" if enabled else "切走隐藏")
        self.update_restore_button_visibility()
        self.save_settings()

    def set_floating_button_enabled(self, enabled: bool) -> None:
        """切换常驻悬浮按钮。"""
        self.floating_button_enabled = enabled
        self.float_button.setText("已悬浮" if enabled else "悬浮按钮")
        self.update_restore_button_visibility()
        self.save_settings()

    def hide_if_still_inactive(self) -> None:
        """避免点击窗口内部控件时误触发自动隐藏。"""
        active_window = QApplication.activeWindow()
        if active_window in (self, self.restore_button):
            return
        if not self.isVisible():
            return
        self.hide()
        self.update_restore_button_visibility()

    def toggle_main_window_visibility(self) -> None:
        """悬浮按钮点击后隐藏或恢复主窗口。"""
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()
        self.update_restore_button_visibility()

    def update_restore_button_visibility(self) -> None:
        """根据用户选项和主窗口状态显示悬浮按钮。"""
        should_show = self.floating_button_enabled or not self.isVisible()
        if should_show:
            self.position_restore_button()
            self.restore_button.show()
        else:
            self.restore_button.hide()

    def position_restore_button(self) -> None:
        """把悬浮按钮固定到主窗口右侧；主窗口隐藏时贴到屏幕右上角。"""
        if self.restore_button_custom_position is not None:
            self.restore_button.move(self.restore_button_custom_position)
            return

        if self.isVisible():
            point = self.mapToGlobal(QPoint(self.width() - 84, 44))
        else:
            screen = QApplication.primaryScreen()
            available = screen.availableGeometry() if screen else self.geometry()
            point = QPoint(available.right() - 88, available.top() + 120)
        self.restore_button.move(point)

    def handle_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """双击托盘图标切换主窗口显示状态。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_main_window_visibility()

    def restore_settings(self) -> None:
        """恢复上次窗口、置顶、隐藏和悬浮按钮设置。"""
        geometry = self.settings.value("main/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        float_pos = self.settings.value("main/restore_button_pos")
        if isinstance(float_pos, QPoint):
            self.restore_button_custom_position = float_pos

        self.pin_button.setChecked(self.settings.value("main/always_on_top", False, type=bool))
        self.auto_hide_button.setChecked(self.settings.value("main/hide_when_deactivated", False, type=bool))
        self.float_button.setChecked(self.settings.value("main/floating_button", False, type=bool))
        self.tabs.setCurrentIndex(self.settings.value("main/current_tab", 0, type=int))
        self.novel_reader.restore_settings()
        self.video_browser.restore_settings()
        self.update_restore_button_visibility()

    def save_settings(self) -> None:
        """保存窗口和模块设置。"""
        self.settings.setValue("main/geometry", self.saveGeometry())
        self.settings.setValue("main/always_on_top", self.pin_button.isChecked())
        self.settings.setValue("main/hide_when_deactivated", self.auto_hide_button.isChecked())
        self.settings.setValue("main/floating_button", self.float_button.isChecked())
        self.settings.setValue("main/current_tab", self.tabs.currentIndex())
        if self.restore_button_custom_position is not None:
            self.settings.setValue("main/restore_button_pos", self.restore_button_custom_position)
        self.novel_reader.save_settings()
        self.video_browser.save_settings()

    def quit_application(self) -> None:
        """从托盘菜单真正退出应用。"""
        self.force_quit = True
        self.close()

    def apply_dark_theme(self) -> None:
        """应用顶层标签页暗色样式。"""
        self.setStyleSheet(
            """
            QMainWindow, QTabWidget::pane {
                background: #1e1e1e;
                border: 0;
            }
            QWidget#windowControls {
                background: #252526;
                border-bottom: 1px solid #3c3c3c;
            }
            QWidget#windowControls QPushButton {
                background: #333333;
                color: #d4d4d4;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QWidget#windowControls QPushButton:hover {
                background: #3c3c3c;
            }
            QWidget#windowControls QPushButton:checked {
                background: #0e639c;
                color: #ffffff;
                border-color: #1177bb;
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
        self.restore_button.setStyleSheet(
            """
            QPushButton {
                background: #0e639c;
                color: #ffffff;
                border: 1px solid #1177bb;
                border-radius: 6px;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1177bb;
            }
            """
        )
